"""
Модуль извлечения контактных данных из HTML-страниц.
Вариант A (классический): регулярные выражения + DOM-анализ.
Вариант B (AI): вызовы LLM с автоматическим фоллбэком на Вариант A.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from app.config import settings
from app.models import (
    ContactRecord,
    ExtractionVariant,
    FallbackReason,
    ParseMode,
    SocialLinks,
)

logger = logging.getLogger(__name__)

# ── Пути к словарям ───────────────────────────────────────────────────────────────────
_DICT_DIR = Path(__file__).parent.parent / "dictionaries"


def _load_json(filename: str) -> Any:
    path = _DICT_DIR / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ── Регулярные выражения ────────────────────────────────────────────────────────────

# Email: стандартный паттерн RFC 5322 упрощённый
RE_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.I,
)

# Телефоны: российские и международные форматы
RE_PHONE = re.compile(
    r"""
    (?:
        (?:\+7|8|7)          # Российский префикс
        [\s\-\(\.]*
        (?:\d{3}|\(\d{3}\))  # Код города/оператора
        [\s\-\)\.]*
        \d{3}
        [\s\-\.]*
        \d{2}
        [\s\-\.]*
        \d{2}
    )
    |
    (?:
        \+\d{1,3}            # Международный
        [\s\-\(\.]*
        \d{2,4}
        [\s\-\)\.]*
        \d{3,4}
        [\s\-\.]*
        \d{3,4}
    )
    """,
    re.VERBOSE,
)

# ИНН: 10 или 12 цифр (с контекстом для снижения ложных срабатываний)
RE_INN = re.compile(
    r"""
    (?:
        (?:ИНН|инн|inn|INN)  # Явный контекст
        [\s:№\-]*
        (\d{10}|\d{12})      # Значение
    )
    |
    (?<!\d)(\d{10}|\d{12})(?!\d)  # Изолированное число
    """,
    re.VERBOSE | re.I,
)

# КПП: 9 цифр (с контекстом)
RE_KPP = re.compile(
    r"""
    (?:
        (?:КПП|кпп|kpp|KPP)
        [\s:№\-]*
        (\d{9})
    )
    |
    (?<!\d)(\d{9})(?!\d)
    """,
    re.VERBOSE | re.I,
)

# ФИО: три компонента с большой буквы (русские)
RE_FIO_RU = re.compile(
    r"""
    \b
    ([\u0410-\u042f\u0401][\u0430-\u044f\u0451]+(?:-[\u0410-\u042f\u0401][\u0430-\u044f\u0451]+)?)   # Фамилия
    \s+
    ([\u0410-\u042f\u0401][\u0430-\u044f\u0451]+)                         # Имя
    \s+
    ([\u0410-\u042f\u0401][\u0430-\u044f\u0451]*(?:вич|вна|ич|на|евна|евич|ович|овна|ич|ина|\u044cич|\u044cевна)\b)  # Отчество
    """,
    re.VERBOSE,
)

# Инициалы + фамилия: И.О. Фамилия
RE_FIO_INITIALS = re.compile(
    r"""
    \b
    ([\u0410-\u042f\u0401]\.)         # Инициал имени
    ([\u0410-\u042f\u0401]\.)         # Инициал отчества
    \s*
    ([\u0410-\u042f\u0401][\u0430-\u044f\u0451]+)   # Фамилия
    \b
    """,
    re.VERBOSE,
)

# Социальные сети
RE_SOCIAL = {
    "vk": re.compile(r"(?:https?://)?(?:www\.)?vk\.com/[^\s\"'<>]+", re.I),
    "telegram": re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/[^\s\"'<>]+", re.I),
    "linkedin": re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/[^\s\"'<>]+", re.I),
    "facebook": re.compile(r"(?:https?://)?(?:www\.)?facebook\.com/[^\s\"'<>]+", re.I),
    "instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/[^\s\"'<>]+", re.I),
    "twitter": re.compile(r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[^\s\"'<>]+", re.I),
    "youtube": re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/(?:channel|user|c)/[^\s\"'<>]+", re.I),
    "ok": re.compile(r"(?:https?://)?(?:www\.)?ok\.ru/[^\s\"'<>]+", re.I),
}


class ContactExtractor:
    """
    Извлекает контактные данные из HTML-страниц.
    Поддерживает два варианта: классический (A) и AI (B).
    """

    def __init__(
        self,
        variant: ExtractionVariant = ExtractionVariant.CLASSIC,
        target_positions: Optional[list[str]] = None,
        mode: ParseMode = ParseMode.SITES_ALL_POSITIONS,
    ) -> None:
        self._variant = variant
        self._target_positions = target_positions or []
        self._mode = mode

        # Загружаем словари должностей
        self._positions_ru: dict = _load_json("positions_ru.json")
        self._positions_en: dict = _load_json("positions_en.json")

        # Все нормализованные должности для fuzzy-поиска
        self._all_positions: list[str] = (
            list(self._positions_ru.keys()) + list(self._positions_en.keys())
        )

        # LLM клиент (ленивая инициализация)
        self._llm: Optional[Any] = None

        # Счётчики
        self.tokens_used: int = 0
        self.fallback_count: int = 0
        self._fallback_log: list[dict] = []

    def _get_llm(self):
        """Ленивая инициализация LLM-клиента."""
        if self._llm is None:
            from app.core.llm_client import LLMClient
            self._llm = LLMClient()
        return self._llm

    async def extract(
        self,
        html: str,
        page_url: str,
        site_url: str,
        company_name: Optional[str] = None,
        inn: Optional[str] = None,
        language: str = "unknown",
    ) -> list[ContactRecord]:
        """
        Извлекает контактные данные из HTML страницы.
        Выбирает вариант A или B в зависимости от конфигурации.
        Возвращает список ContactRecord.
        """
        if not html:
            return []

        if self._variant == ExtractionVariant.AI:
            try:
                return await self._extract_with_llm(
                    html=html,
                    page_url=page_url,
                    site_url=site_url,
                    company_name=company_name,
                    inn=inn,
                    language=language,
                )
            except Exception as exc:
                from app.core.llm_client import LLMClientError
                if isinstance(exc, LLMClientError):
                    reason = exc.reason
                else:
                    reason = FallbackReason.LLM_UNAVAILABLE

                self.fallback_count += 1
                self._fallback_log.append({
                    "url": page_url,
                    "reason": reason.value,
                    "error": str(exc),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                logger.warning(
                    "Фоллбэк на Вариант A для %s (причина: %s): %s",
                    page_url,
                    reason.value,
                    exc,
                )
                # Фоллбэк на классический вариант
                return self._extract_classic(
                    html=html,
                    page_url=page_url,
                    site_url=site_url,
                    company_name=company_name,
                    inn=inn,
                    language=language,
                    variant=ExtractionVariant.CLASSIC,
                )
        else:
            return self._extract_classic(
                html=html,
                page_url=page_url,
                site_url=site_url,
                company_name=company_name,
                inn=inn,
                language=language,
            )

    # ── Вариант A: Классическое извлечение ────────────────────────────────────────────────

    def _extract_classic(
        self,
        html: str,
        page_url: str,
        site_url: str,
        company_name: Optional[str],
        inn: Optional[str],
        language: str,
        variant: ExtractionVariant = ExtractionVariant.CLASSIC,
    ) -> list[ContactRecord]:
        """Классическое извлечение через DOM + регулярные выражения."""
        soup = BeautifulSoup(html, "lxml")

        # Убираем нежелательные теги
        for tag in soup.find_all(["script", "style", "noscript", "head"]):
            tag.decompose()

        full_text = soup.get_text(separator=" ", strip=True)

        # Извлекаем метаданные компании
        detected_company = company_name or self._extract_company_name(soup)
        detected_inn = inn or self._extract_inn_from_text(full_text)
        detected_kpp = self._extract_kpp_from_text(full_text)
        company_email = self._extract_company_email(full_text, site_url)
        social_links_global = self._extract_social_links(html)

        # Ищем блоки с персонами (карточки сотрудников)
        person_blocks = self._find_person_blocks(soup)

        contacts: list[ContactRecord] = []

        if person_blocks:
            for block in person_blocks:
                block_text = block.get_text(separator=" ", strip=True)
                block_html = str(block)

                fio = self._extract_fio(block_text)
                if not fio:
                    continue

                position_raw = self._extract_position_from_block(block)
                position_normalized = self._normalize_position(position_raw) if position_raw else None

                # Фильтр по целевым должностям (режим 1)
                if (
                    self._mode == ParseMode.SITES_WITH_TARGET_POSITIONS
                    and self._target_positions
                    and not self._position_matches_targets(position_raw or "", position_normalized or "")
                ):
                    continue

                emails = RE_EMAIL.findall(block_html)
                personal_email = next(
                    (e for e in emails if not self._is_company_email(e, site_url)),
                    None,
                )

                phones = self._extract_phones(block_text)
                phone_raw = phones[0] if phones else None
                phone_normalized = self._normalize_phone(phone_raw) if phone_raw else None

                block_social = self._extract_social_links(block_html)

                contacts.append(ContactRecord(
                    company_name=detected_company,
                    site_url=site_url,
                    inn=detected_inn,
                    kpp=detected_kpp,
                    company_email=company_email,
                    position_raw=position_raw,
                    position_normalized=position_normalized,
                    full_name=fio,
                    personal_email=personal_email,
                    phone=phone_normalized,
                    phone_raw=phone_raw,
                    social_links=block_social,
                    source_url=page_url,
                    page_language=language,
                    status="ok",
                    extraction_variant=variant,
                ))

        # Если блоки не найдены — извлекаем из всего текста
        if not contacts:
            all_fios = self._extract_all_fios(full_text)
            all_emails = RE_EMAIL.findall(full_text)
            all_phones = self._extract_phones(full_text)

            for i, fio in enumerate(all_fios[:20]):  # Ограничиваем 20 персонами
                position_raw = self._extract_position_near_fio(full_text, fio)
                position_normalized = self._normalize_position(position_raw) if position_raw else None

                if (
                    self._mode == ParseMode.SITES_WITH_TARGET_POSITIONS
                    and self._target_positions
                    and not self._position_matches_targets(position_raw or "", position_normalized or "")
                ):
                    continue

                personal_email = all_emails[i] if i < len(all_emails) else None
                phone_raw = all_phones[i] if i < len(all_phones) else None
                phone_normalized = self._normalize_phone(phone_raw) if phone_raw else None

                contacts.append(ContactRecord(
                    company_name=detected_company,
                    site_url=site_url,
                    inn=detected_inn,
                    kpp=detected_kpp,
                    company_email=company_email,
                    position_raw=position_raw,
                    position_normalized=position_normalized,
                    full_name=fio,
                    personal_email=personal_email,
                    phone=phone_normalized,
                    phone_raw=phone_raw,
                    social_links=social_links_global,
                    source_url=page_url,
                    page_language=language,
                    status="ok",
                    extraction_variant=variant,
                ))

        return contacts

    # ── Вариант B: AI-извлечение ────────────────────────────────────────────────────

    async def _extract_with_llm(
        self,
        html: str,
        page_url: str,
        site_url: str,
        company_name: Optional[str],
        inn: Optional[str],
        language: str,
    ) -> list[ContactRecord]:
        """Извлечение контактов с помощью LLM."""
        llm = self._get_llm()

        if not llm.is_available:
            from app.core.llm_client import LLMClientError
            raise LLMClientError(
                "LLM недоступен (не настроен или бюджет исчерпан)",
                FallbackReason.LLM_UNAVAILABLE,
            )

        # Готовим текст: убираем HTML-разметку
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all(["script", "style", "noscript"]):
            tag.decompose()
        clean_text = soup.get_text(separator="\n", strip=True)

        # Вызываем LLM
        result = await llm.extract_contacts(
            text=clean_text,
            page_url=page_url,
            target_positions=self._target_positions or None,
        )
        self.tokens_used = llm.tokens_used

        # Парсим ответ LLM в ContactRecord
        contacts: list[ContactRecord] = []
        detected_company = result.get("company_name") or company_name
        detected_inn = result.get("inn") or inn
        detected_kpp = result.get("kpp")
        company_email = result.get("company_email")

        for item in result.get("contacts", []):
            if not isinstance(item, dict):
                continue

            fio = item.get("full_name")
            if not fio:
                continue

            position_raw = item.get("position_raw")
            position_normalized = self._normalize_position(position_raw) if position_raw else None

            # Фильтр по целевым должностям (режим 1)
            if (
                self._mode == ParseMode.SITES_WITH_TARGET_POSITIONS
                and self._target_positions
                and not self._position_matches_targets(position_raw or "", position_normalized or "")
            ):
                continue

            phone_raw = item.get("phone")
            phone_normalized = self._normalize_phone(phone_raw) if phone_raw else None

            social_data = item.get("social_links", {}) or {}
            social_links = SocialLinks(
                vk=social_data.get("vk"),
                telegram=social_data.get("telegram"),
                linkedin=social_data.get("linkedin"),
                facebook=social_data.get("facebook"),
                instagram=social_data.get("instagram"),
                twitter=social_data.get("twitter"),
            )

            contacts.append(ContactRecord(
                company_name=detected_company,
                site_url=site_url,
                inn=detected_inn,
                kpp=detected_kpp,
                company_email=company_email,
                position_raw=position_raw,
                position_normalized=position_normalized,
                full_name=fio,
                personal_email=item.get("personal_email"),
                phone=phone_normalized,
                phone_raw=phone_raw,
                social_links=social_links,
                source_url=page_url,
                page_language=language,
                status="ok",
                extraction_variant=ExtractionVariant.AI,
            ))

        return contacts

    # ── Вспомогательные методы извлечения ──────────────────────────────────────────────

    @staticmethod
    def _extract_company_name(soup: BeautifulSoup) -> Optional[str]:
        """Извлекает название компании из метатегов и заголовков страницы."""
        # og:site_name
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            return str(og_site["content"]).strip()

        # og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return str(og_title["content"]).strip().split("|")[0].strip()

        # <title>
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Берём первую часть до разделителя
            for sep in ("|", "—", "-", "–", ":"):
                if sep in title:
                    return title.split(sep)[0].strip()
            return title[:80]

        # Заголовок h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)[:80]

        return None

    @staticmethod
    def _extract_inn_from_text(text: str) -> Optional[str]:
        """Ищет ИНН в тексте с приоритетом явного контекста."""
        for m in RE_INN.finditer(text):
            val = m.group(1) or m.group(2)
            if val and len(val) in (10, 12):
                return val
        return None

    @staticmethod
    def _extract_kpp_from_text(text: str) -> Optional[str]:
        """Ищет КПП в тексте."""
        for m in RE_KPP.finditer(text):
            val = m.group(1) or m.group(2)
            if val:
                return val
        return None

    @staticmethod
    def _extract_company_email(text: str, site_url: str) -> Optional[str]:
        """Извлекает общий email компании."""
        from urllib.parse import urlparse
        domain = urlparse(site_url).netloc.lower().lstrip("www.")

        emails = RE_EMAIL.findall(text)
        # Приоритет: email на домене компании
        for email in emails:
            if domain and domain in email.lower():
                return email.lower()
        # Общие email (info@, contact@, mail@, office@)
        for email in emails:
            lower = email.lower()
            if any(lower.startswith(p) for p in ("info@", "contact@", "mail@", "office@", "hello@", "support@", "admin@", "help@")):
                return lower
        return emails[0] if emails else None

    @staticmethod
    def _is_company_email(email: str, site_url: str) -> bool:
        """Проверяет, является ли email общим корпоративным."""
        from urllib.parse import urlparse
        domain = urlparse(site_url).netloc.lower().lstrip("www.")
        lower = email.lower()
        general_prefixes = ("info@", "contact@", "mail@", "office@", "hello@", "support@", "admin@", "post@", "noreply@")
        return (domain and domain in lower) or any(lower.startswith(p) for p in general_prefixes)

    @staticmethod
    def _extract_phones(text: str) -> list[str]:
        """Извлекает все телефонные номера из текста."""
        phones = RE_PHONE.findall(text)
        return [" ".join(p.split()) for p in phones if p.strip()]

    @staticmethod
    def _normalize_phone(raw: Optional[str]) -> Optional[str]:
        """Нормализует телефонный номер в формат E.164."""
        if not raw:
            return None
        try:
            import phonenumbers
            cleaned = re.sub(r"[^\d+]", "", raw)
            if cleaned.startswith("8") and len(cleaned) == 11:
                cleaned = "+7" + cleaned[1:]
            elif cleaned.startswith("7") and len(cleaned) == 11:
                cleaned = "+" + cleaned

            parsed = phonenumbers.parse(cleaned, "RU")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed,
                    phonenumbers.PhoneNumberFormat.E164,
                )
        except Exception:
            pass
        cleaned = re.sub(r"[^\d+\-\(\)\s]", "", raw).strip()
        return cleaned if cleaned else None

    @staticmethod
    def _extract_fio(text: str) -> Optional[str]:
        """Извлекает первое ФИО из текста."""
        match = RE_FIO_RU.search(text)
        if match:
            return f"{match.group(1)} {match.group(2)} {match.group(3)}"

        match = RE_FIO_INITIALS.search(text)
        if match:
            return f"{match.group(1)}{match.group(2)} {match.group(3)}"

        return None

    @staticmethod
    def _extract_all_fios(text: str) -> list[str]:
        """Извлекает все ФИО из текста."""
        results = []
        seen: set[str] = set()

        for m in RE_FIO_RU.finditer(text):
            fio = f"{m.group(1)} {m.group(2)} {m.group(3)}"
            if fio not in seen:
                seen.add(fio)
                results.append(fio)

        for m in RE_FIO_INITIALS.finditer(text):
            fio = f"{m.group(1)}{m.group(2)} {m.group(3)}"
            if fio not in seen:
                seen.add(fio)
                results.append(fio)

        return results

    @staticmethod
    def _extract_position_near_fio(text: str, fio: str) -> Optional[str]:
        """Ищет должность рядом с ФИО в тексте."""
        idx = text.find(fio)
        if idx == -1:
            return None

        context_start = max(0, idx - 200)
        context_end = min(len(text), idx + len(fio) + 200)
        context = text[context_start:context_end]

        pos_patterns = [
            r"(Генеральный директор|Директор|Заместитель|Главный \w+|Руководитель|Начальник|Председатель|Президент|Вице-президент|Технический директор|Финансовый директор|Исполнительный директор|CEO|CTO|CFO|COO|VP|Head of|Director of|Manager)",
            r"([\u0410-\u042f\u0401][\u0430-\u044f\u0451]+ директор|[\u0410-\u042f\u0401][\u0430-\u044f\u0451]+ руководитель|[\u0410-\u042f\u0401][\u0430-\u044f\u0451]+ менеджер)",
        ]
        for pattern in pos_patterns:
            m = re.search(pattern, context, re.I)
            if m:
                return m.group(1).strip()

        return None

    def _normalize_position(self, position_raw: Optional[str]) -> Optional[str]:
        """
        Нормализует должность, сопоставляя со словарём через fuzzy-поиск.
        """
        if not position_raw or not position_raw.strip():
            return None

        position_lower = position_raw.strip().lower()

        # Точное совпадение
        for pos_dict in (self._positions_ru, self._positions_en):
            for key, val in pos_dict.items():
                if key.lower() == position_lower:
                    return val if isinstance(val, str) else key

        # Fuzzy-поиск
        try:
            from rapidfuzz import fuzz, process

            all_keys = list(self._positions_ru.keys()) + list(self._positions_en.keys())
            if not all_keys:
                return position_raw

            result = process.extractOne(
                position_lower,
                [k.lower() for k in all_keys],
                scorer=fuzz.token_sort_ratio,
                score_cutoff=75,
            )
            if result:
                best_key = all_keys[result[2]]
                normalized = (
                    self._positions_ru.get(best_key)
                    or self._positions_en.get(best_key)
                    or best_key
                )
                return normalized if isinstance(normalized, str) else best_key
        except ImportError:
            pass

        return position_raw

    def _position_matches_targets(
        self,
        position_raw: str,
        position_normalized: str,
    ) -> bool:
        """Проверяет, соответствует ли должность целевым должностям."""
        if not self._target_positions:
            return True

        combined = f"{position_raw} {position_normalized}".lower()

        for target in self._target_positions:
            target_lower = target.lower()
            if target_lower in combined:
                return True
            try:
                from rapidfuzz import fuzz
                if fuzz.partial_ratio(target_lower, combined) >= 70:
                    return True
            except ImportError:
                pass

        return False

    def _find_person_blocks(self, soup: BeautifulSoup) -> list[Tag]:
        """
        Находит блоки HTML с информацией о персонах.
        Ищет карточки сотрудников по структуре DOM.
        """
        blocks: list[Tag] = []

        # 1. Ищем типичные CSS-классы карточек
        card_patterns = re.compile(
            r"(person|employee|staff|team|member|manager|director|contact|"
            r"card|profile|bio|\u0447еловек|\u0441отрудник|\u0440уководитель|\u043fерсона|\u043aонтакт)",
            re.I,
        )

        for tag in soup.find_all(["div", "article", "section", "li"]):
            classes = " ".join(tag.get("class", []))
            tag_id = tag.get("id", "")
            if card_patterns.search(classes) or card_patterns.search(tag_id):
                text = tag.get_text(strip=True)
                if len(text) > 20 and RE_FIO_RU.search(text):
                    blocks.append(tag)

        if blocks:
            return blocks

        # 2. Структурный анализ: повторяющиеся блоки с ФИО
        for parent in soup.find_all(["ul", "div", "section"]):
            children = parent.find_all(["li", "div", "article"], recursive=False)
            if len(children) < 2:
                continue
            fio_children = [c for c in children if RE_FIO_RU.search(c.get_text())]
            if len(fio_children) >= 2:
                blocks.extend(fio_children)
                break

        return blocks

    @staticmethod
    def _extract_position_from_block(block: Tag) -> Optional[str]:
        """Извлекает должность из HTML-блока персоны."""
        pos_patterns = re.compile(
            r"(position|title|role|post|job|\u0434\u043e\u043b\u0436\u043d\u043e\u0441\u0442\u044c|\u0437\u0432\u0430\u043d\u0438\u0435|"
            r"subtitle|caption|function|occupation)",
            re.I,
        )

        for tag in block.find_all(["p", "span", "div", "h3", "h4", "small", "em", "strong"]):
            classes = " ".join(tag.get("class", []))
            if pos_patterns.search(classes):
                text = tag.get_text(strip=True)
                if text and 3 < len(text) < 100:
                    return text

        texts = [t.strip() for t in block.stripped_strings]
        for i, text in enumerate(texts):
            if RE_FIO_RU.search(text) and i + 1 < len(texts):
                next_text = texts[i + 1]
                if 3 < len(next_text) < 100 and not RE_EMAIL.match(next_text):
                    return next_text

        return None

    @staticmethod
    def _extract_social_links(html_or_text: str) -> SocialLinks:
        """Извлекает ссылки на социальные сети."""
        result: dict[str, Optional[str]] = {}
        for network, pattern in RE_SOCIAL.items():
            match = pattern.search(html_or_text)
            if match:
                url = match.group()
                if not url.startswith("http"):
                    url = "https://" + url
                result[network] = url
            else:
                result[network] = None
        return SocialLinks(**result)
