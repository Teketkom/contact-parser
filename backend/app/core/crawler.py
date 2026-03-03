"""
Веб-краулер на базе Playwright для сбора HTML-контента страниц.
Поддерживает JS-рендеринг, ротацию User-Agent, адаптивные задержки,
соблюдение robots.txt, обработку ошибок и прокси.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from asyncio import Event
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
)

from app.config import settings

logger = logging.getLogger(__name__)

# ── User-Agent ротация ─────────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
]

# ── Ключевые слова для поиска страниц с контактами ────────────────────────────
CONTACT_PAGE_KEYWORDS = [
    # Русские
    "руководство", "команда", "о компании", "о нас", "контакты",
    "структура", "сотрудники", "управление", "персонал", "менеджмент",
    "директор", "правление", "совет", "органы управления",
    "топ-менеджмент", "менеджеры", "коллектив", "наши специалисты",
    # Английские
    "management", "team", "about", "leadership", "staff",
    "executives", "directors", "board", "officers", "people",
    "who we are", "our team", "contacts", "contact us",
    "company", "organization", "structure",
]

# ── Паттерн CAPTCHA ─────────────────────────────────────────────────────────────
CAPTCHA_PATTERNS = re.compile(
    r"(captcha|recaptcha|hcaptcha|cf-challenge|challenge-form|"
    r"cloudflare.*challenge|ddos.*protection|access.*denied.*robot|"
    r"prove.*human|are you a robot|verify.*human)",
    re.I,
)

# ── Стоп-расширения файлов ────────────────────────────────────────────────────────
SKIP_EXTENSIONS = re.compile(
    r"\.(pdf|doc|docx|xls|xlsx|zip|rar|tar|gz|exe|msi|"
    r"jpg|jpeg|png|gif|bmp|svg|ico|webp|mp4|mp3|avi|"
    r"css|js|json|xml|rss|atom|woff|woff2|ttf|eot)$",
    re.I,
)


class BrowserPool:
    """
    Пул браузерных инстансов Playwright.
    Управляет запуском/остановкой, предоставляет контексты для задач.
    """

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()
        self.active_count: int = 0

    async def startup(self) -> None:
        """Запускает Playwright и браузер."""
        self._playwright = await async_playwright().start()
        launch_kwargs: dict = {
            "headless": settings.HEADLESS,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1920,1080",
            ],
        }
        if settings.PROXY_URL:
            launch_kwargs["proxy"] = {"server": settings.PROXY_URL}

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        logger.info("Playwright Chromium запущен (headless=%s)", settings.HEADLESS)

    async def shutdown(self) -> None:
        """Останавливает браузер и Playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Playwright остановлен")

    async def new_context(self, user_agent: Optional[str] = None) -> BrowserContext:
        """Создаёт новый изолированный браузерный контекст."""
        if not self._browser:
            raise RuntimeError("Браузер не запущен — вызовите startup() сначала")

        ua = user_agent or random.choice(USER_AGENTS)
        ctx = await self._browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True,
        )
        # Маскируем webdriver
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        async with self._lock:
            self.active_count += 1
        return ctx

    async def close_context(self, context: BrowserContext) -> None:
        """Закрывает браузерный контекст."""
        try:
            await context.close()
        except Exception:
            pass
        finally:
            async with self._lock:
                self.active_count = max(0, self.active_count - 1)


# Глобальный пул браузеров (инициализируется при старте)
browser_pool = BrowserPool()


class RobotsChecker:
    """Проверяет доступность URL по robots.txt."""

    def __init__(self) -> None:
        self._cache: dict[str, object] = {}

    async def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """
        Возвращает True если URL разрешён для краулинга по robots.txt.
        При ошибках загрузки robots.txt — разрешает (fail open).
        """
        if not settings.RESPECT_ROBOTS_TXT:
            return True

        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        if base not in self._cache:
            robots_url = f"{base}/robots.txt"
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        robots_url,
                        headers={"User-Agent": user_agent},
                        follow_redirects=True,
                    )
                    if resp.status_code == 200:
                        try:
                            from robotexclusionrulesparser import RobotExclusionRulesParser
                            parser = RobotExclusionRulesParser()
                            parser.parse(resp.text)
                            self._cache[base] = parser
                        except ImportError:
                            # Фоллбэк: простой парсер
                            self._cache[base] = _SimpleRobotsParser(resp.text)
                    else:
                        self._cache[base] = None  # Нет robots.txt → разрешаем
            except Exception as exc:
                logger.debug("Ошибка загрузки robots.txt для %s: %s", base, exc)
                self._cache[base] = None

        parser = self._cache.get(base)
        if parser is None:
            return True

        try:
            if hasattr(parser, "is_allowed"):
                return parser.is_allowed(user_agent, url)
            elif hasattr(parser, "can_fetch"):
                return parser.can_fetch(user_agent, url)
        except Exception:
            pass
        return True


