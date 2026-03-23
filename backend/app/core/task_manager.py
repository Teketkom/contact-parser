"""
Менеджер фоновых задач парсинга контактов.
Управляет жизненным циклом задач, прогрессом, WebSocket-подписками
и восстановлением состояния после перезапуска сервера.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from asyncio import Queue
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.config import settings
from app.core.normalizer import normalize_contacts
from app.core.enricher import DataEnricher
from app.models import (
    ExtractionVariant,
    ParseMode,
    ParseTask,
    ParseTaskRequest,
    SiteEntry,
    TaskProgress,
    TaskStatus,
    WSMessage,
    WSMessageType,
)

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Асинхронный менеджер задач парсинга.

    Отвечает за:
    - Создание и хранение задач
    - Запуск фоновых задач через asyncio
    - Отслеживание прогресса и рассылку WebSocket-обновлений
    - Сохранение/восстановление состояния на диск
    - Управление семафором для ограничения параллельных браузеров
    """

    def __init__(self) -> None:
        self.tasks: dict[str, ParseTask] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._subscribers: dict[str, list[Queue]] = {}
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._cancel_events: dict[str, asyncio.Event] = {}

    async def startup(self) -> None:
        """Инициализация при запуске: загружает сохранённые задачи."""
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_BROWSERS)
        self._load_state()
        logger.info("TaskManager запущен, загружено задач: %d", len(self.tasks))

    async def shutdown(self) -> None:
        """Завершение работы: сохраняет состояние, отменяет активные задачи."""
        for task_id, async_task in list(self._running.items()):
            logger.info("Отмена задачи %s при остановке сервера", task_id)
            async_task.cancel()
            try:
                await asyncio.wait_for(async_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        for task_id, task in self.tasks.items():
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.PAUSED
                task.error_message = "Сервер остановлен во время выполнения"

        self._save_state()
        logger.info("TaskManager остановлен")

    async def create_task(
        self,
        mode: ParseMode,
        variant: ExtractionVariant,
        sites: list[SiteEntry],
        target_positions: list[str],
        search_queries: list[str],
    ) -> ParseTask:
        """Создаёт новую задачу парсинга и сохраняет её состояние."""
        task = ParseTask(
            mode=mode,
            variant=ExtractionVariant.AI,  # Всегда Вариант B
            sites=sites,
            target_positions=target_positions,
            search_queries=search_queries,
            progress=TaskProgress(total_sites=len(sites)),
        )
        task_id = str(task.task_id)
        self.tasks[task_id] = task
        self._cancel_events[task_id] = asyncio.Event()
        self._save_state()
        logger.info("Создана задача %s (режим=%s, сайтов=%d)", task_id, mode, len(sites))
        return task

    async def run_task(self, task_id: str) -> None:
        """Запускает задачу в фоновом режиме через asyncio."""
        task = self.tasks.get(task_id)
        if not task:
            logger.error("Задача %s не найдена", task_id)
            return

        coro = self._execute_task(task_id)
        async_task = asyncio.create_task(coro, name=f"parse-{task_id}")
        self._running[task_id] = async_task

        try:
            await async_task
        except asyncio.CancelledError:
            logger.info("Задача %s отменена", task_id)
        except Exception as exc:
            logger.exception("Задача %s завершилась с ошибкой: %s", task_id, exc)
        finally:
            self._running.pop(task_id, None)

    async def cancel_task(self, task_id: str) -> None:
        """Отменяет выполняющуюся задачу."""
        if task_id in self._cancel_events:
            self._cancel_events[task_id].set()

        async_task = self._running.get(task_id)
        if async_task and not async_task.done():
            async_task.cancel()

        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.CANCELLED
            task.finished_at = datetime.utcnow()
            self._save_state()

        await self._broadcast(
            task_id,
            WSMessageType.CANCELLED,
            {"message": f"Задача {task_id} отменена"},
        )

    async def _execute_task(self, task_id: str) -> None:
        """Основной цикл выполнения задачи парсинга."""
        task = self.tasks[task_id]
        cancel_event = self._cancel_events.get(task_id, asyncio.Event())

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        start_time = time.monotonic()
        self._save_state()

        result_dir = settings.RESULTS_DIR / datetime.utcnow().strftime("Результаты_парсинга/%Y-%m-%d_%H-%M")
        result_dir.mkdir(parents=True, exist_ok=True)

        log_file = result_dir / f"errors_{task_id[:8]}.txt"
        task.log_file = str(log_file)

        error_log_lines: list[str] = []
        all_results = []

        try:
            from app.core.crawler import SiteCrawler
            from app.core.extractor import ContactExtractor
            from app.core.exporter import ExcelExporter
            from app.core.blacklist import blacklist_manager

            extractor = ContactExtractor(
                variant=ExtractionVariant.AI,  # Всегда Вариант B
                target_positions=task.target_positions,
                mode=task.mode,
            )

            sites_to_process = task.sites

            if task.mode == ParseMode.AUTO_SEARCH:
                sites_to_process = await self._auto_search_sites(
                    task.search_queries, cancel_event
                )
                task.progress.total_sites = len(sites_to_process)
                await self._broadcast_progress(task_id, task, start_time)

            total = len(sites_to_process)

            for idx, site_entry in enumerate(sites_to_process):
                if cancel_event.is_set():
                    logger.info("Задача %s: обнаружена отмена на сайте %d", task_id, idx)
                    break

                url = site_entry.url

                if blacklist_manager.is_domain_blocked(url):
                    logger.info("Пропуск заблокированного сайта: %s", url)
                    error_log_lines.append(f"[BLACKLIST] {url} — в чёрном списке")
                    task.progress.processed_sites += 1
                    task.progress.errors += 1
                    continue

                task.progress.current_site = url
                await self._broadcast_progress(task_id, task, start_time)

                await self._broadcast(
                    task_id,
                    WSMessageType.LOG,
                    {"message": f"[{idx+1}/{total}] Обработка: {url}"},
                )

                try:
                    async with self._semaphore:
                        crawler = SiteCrawler(cancel_event=cancel_event)
                        pages = await crawler.crawl_site(url)
                        task.progress.total_pages += len(pages)

                    contacts = []
                    for page_url, page_html, page_lang in pages:
                        if cancel_event.is_set():
                            break
                        task.progress.current_page = page_url
                        try:
                            page_contacts = await extractor.extract(
                                html=page_html,
                                page_url=page_url,
                                site_url=url,
                                company_name=site_entry.company_name,
                                inn=site_entry.inn,
                                language=page_lang,
                            )
                            contacts.extend(page_contacts)
                            task.progress.llm_tokens_used = extractor.tokens_used
                            task.progress.fallback_count = extractor.fallback_count

                        except Exception as page_exc:
                            msg = f"[PAGE_ERROR] {page_url}: {page_exc}"
                            error_log_lines.append(msg)
                            logger.warning(msg)
                            task.progress.errors += 1

                    unique_contacts = _deduplicate_contacts(contacts)
                    # Нормализация контактов перед экспортом
                    unique_contacts = normalize_contacts(unique_contacts)
                    task.progress.contacts_found += len(unique_contacts)
                    all_results.append({
                        "site_url": url,
                        "company_name": site_entry.company_name,
                        "contacts": unique_contacts,
                    })

                except asyncio.CancelledError:
                    raise
                except Exception as site_exc:
                    msg = f"[SITE_ERROR] {url}: {site_exc}"
                    error_log_lines.append(msg)
                    logger.warning("Ошибка при обработке %s: %s", url, site_exc)
                    task.progress.errors += 1

                task.progress.processed_sites += 1
                task.progress.percent = (task.progress.processed_sites / total * 100) if total > 0 else 0
                await self._broadcast_progress(task_id, task, start_time)

            if all_results:
                # Обогащение данных (ИНН/КПП, company_email)
                try:
                    enricher = DataEnricher()
                    all_results = await enricher.enrich(all_results)
                    logger.info("Обогащение данных завершено")
                except Exception as enrich_exc:
                    logger.warning("Ошибка обогащения данных: %s", enrich_exc)

                exporter = ExcelExporter()
                result_path = await exporter.export(
                    results=all_results,
                    task=task,
                    output_dir=result_dir,
                )
                task.result_file = str(result_path)

            if error_log_lines:
                log_file.write_text("\n".join(error_log_lines), encoding="utf-8")

            task.status = TaskStatus.COMPLETED
            task.progress.percent = 100.0

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            logger.info("Задача %s отменена", task_id)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            logger.exception("Критическая ошибка задачи %s: %s", task_id, exc)
            error_log_lines.append(f"[FATAL] {exc}")
            if error_log_lines:
                log_file.write_text("\n".join(error_log_lines), encoding="utf-8")
        finally:
            task.finished_at = datetime.utcnow()
            task.progress.elapsed_seconds = time.monotonic() - start_time
            task.progress.current_site = None
            task.progress.current_page = None
            self._save_state()

        if task.status == TaskStatus.COMPLETED:
            await self._broadcast(
                task_id,
                WSMessageType.COMPLETED,
                {
                    "contacts_found": task.progress.contacts_found,
                    "result_file": task.result_file,
                    "duration": task.progress.elapsed_seconds,
                },
            )
        elif task.status == TaskStatus.FAILED:
            await self._broadcast(
                task_id,
                WSMessageType.ERROR,
                {"message": task.error_message},
            )

    async def _auto_search_sites(
        self,
        queries: list[str],
        cancel_event: asyncio.Event,
    ) -> list[SiteEntry]:
        import httpx
        from urllib.parse import urlencode

        sites: list[SiteEntry] = []
        seen_domains: set[str] = set()

        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ContactParserBot/1.0)"},
            follow_redirects=True,
        ) as client:
            for query in queries:
                if cancel_event.is_set():
                    break
                try:
                    params = urlencode({"q": query, "num": 10})
                    resp = await client.get(f"https://www.google.com/search?{params}")
                    import re
                    from urllib.parse import urlparse, unquote
                    urls = re.findall(r'/url\?q=(https?://[^&"]+)', resp.text)
                    for raw_url in urls:
                        url = unquote(raw_url)
                        try:
                            parsed = urlparse(url)
                            domain = parsed.netloc.lower().lstrip("www.")
                            if domain and domain not in seen_domains:
                                seen_domains.add(domain)
                                sites.append(SiteEntry(url=f"{parsed.scheme}://{parsed.netloc}"))
                        except Exception:
                            pass
                    await asyncio.sleep(2.0)
                except Exception as exc:
                    logger.warning("Ошибка автопоиска по запросу '%s': %s", query, exc)

        logger.info("Автопоиск нашёл %d уникальных сайтов", len(sites))
        return sites

    async def subscribe(self, task_id: str) -> Queue:
        queue: Queue = asyncio.Queue(maxsize=100)
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(queue)
        return queue

    async def unsubscribe(self, task_id: str, queue: Queue) -> None:
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass

    async def _broadcast(
        self,
        task_id: str,
        msg_type: WSMessageType,
        data: dict[str, Any],
    ) -> None:
        message = WSMessage(
            type=msg_type,
            task_id=task_id,
            data=data,
        ).model_dump(mode="json")

        subscribers = self._subscribers.get(task_id, [])
        for queue in list(subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(message)
                except Exception:
                    pass

    async def _broadcast_progress(
        self,
        task_id: str,
        task: ParseTask,
        start_time: float,
    ) -> None:
        elapsed = time.monotonic() - start_time
        task.progress.elapsed_seconds = elapsed

        if task.progress.processed_sites > 0 and task.progress.total_sites > 0:
            rate = task.progress.processed_sites / elapsed
            remaining = task.progress.total_sites - task.progress.processed_sites
            task.progress.eta_seconds = remaining / rate if rate > 0 else None

        await self._broadcast(
            task_id,
            WSMessageType.PROGRESS,
            task.progress.model_dump(),
        )

    def _save_state(self) -> None:
        try:
            state = {}
            for task_id, task in self.tasks.items():
                state[task_id] = task.model_dump(mode="json")
            settings.TASKS_STATE_FILE.write_text(
                json.dumps(state, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Ошибка сохранения состояния задач: %s", exc)

    def _load_state(self) -> None:
        if not settings.TASKS_STATE_FILE.exists():
            return
        try:
            data = json.loads(
                settings.TASKS_STATE_FILE.read_text(encoding="utf-8")
            )
            for task_id, task_data in data.items():
                try:
                    task = ParseTask.model_validate(task_data)
                    if task.status == TaskStatus.RUNNING:
                        task.status = TaskStatus.PAUSED
                        task.error_message = "Прервано при перезапуске сервера"
                    self.tasks[task_id] = task
                    self._cancel_events[task_id] = asyncio.Event()
                except Exception as exc:
                    logger.warning("Не удалось восстановить задачу %s: %s", task_id, exc)
            logger.info("Восстановлено %d задач из сохранённого состояния", len(self.tasks))
        except Exception as exc:
            logger.error("Ошибка загрузки состояния задач: %s", exc)


def _deduplicate_contacts(contacts: list) -> list:
    seen: set[str] = set()
    unique: list = []
    for c in contacts:
        key = f"{c.full_name or ''}|{c.personal_email or ''}|{c.phone or ''}"
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


# Синглтон менеджера задач
task_manager = TaskManager()
