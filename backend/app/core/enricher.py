"""
Модуль обогащения данных — дозаполнение ИНН/КПП и должностей.
Работает ПОСЛЕ извлечения и ПЕРЕД нормализацией.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from app.config import settings
from app.models import ContactRecord

logger = logging.getLogger(__name__)

# Паттерн ИНН с контекстом
RE_INN_CONTEXT = re.compile(
    r"(?:ИНН|инн|INN)[:\s]*(\d{10}|\d{12})", re.I
)
RE_KPP_CONTEXT = re.compile(
    r"(?:КПП|кпп|KPP)[:\s]*(\d{9})", re.I
)


class DataEnricher:
    """Обогащает извлечённые контакты дополнительными данными."""

    def __init__(self) -> None:
        self._llm = None
        self._inn_cache: dict[str, tuple[Optional[str], Optional[str]]] = {}

    def _get_llm(self):
        """Ленивая инициализация LLM."""
        if self._llm is None:
            try:
                from app.core.llm_client import LLMClient
                client = LLMClient()
                if client.is_available:
                    self._llm = client
            except Exception as exc:
                logger.debug("LLM недоступен для обогащения: %s", exc)
        return self._llm

    async def enrich(
        self,
        results: list[dict[str, Any]],
        page_texts: Optional[dict[str, str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Обогащает результаты:
        1. Ищет ИНН/КПП в текстах страниц
        2. Заполняет ИНН/КПП на все контакты компании
        3. Пытается дозаполнить через LLM если доступен
        """
        page_texts = page_texts or {}

        for site_result in results:
            site_url = site_result.get("site_url", "")
            company_name = site_result.get("company_name", "")
            contacts: list[ContactRecord] = site_result.get("contacts", [])

            if not contacts:
                continue

            # ── 1. Ищем ИНН/КПП в текстах страниц ──
            found_inn = None
            found_kpp = None

            # Сначала из контактов (может уже быть)
            for c in contacts:
                if c.inn and not found_inn:
                    found_inn = c.inn
                if c.kpp and not found_kpp:
                    found_kpp = c.kpp

            # Из текстов страниц
            if not found_inn:
                for url, text in page_texts.items():
                    if site_url and site_url.split("//")[-1].split("/")[0] in url:
                        m = RE_INN_CONTEXT.search(text)
                        if m:
                            found_inn = m.group(1)
                            logger.info("Найден ИНН %s для %s на %s", found_inn, company_name, url)
                            break

            if not found_kpp:
                for url, text in page_texts.items():
                    if site_url and site_url.split("//")[-1].split("/")[0] in url:
                        m = RE_KPP_CONTEXT.search(text)
                        if m:
                            found_kpp = m.group(1)
                            logger.info("Найден КПП %s для %s на %s", found_kpp, company_name, url)
                            break

            # ── 2. Пробуем LLM для ИНН если не нашли ──
            if not found_inn and company_name:
                found_inn, found_kpp_llm = await self._lookup_inn_llm(company_name)
                if not found_kpp and found_kpp_llm:
                    found_kpp = found_kpp_llm

            # ── 3. Заполняем ИНН/КПП на всех контактах ──
            if found_inn:
                for c in contacts:
                    if not c.inn:
                        c.inn = found_inn
            if found_kpp:
                for c in contacts:
                    if not c.kpp:
                        c.kpp = found_kpp

            # ── 4. Заполняем company_email если не найден ──
            company_email = None
            for c in contacts:
                if c.company_email:
                    company_email = c.company_email
                    break
            if company_email:
                for c in contacts:
                    if not c.company_email:
                        c.company_email = company_email

        return results

    async def _lookup_inn_llm(
        self, company_name: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Запрашивает ИНН/КПП через LLM."""
        cache_key = company_name.lower().strip()
        if cache_key in self._inn_cache:
            return self._inn_cache[cache_key]

        llm = self._get_llm()
        if not llm:
            return None, None

        try:
            prompt = (
                f"Какой ИНН и КПП у российской компании «{company_name}»? "
                f"Ответь ТОЛЬКО в формате JSON: "
                f'{{ "inn": "1234567890", "kpp": "123456789" }}. '
                f"Если не знаешь — верни null."
            )

            result = await llm.extract_contacts(
                text=prompt,
                page_url="enrichment",
                target_positions=None,
            )

            inn = result.get("inn")
            kpp = result.get("kpp")

            # Валидация
            if inn and re.match(r"^\d{10}$|^\d{12}$", str(inn)):
                inn = str(inn)
            else:
                inn = None

            if kpp and re.match(r"^\d{9}$", str(kpp)):
                kpp = str(kpp)
            else:
                kpp = None

            self._inn_cache[cache_key] = (inn, kpp)
            if inn:
                logger.info("LLM: найден ИНН %s для %s", inn, company_name)
            return inn, kpp

        except Exception as exc:
            logger.debug("LLM обогащение ИНН не удалось для %s: %s", company_name, exc)
            self._inn_cache[cache_key] = (None, None)
            return None, None