class _SimpleRobotsParser:
    """Простой парсер robots.txt без внешних зависимостей."""

    def __init__(self, content: str) -> None:
        self._disallow: list[str] = []
        self._parse(content)

    def _parse(self, content: str) -> None:
        current_agent_applies = False
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "user-agent":
                current_agent_applies = val in ("*", "ContactParser")
            elif key == "disallow" and current_agent_applies and val:
                self._disallow.append(val)

    def is_allowed(self, user_agent: str, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path or "/"
        for disallow in self._disallow:
            if path.startswith(disallow):
                return False
        return True


class SiteCrawler:
    """
    Краулер для одного сайта.
    Находит релевантные страницы и возвращает их HTML-контент с языком.
    """

    def __init__(self, cancel_event: Optional[Event] = None) -> None:
        self._cancel_event = cancel_event or Event()
        self._robots = RobotsChecker()
        self._visited: set[str] = set()

    async def crawl_site(self, start_url: str) -> list[tuple[str, str, str]]:
        """
        Краулит сайт начиная с start_url.
        Возвращает список кортежей (url, html, language).
        """
        start_url = _normalize_url(start_url)
        results: list[tuple[str, str, str]] = []

        context = await browser_pool.new_context()
        try:
            # 1. Краулим главную страницу
            main_html, main_lang = await self._fetch_page(context, start_url)
            if main_html:
                results.append((start_url, main_html, main_lang))
                self._visited.add(start_url)

            # 2. Находим ссылки на страницы с контактами
            if main_html:
                contact_urls = self._find_contact_page_links(
                    main_html, start_url
                )
                logger.debug(
                    "Найдено %d потенциальных страниц контактов на %s",
                    len(contact_urls),
                    start_url,
                )

                # 3. Краулим найденные страницы
                for url in contact_urls:
                    if self._cancel_event.is_set():
                        break
                    if len(results) >= settings.MAX_PAGES_PER_SITE:
                        break
                    if url in self._visited:
                        continue

                    # Пауза между запросами
                    delay = random.uniform(
                        settings.REQUEST_DELAY_MIN,
                        settings.REQUEST_DELAY_MAX,
                    )
                    await asyncio.sleep(delay)

                    # Проверяем robots.txt
                    if not await self._robots.can_fetch(url):
                        logger.info("robots.txt запрещает: %s", url)
                        continue

                    html, lang = await self._fetch_page(context, url)
                    if html:
                        results.append((url, html, lang))
                        self._visited.add(url)

                        # Если нашли страницу с «Руководство» — ищем ещё вглубь
                        sub_urls = self._find_contact_page_links(html, url)
                        for sub_url in sub_urls:
                            if sub_url not in self._visited and sub_url not in contact_urls:
                                contact_urls.append(sub_url)

        finally:
            await browser_pool.close_context(context)

        logger.info(
            "Сайт %s: просмотрено %d страниц",
            start_url,
            len(results),
        )
        return results

    async def _fetch_page(
        self,
        context: BrowserContext,
        url: str,
    ) -> tuple[str, str]:
        """
        Загружает страницу через Playwright.
        Возвращает (html, language). При ошибке — ("", "unknown").
        """
        page: Optional[Page] = None
        try:
            page = await context.new_page()

            # Блокируем медиа и рекламу для ускорения
            await page.route(
                re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|ico|woff|woff2|ttf|mp4|mp3)(\?.*)?$", re.I),
                lambda route: route.abort(),
            )
            await page.route(
                re.compile(r"(google-analytics|googletagmanager|facebook\.com/tr|doubleclick|yandex\.ru/metrika)", re.I),
                lambda route: route.abort(),
            )

            # Загружаем страницу
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=settings.PAGE_TIMEOUT,
            )

            if response is None:
                logger.warning("Нет ответа для %s", url)
                return "", "unknown"

            status = response.status
            if status == 403:
                logger.warning("403 Forbidden: %s", url)
                return "", "unknown"
            elif status == 404:
                logger.debug("404 Not Found: %s", url)
                return "", "unknown"
            elif status == 429:
                logger.warning("429 Too Many Requests: %s — делаем паузу", url)
                await asyncio.sleep(random.uniform(10, 20))
                return "", "unknown"
            elif status >= 500:
                logger.warning("HTTP %d для %s", status, url)
                return "", "unknown"

            # Ждём дополнительного рендеринга JS (для SPA)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                pass  # Продолжаем с тем, что есть

            # Получаем HTML
            html = await page.content()

            # Проверяем на CAPTCHA
            if CAPTCHA_PATTERNS.search(html[:5000]):
                logger.warning("CAPTCHA обнаружена на %s — пропускаем", url)
                return "", "unknown"

            # Определяем язык
            lang = await self._detect_language(page, html)

            return html, lang

        except PlaywrightTimeoutError:
            logger.warning("Тайм-аут загрузки %s (>%dмс)", url, settings.PAGE_TIMEOUT)
            return "", "unknown"
        except PlaywrightError as exc:
            err_msg = str(exc).lower()
            if "net::err_name_not_resolved" in err_msg:
                logger.info("DNS не разрешён: %s", url)
            elif "net::err_connection_refused" in err_msg:
                logger.info("Соединение отклонено: %s", url)
            elif "net::err_connection_timed_out" in err_msg:
                logger.warning("Тайм-аут соединения: %s", url)
            else:
                logger.warning("Playwright ошибка для %s: %s", url, exc)
            return "", "unknown"
        except Exception as exc:
            logger.error("Ошибка загрузки %s: %s", url, exc)
            return "", "unknown"
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    @staticmethod
    async def _detect_language(page: Page, html: str) -> str:
        """Определяет язык страницы по html[lang] или мета-тегу."""
        try:
            lang_attr = await page.evaluate(
                "document.documentElement.getAttribute('lang') || "
                "document.querySelector('meta[http-equiv=\"Content-Language\"]')?.getAttribute('content') || "
                "document.querySelector('meta[name=\"language\"]')?.getAttribute('content') || ''"
            )
            if lang_attr:
                return lang_attr.lower()[:2]
        except Exception:
            pass

        # Фоллбэк: ищем lang в теге <html>
        match = re.search(r'<html[^>]+lang=["\']([^"\']+)["\']', html[:500], re.I)
        if match:
            return match.group(1).lower()[:2]

        return "unknown"

    def _find_contact_page_links(self, html: str, base_url: str) -> list[str]:
        """
        Находит ссылки на страницы с контактами и сведениями о руководстве.
        Возвращает список нормализованных URL.
        """
        from bs4 import BeautifulSoup

        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.lower()

        soup = BeautifulSoup(html, "lxml")
        found: list[str] = []
        seen: set[str] = set()

        for tag in soup.find_all("a", href=True):
            href = tag.get("href", "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            # Полный URL
            try:
                full_url = urljoin(base_url, href)
                normalized = _normalize_url(full_url)
            except Exception:
                continue

            # Только тот же домен
            parsed = urlparse(normalized)
            link_domain = parsed.netloc.lower()
            if not _same_domain(base_domain, link_domain):
                continue

            # Пропускаем статические файлы
            if SKIP_EXTENSIONS.search(parsed.path):
                continue

            if normalized in seen or normalized in self._visited:
                continue

            # Проверяем текст ссылки и URL на ключевые слова
            link_text = (tag.get_text(separator=" ") or "").lower()
            link_url_lower = normalized.lower()

            is_relevant = False
            for keyword in CONTACT_PAGE_KEYWORDS:
                if keyword in link_text or keyword.replace(" ", "-") in link_url_lower or keyword.replace(" ", "_") in link_url_lower:
                    is_relevant = True
                    break

            # Также проверяем title атрибут
            title = (tag.get("title", "") or "").lower()
            if not is_relevant:
                for keyword in CONTACT_PAGE_KEYWORDS:
                    if keyword in title:
                        is_relevant = True
                        break

            if is_relevant:
                found.append(normalized)
                seen.add(normalized)

        # Сортируем: приоритет более коротким URL (обычно важнее)
        found.sort(key=lambda u: len(u))
        return found


# ── Вспомогательные функции ────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """
    Нормализует URL:
    - Добавляет схему https:// если отсутствует
    - Убирает trailing slash (кроме корня)
    - Нормализует регистр хоста
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    # Нормализуем хост
    netloc = parsed.netloc.lower()

    # Нормализуем путь
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunparse((
        parsed.scheme,
        netloc,
        path,
        parsed.params,
        parsed.query,
        "",  # Убираем fragment
    ))
    return normalized


def _same_domain(base: str, target: str) -> bool:
    """
    Проверяет принадлежность к одному домену.
    Учитывает поддомены (target может быть поддоменом base).
    """
    if not base or not target:
        return False
    # Убираем www
    b = base.lstrip("www.")
    t = target.lstrip("www.")
    return t == b or t.endswith(f".{b}")
