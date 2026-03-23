"""
Модуль пост-процессинга и нормализации извлечённых контактов.
Вызывается task_manager после извлечения и перед экспортом в Excel.

Выполняет:
- Валидацию и очистку каждого поля
- Удаление мусорных записей
- Классификацию email (личный vs общий)
- Валидацию должностей (исключение мусора)
- Валидацию ФИО (исключение не-персон)
- Дедупликацию
- Фильтрацию политиков и знаменитостей
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.models import ContactRecord

logger = logging.getLogger(__name__)

# ── Общие email-префиксы (НЕ личные email) ─────────────────────────────────
GENERIC_EMAIL_PREFIXES = frozenset({
    "info", "support", "help", "admin", "office", "pr", "secretary",
    "reception", "contact", "mail", "noreply", "sales", "marketing",
    "press", "media", "feedback", "webmaster", "postmaster", "abuse",
    "security", "careers", "jobs", "hr", "legal", "compliance",
    "billing", "finance", "accounting", "it", "tech", "dev", "api",
    "team", "hello", "general", "service", "inquiry", "request",
    "booking", "order", "subscribe", "unsubscribe", "newsletter",
    "post", "no-reply", "do-not-reply", "donotreply",
})

# ── Ключевые слова реальных должностей ──────────────────────────────────────
POSITION_KEYWORDS = {
    # Русские
    "директор", "менеджер", "начальник", "руководитель", "специалист",
    "инженер", "бухгалтер", "экономист", "юрист", "аналитик",
    "координатор", "администратор", "секретарь", "ассистент",
    "консультант", "заведующий", "председатель", "президент",
    "вице-президент", "заместитель", "главный", "старший", "младший",
    "ведущий", "главбух", "технолог", "программист", "разработчик",
    "дизайнер", "маркетолог", "логист", "оператор", "диспетчер",
    "мастер", "механик", "электрик", "водитель", "охранник",
    "продавец", "кассир", "товаровед", "агент", "представитель",
    "партнёр", "учредитель", "основатель", "совладелец", "акционер",
    "советник", "эксперт", "исследователь", "доцент", "профессор",
    "врач", "доктор", "архитектор", "аудитор", "контролёр",
    "супервайзер", "стажёр", "куратор", "редактор", "корреспондент",
    "переводчик", "методист",
    # Английские
    "director", "manager", "head", "chief", "officer", "president",
    "vice president", "vp", "ceo", "cto", "cfo", "coo", "cmo", "cio",
    "lead", "senior", "junior", "engineer", "developer", "designer",
    "analyst", "consultant", "coordinator", "specialist", "assistant",
    "secretary", "accountant", "lawyer", "advisor", "partner",
    "founder", "co-founder", "owner", "chairman", "board member",
    "architect", "auditor", "supervisor", "intern",
}

# ── Организационные термины (НЕ имена людей) ───────────────────────────────
ORG_KEYWORDS = {
    "компания", "отдел", "управление", "департамент", "служба",
    "филиал", "представительство", "группа", "холдинг", "корпорация",
    "общество", "фонд", "ассоциация", "союз", "институт",
    "министерство", "правительство", "администрация", "комитет",
    "агентство", "бюро", "центр", "лаборатория", "предприятие",
}

# ── Известные политики / знаменитости (НЕ сотрудники компаний) ──────────────
BLACKLISTED_PERSONS = {
    "путин", "медведев", "мишустин", "лавров", "шойгу",
    "навальный", "зеленский", "байден", "трамп", "макрон",
    "си цзиньпин", "меркель", "обама", "клинтон", "собянин",
    "матвиенко", "володин", "набиуллина", "силуанов", "патрушев",
}


def normalize_contacts(contacts: list[ContactRecord]) -> list[ContactRecord]:
    """
    Основная функция нормализации.
    Валидирует, очищает и дедуплицирует список контактов.
    Вызывается после извлечения и перед экспортом в Excel.

    Args:
        contacts: Список извлечённых контактов.

    Returns:
        Очищенный и валидированный список контактов.
    """
    if not contacts:
        return []

    validated: list[ContactRecord] = []
    rejected_count = 0

    for contact in contacts:
        # 1. Валидация ФИО
        if not _validate_full_name(contact.full_name):
            logger.debug("Нормализатор: отклонено ФИО '%s'", contact.full_name)
            rejected_count += 1
            continue

        # 2. Очистка и нормализация ФИО
        contact.full_name = _clean_full_name(contact.full_name)

        # 3. Валидация и очистка должности
        contact.position_raw = _validate_position(contact.position_raw)
        if not contact.position_raw:
            contact.position_normalized = None

        # 4. Валидация личного email
        if contact.personal_email:
            if _is_generic_email(contact.personal_email):
                # Перемещаем общий email в company_email
                if not contact.company_email:
                    contact.company_email = contact.personal_email.lower()
                contact.personal_email = None
                logger.debug(
                    "Нормализатор: переместил общий email '%s' из личного в компанию для '%s'",
                    contact.company_email, contact.full_name,
                )
            else:
                contact.personal_email = contact.personal_email.lower().strip()

        # 5. Нормализация company_email
        if contact.company_email:
            contact.company_email = contact.company_email.lower().strip()

        # 6. Валидация ИНН
        if contact.inn:
            digits = re.sub(r"\D", "", contact.inn)
            if len(digits) in (10, 12):
                contact.inn = digits
            else:
                contact.inn = None

        # 7. Валидация КПП
        if contact.kpp:
            digits = re.sub(r"\D", "", contact.kpp)
            if len(digits) == 9:
                contact.kpp = digits
            else:
                contact.kpp = None

        validated.append(contact)

    # 8. Дедупликация (по ФИО + компания)
    deduplicated = _deduplicate(validated)

    if rejected_count > 0:
        logger.info(
            "Нормализатор: отклонено %d из %d контактов, итого %d уникальных",
            rejected_count, len(contacts), len(deduplicated),
        )

    return deduplicated


def _validate_full_name(name: Optional[str]) -> bool:
    """
    Проверяет, что ФИО похоже на реальное имя человека.
    """
    if not name or not name.strip():
        return False

    name = name.strip()

    # Слишком короткое или длинное
    if len(name) < 4 or len(name) > 100:
        return False

    # Содержит числа, URL-символы, email
    if re.search(r"[\d@:/\\#\[\]{}]", name):
        return False

    # Содержит URL
    if re.search(r"https?://|www\.|\.com|\.ru|\.org", name, re.I):
        return False

    words = name.split()

    # Имя должно состоять из 2-5 слов
    if len(words) < 2 or len(words) > 5:
        return False

    # Каждое слово должно начинаться с заглавной буквы
    for word in words:
        for part in word.split("-"):
            part_clean = part.rstrip(".")
            if part_clean and not part_clean[0].isupper():
                return False

    # Исключаем организационные термины
    name_lower = name.lower()
    for kw in ORG_KEYWORDS:
        if kw in name_lower:
            return False

    # Исключаем известных политиков
    for person in BLACKLISTED_PERSONS:
        if person in name_lower:
            return False

    return True


def _clean_full_name(name: str) -> str:
    """Очищает и нормализует ФИО."""
    name = name.strip()
    # Убираем лишние пробелы
    name = re.sub(r"\s+", " ", name)
    # Убираем точки после полных слов (но не после инициалов)
    parts = name.split()
    cleaned = []
    for part in parts:
        if len(part) > 2 and part.endswith("."):
            cleaned.append(part.rstrip("."))
        else:
            cleaned.append(part)
    return " ".join(cleaned)


def _validate_position(position: Optional[str]) -> Optional[str]:
    """
    Проверяет, что строка является реальной должностью.
    Отклоняет мусор: телефоны, email, адреса, даты, URL.
    """
    if not position or not position.strip():
        return None

    position = position.strip()

    # Слишком короткое или длинное
    if len(position) < 3 or len(position) > 150:
        return None

    # Мусорные слова — метки полей, не должности
    garbage_labels = {
        "адрес", "адрес:", "телефон", "телефон:", "e-mail", "e-mail:", "email", "email:",
        "факс", "факс:", "fax", "fax:", "тел", "тел:", "тел.", "почта", "почта:",
        "phone", "phone:", "address", "address:", "контакт", "контакт:", "контакты",
        "реквизиты", "реквизиты:", "название", "сайт", "сайт:", "офис", "офис:",
        "город", "город:", "индекс", "индекс:", "улица", "район", "область",
        "проспект", "переулок", "шоссе", "бульвар", "набережная",
    }
    if position.lower().rstrip(":").strip() in garbage_labels or position.lower().strip() in garbage_labels:
        return None

    # Если позиция состоит из одного слова и заканчивается на ":", это метка поля
    if position.endswith(":") and " " not in position.strip().rstrip(":"):
        return None

    # Содержит email
    if "@" in position:
        return None

    # Содержит URL
    if re.search(r"https?://|www\.", position, re.I):
        return None

    # Содержит телефон (паттерн +7 или 8(...)...)
    if re.search(r"(?:\+7|8[\s\-]?\(?\d{3})\)?[\s\-]?\d{3}", position):
        return None

    # Содержит дату
    if re.search(r"\d{2}[./-]\d{2}[./-]\d{2,4}", position):
        return None

    # Слишком много цифр
    digit_count = sum(1 for c in position if c.isdigit())
    if digit_count > 4:
        return None

    # Физический адрес
    address_markers = ["ул.", "пр.", "пер.", "д.", "кв.", "корп.", "стр.", "обл.", "р-н"]
    pos_lower = position.lower()
    address_hits = sum(1 for m in address_markers if m in pos_lower)
    if address_hits >= 2:
        return None

    # Слишком длинное (>8 слов обычно не должность)
    if len(position.split()) > 8:
        return None

    return position


def _is_generic_email(email: str) -> bool:
    """Проверяет, является ли email общим/корпоративным (НЕ личным)."""
    if not email:
        return False
    prefix = email.split("@")[0].lower().strip()
    if prefix in GENERIC_EMAIL_PREFIXES:
        return True
    # Проверяем нормализованный (без разделителей)
    normalized = prefix.replace("-", "").replace(".", "").replace("_", "")
    normalized_prefixes = {p.replace("-", "").replace(".", "").replace("_", "") for p in GENERIC_EMAIL_PREFIXES}
    if normalized in normalized_prefixes:
        return True
    # Короткие префиксы (1-3 символа) — обычно аббревиатуры отделов, не личные
    if len(prefix) <= 3 and not prefix.isdigit():
        return True
    # Содержит слова-маркеры отделов
    dept_markers = {"filial", "otdel", "dept", "unit", "group", "sector", "region"}
    for marker in dept_markers:
        if marker in prefix:
            return True
    return False


def _deduplicate(contacts: list[ContactRecord]) -> list[ContactRecord]:
    """Удаляет дубликаты по ФИО + компания."""
    seen: set[str] = set()
    unique: list[ContactRecord] = []
    for c in contacts:
        key = f"{(c.full_name or '').lower().strip()}|{(c.company_name or '').lower().strip()}"
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique
