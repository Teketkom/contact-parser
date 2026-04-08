"""
Модуль нормализации контактов — ПОСЛЕДНИЙ БАРЬЕР перед выгрузкой в Excel.
Жёсткая валидация ФИО, должностей, email. Удаление мусорных строк.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.models import ContactRecord

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# СЛОВАРИ ФИЛЬТРАЦИИ
# ══════════════════════════════════════════════════════════════════════════════

# Слова-мусор, которые regex захватывает как часть ФИО с сайтов
GARBAGE_NAME_WORDS = frozenset({
    "подробнее", "подробности", "подробно", "далее", "ещё", "еще", "читать",
    "смотреть", "more", "details", "read", "view", "show",
    "банкротство", "банкротства", "банкротств",
    "практика", "практики",
    "компания", "компании", "компаний",
    "галерея", "галереи",
    "кооперативная", "кооперативный",
    "республика", "республики",
    "металлургический", "металлургическая", "металлургического",
    "пленэр", "пленэра",
    "юрист", "юриста", "юристов",
    "адвокат", "адвоката", "адвокатов",
    "партнер", "партнёр", "партнера", "партнёра",
    "сооснователь", "сооснователя",
    "основатель", "основателя",
    "бокситов", "боксит", "бокситы",
    "тимана", "тиман",
    "конференция", "конференции",
    "форум", "форума",
    "выставка", "выставки",
    "мероприятие", "мероприятия",
    "семинар", "семинара",
    "фестиваль", "фестиваля",
    "проект", "проекта", "проектов",
    "программа", "программы",
    "отдел", "отдела", "отделов",
    "управление", "управления",
    "департамент", "департамента",
    "дивизион", "дивизиона",
    "филиал", "филиала",
    "представительство", "представительства",
    "корпорация", "корпорации",
    "холдинг", "холдинга",
    "группа", "группы",
    "комитет", "комитета",
    "совет", "совета",
    "президент", "президента",  # Путин и т.д.
    "правительство", "правительства",
    "министерство", "министерства",
    "ведомство", "ведомства",
    # Страны
    "туркменистан", "узбекистан", "украина", "казахстан", "таджикистан",
    "кыргызстан", "белоруссия", "беларусь", "грузия", "армения",
    "азербайджан", "молдова", "молдавия", "латвия", "литва", "эстония",
    "россия", "гайана", "гайаны",
    # Прочий мусор
    "арест", "ареста", "строительства", "строительство",
    "пятилетки", "пятилетка", "предвкушении", "расширение",
    "итоги", "активная", "фаза", "победы", "трудовые", "будни",
    "сортамент", "продукции", "ринат", "шарафутдинов",
})

# Города России — если ВСЕ слова ФИО это города, значит это мусор
RUSSIAN_CITIES = frozenset({
    "москва", "санкт-петербург", "петербург", "новосибирск", "екатеринбург",
    "казань", "нижний", "новгород", "челябинск", "самара", "омск", "ростов",
    "уфа", "красноярск", "пермь", "воронеж", "волгоград", "краснодар",
    "саратов", "тюмень", "тольятти", "ижевск", "барнаул", "иркутск",
    "ульяновск", "хабаровск", "владивосток", "ярославль", "махачкала",
    "томск", "оренбург", "кемерово", "новокузнецк", "рязань", "астрахань",
    "пенза", "липецк", "тула", "курск", "сочи", "калининград", "чебоксары",
    "брянск", "мурманск", "магнитогорск", "норильск", "сургут", "архангельск",
    "смоленск", "белгород", "вологда", "псков", "петрозаводск", "тверь",
    "киров", "калуга", "орёл", "орел", "тамбов", "кострома", "иваново",
    "владимир", "йошкар-ола", "чита", "якутск", "улан-удэ", "абакан",
    "благовещенск", "южно-сахалинск", "биробиджан", "анадырь", "магадан",
    "петропавловск-камчатский", "нарьян-мар", "ханты-мансийск", "салехард",
    "сыктывкар", "элиста", "черкесск", "нальчик", "владикавказ", "грозный",
    "ставрополь", "майкоп", "горно-алтайск", "кызыл", "воткинск", "выборг",
    "гатчина", "гатчин", "колпино", "пушкин", "стерлитамак", "нефтекамск",
    "октябрьский", "набережные", "челны", "нижнекамск", "альметьевск",
    "дзержинск", "арзамас", "саров", "бор", "кстово", "балахна",
})

# Известные политики/не-сотрудники
BLACKLISTED_NAMES = frozenset({
    # Президенты и политики
    "путин владимир владимирович", "путин в.в.", "путин в в",
    "медведев дмитрий анатольевич", "мишустин михаил владимирович",
    "лавров сергей викторович", "шойгу сергей кужугетович",
    "россии владимир владимирович",  # "Президент России В.В. Путин" -> парсер ловит "России Владимир Владимирович"
    "рф владимир владимирович",
    # Исторические личности (названия улиц, учреждений)
    "ленин владимир ильич", "в.и. ленина", "в.и.ленина",
    "менделеев дмитрий иванович", "д.и. менделеева", "д.и.менделеева",
    "ломоносов михаил васильевич", "м.в. ломоносова", "м.в.ломоносова",
    "пушкин александр сергеевич", "а.с. пушкина", "а.с.пушкина",
    "сеченов иван михайлович", "и.м. сеченова", "и.м.сеченова",
    "пирогов николай иванович", "н.и. пирогова", "н.и.пирогова",
    "губкин иван михайлович", "и.м. губкина", "и.м.губкина",
    "бауман николай эрнестович", "н.э. баумана", "н.э.баумана",
    "плеханов георгий валентинович", "г.в. плеханова", "г.в.плеханова",
    "вернадский владимир иванович", "в.и. вернадского", "в.и.вернадского",
    "королёв сергей павлович", "с.п. королёва", "с.п.королева",
    "сербский владимир петрович", "в.п. сербского", "в.п.сербского",
    "мозолина виктория павловна",
    # Министры, губернаторы
    "мантуров денис валентинович", "д.в. мантуров", "д.в.мантуров",
    "дрозденко александр юрьевич", "а.ю. дрозденко", "а.ю.дрозденко",
    "чемезов сергей викторович", "с.в. чемезов",
    "сечин игорь иванович", "и.и. сечин",
    "миллер алексей борисович", "а.б. миллер",
    "греф герман оскарович", "г.о. греф",
    "набиуллина эльвира сахипзадовна",
    "силуанов антон германович", "а.г. силуанов",
    "костин андрей леонидович", "а.л. костин",
    "собянин сергей семёнович", "с.с. собянин",
    "беглов александр дмитриевич", "а.д. беглов",
    "воробьёв андрей юрьевич", "а.ю. воробьёв",
    "кадыров рамзан ахматович", "р.а. кадыров",
})

# Паттерны: имена оканчивающиеся на "а" в родительном падеже (названия объектов: "им. Менделеева")
GENITIVE_HISTORICAL = frozenset({
    # Учёные, писатели, политики — часто в названиях институтов, улиц
    "ленина", "менделеева", "ломоносова", "пушкина", "сеченова",
    "пирогова", "губкина", "баумана", "плеханова", "вернадского",
    "королёва", "королева", "сербского", "мозолина", "гагарина",
    "чайковского", "толстого", "достоевского", "чехова", "горького",
    "тургенева", "лермонтова", "некрасова", "грибоедова", "жуковского",
    "кутузова", "суворова", "нахимова", "ушакова",
    # Учёные-агрономы/химики (часто в названиях НИИ ФосАгро и т.д.)
    "тимирязева", "прянишникова", "бакулева", "лавёрова", "лаверова",
    "вавилова", "мичурина", "докучаева", "вильямса", "костычева",
    # Медики
    "склифосовского", "боткина", "филатова", "бурденко", "бехтерева",
    "павлова", "мечникова",
    # Инженеры/конструкторы
    "жуковского", "туполева", "яковлева", "ильюшина", "микояна",
    "курчатова", "ландау", "капицы",
    # Прочие
    "герцена", "крупской", "кирова", "калинина", "свердлова",
    "орджоникидзе", "дзержинского", "фрунзе", "чапаева",
    "тимошенко", "жданова", "маленкова",
})

# Месяцы — для фильтрации дат в должностях
MONTHS_RU = frozenset({
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
})

MONTHS_EN = frozenset({
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
})

# Мусорные слова в должностях
GARBAGE_POSITION_WORDS = frozenset({
    "подробнее", "подробности", "далее", "галерея", "республика",
    "кооперативная", "пленэр", "бокситов", "тимана", "конференция",
    "форум", "выставка", "мероприятие", "семинар", "фестиваль",
    "компания", "корпорация", "холдинг", "программа",
})

# Общие email-префиксы (НЕ личные)
GENERIC_EMAIL_PREFIXES = frozenset({
    "info", "support", "help", "admin", "office", "pr", "secretary",
    "reception", "contact", "contacts", "mail", "noreply", "no-reply",
    "sales", "marketing", "press", "media", "feedback", "webmaster",
    "postmaster", "abuse", "security", "careers", "jobs", "hr", "legal",
    "compliance", "billing", "finance", "accounting", "it", "tech", "dev",
    "api", "team", "hello", "general", "service", "inquiry", "request",
    "booking", "order", "subscribe", "unsubscribe", "newsletter",
    "moscow", "msk", "spb", "kazan", "region", "filial", "dept",
    "otdel", "uso", "unit", "group", "sector", "client", "clients",
    "work", "vacancy", "vacancies", "tender", "tenders", "zakupki",
    "zakaz", "zayavka", "priemnaya", "priemka", "post", "pochta",
    "sekretariat", "sekretar", "kanc", "kancelaria", "obshchiy",
    "docs", "documents", "doc", "priem", "hotline", "call", "center",
    "welcome", "corporate", "company", "invest", "investor", "investors",
    "report", "reports", "supply", "suppliers", "supplier",
    "quality", "audit", "risk", "treasury", "tax", "procurement",
})


# ══════════════════════════════════════════════════════════════════════════════
# ОСНОВНАЯ ФУНКЦИЯ
# ══════════════════════════════════════════════════════════════════════════════

def normalize_contacts(contacts: list[ContactRecord]) -> list[ContactRecord]:
    """
    Нормализация и очистка контактов. Удаляет мусор, валидирует каждое поле.
    Возвращает только качественные записи.
    """
    result: list[ContactRecord] = []
    seen: dict[str, int] = {}  # dedup_key -> index in result
    removed_count = 0

    for contact in contacts:
        # ── 1. Валидация ФИО (критично — если невалидно, удаляем строку) ──
        if not _validate_name(contact.full_name):
            removed_count += 1
            continue

        # Нормализуем ФИО
        contact.full_name = _normalize_name(contact.full_name)

        # Очистка названия компании от мусора (;)
        if contact.company_name and ";" in contact.company_name:
            parts = contact.company_name.split(";")
            contact.company_name = parts[0].strip()

        # Проверка на чёрный список (политики)
        name_lower = contact.full_name.lower().strip() if contact.full_name else ""
        if name_lower in BLACKLISTED_NAMES:
            removed_count += 1
            continue
        # Проверка: последнее слово — родительный падеж исторической личности
        if name_lower:
            last_w = name_lower.split()[-1].strip(".,;:-") if name_lower.split() else ""
            if last_w in GENITIVE_HISTORICAL:
                removed_count += 1
                continue

        # ── 2. Валидация должности ──
        contact.position_raw = _validate_position(contact.position_raw)
        if not contact.position_raw:
            contact.position_normalized = None
        elif not _validate_position(contact.position_normalized):
            contact.position_normalized = contact.position_raw

        # ── 3. Классификация email ──
        if contact.personal_email and _is_generic_email(contact.personal_email):
            if not contact.company_email:
                contact.company_email = contact.personal_email.lower().strip()
            contact.personal_email = None

        if contact.personal_email:
            contact.personal_email = contact.personal_email.lower().strip()
        if contact.company_email:
            contact.company_email = contact.company_email.lower().strip()

        # ── 4. Валидация ИНН/КПП ──
        contact.inn = _validate_inn(contact.inn)
        contact.kpp = _validate_kpp(contact.kpp)

        # ── 5. Проверка ценности строки ──
        # Строка должна иметь хотя бы: ФИО + (email OR phone)
        # Строка должна содержать хоть что-то полезное кроме имени
        # (email, телефон, или должность)
        has_useful = bool(
            contact.personal_email or
            contact.phone or
            contact.position_raw or
            contact.position_normalized or
            contact.inn
        )
        if not has_useful:
            removed_count += 1
            continue

        # ── 6. Дедупликация с мержем данных ──
        # Если тот же человек из той же компании — объединить данные, не дублировать
        dedup_key = f"{(contact.full_name or '').lower().strip()}|{(contact.company_name or '').lower().strip()}"
        if dedup_key in seen:
            # Найти существующую запись и обогатить её
            existing_idx = seen[dedup_key]
            existing = result[existing_idx]
            # Заполняем пустые поля из дубля
            if not existing.personal_email and contact.personal_email:
                existing.personal_email = contact.personal_email
            if not existing.company_email and contact.company_email:
                existing.company_email = contact.company_email
            if not existing.phone and contact.phone:
                existing.phone = contact.phone
            if not existing.inn and contact.inn:
                existing.inn = contact.inn
            if not existing.kpp and contact.kpp:
                existing.kpp = contact.kpp
            if not existing.position_raw and contact.position_raw:
                existing.position_raw = contact.position_raw
            if not existing.position_normalized and contact.position_normalized:
                existing.position_normalized = contact.position_normalized
            if existing.social_links is None and contact.social_links is not None:
                existing.social_links = contact.social_links
            removed_count += 1
            continue
        seen[dedup_key] = len(result)  # store index

        result.append(contact)

    if removed_count > 0:
        logger.info(
            "Нормализатор: удалено %d мусорных записей из %d (осталось %d)",
            removed_count, len(contacts), len(result),
        )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# ВАЛИДАЦИЯ ФИО
# ══════════════════════════════════════════════════════════════════════════════

def _validate_name(name: Optional[str]) -> bool:
    """Проверяет, является ли строка реальным ФИО."""
    if not name or not name.strip():
        return False

    name = name.strip()

    # Длина
    if len(name) < 4 or len(name) > 70:
        return False

    # Содержит мусорные слова
    name_lower = name.lower()
    for word in name_lower.split():
        word_clean = word.strip(".,;:-()\"'")
        if word_clean in GARBAGE_NAME_WORDS:
            return False

    # Количество слов: ФИО = 2-4 слова (Фамилия Имя, Фамилия Имя Отчество, или с инициалами)
    words = name.split()
    # Убираем инициалы при подсчёте
    real_words = [w for w in words if len(w) > 2 or (len(w) == 2 and w.endswith("."))]
    if len(real_words) < 2 or len(real_words) > 4:
        return False

    # Каждое слово должно начинаться с заглавной (кириллица или латиница)
    for word in words:
        if len(word) <= 2 and word.endswith("."):
            continue  # Инициал
        first = word[0]
        if not (("\u0410" <= first <= "\u042f") or first == "\u0401" or ("A" <= first <= "Z")):
            return False

    # Проверяем, не город ли это
    name_words_lower = {w.lower().strip(".,;:-()") for w in words if len(w) > 2}
    if name_words_lower and name_words_lower.issubset(RUSSIAN_CITIES):
        return False

    # Содержит цифры — не ФИО
    if re.search(r"\d", name):
        return False

    # Содержит метки полей (Тел., Tel., Email и т.д.)
    field_labels = {"тел", "тел.", "tel", "tel.", "телефон", "email", "e-mail", "факс", "fax", "адрес", "address"}
    for word in name.lower().split():
        if word.strip(".,;:-()") in field_labels:
            return False

    # Содержит спецсимволы (кроме дефиса и точки)
    if re.search(r"[@#$%^&*=+{}\[\]<>/\\|~`]", name):
        return False

    return True


def _normalize_name(name: str) -> str:
    """Нормализует ФИО — убирает лишние пробелы, правильный регистр."""
    name = " ".join(name.split())  # Убрать двойные пробелы
    return name.strip()


# ══════════════════════════════════════════════════════════════════════════════
# ВАЛИДАЦИЯ ДОЛЖНОСТИ
# ══════════════════════════════════════════════════════════════════════════════

def _validate_position(position: Optional[str]) -> Optional[str]:
    """Проверяет, является ли строка реальной должностью."""
    if not position or not position.strip():
        return None

    position = position.strip()

    # Длина
    if len(position) < 3 or len(position) > 100:
        return None

    pos_lower = position.lower()

    # Это дата (месяц)
    for month in MONTHS_RU | MONTHS_EN:
        if month in pos_lower:
            return None

    # Паттерн даты (01 ..., dd.mm.yyyy)
    if re.match(r"^\d{1,2}\s", position) or re.match(r"^\d{1,2}\.\d{1,2}\.\d{2,4}", position):
        return None

    # Содержит только цифры
    if re.match(r"^[\d\s.,-]+$", position):
        return None

    # Содержит email, URL
    if "@" in position or "http" in pos_lower or "www." in pos_lower:
        return None
    if re.search(r"\.\w{2,3}$", position):  # Заканчивается на .ru, .com
        return None

    # Содержит телефон
    if re.search(r"(?:\+7|8[\s\-]?\(?\d{3})\)?[\s\-]?\d{3}", position):
        return None

    # Заканчивается на ":" — это метка поля, не должность
    if position.endswith(":"):
        return None

    # Мусорные слова в должности
    for word in pos_lower.split():
        word_clean = word.strip(".,;:-()\"'")
        if word_clean in GARBAGE_POSITION_WORDS:
            return None

    # Год в должности (2023, 2024, 2025, 2026) — скорее всего мероприятие
    if re.search(r"\b20[1-3]\d\b", position):
        return None

    # Проза / заголовок новости: если > 5 слов и нет слов-маркеров должности
    pos_words = position.split()
    if len(pos_words) > 5:
        POSITION_MARKERS = {"директор", "менеджер", "начальник", "руководитель",
            "заместитель", "главный", "ведущий", "старший", "младший",
            "специалист", "инженер", "бухгалтер", "аналитик", "юрист", "адвокат", "нотариус", "арбитражный",
            "консультант", "управляющий", "советник", "партнер", "партнёр", "president", "director",
            "manager", "head", "chief", "officer", "lead", "senior", "vp",
            "ceo", "cto", "cfo", "coo", "cio", "chairman",
            "председатель", "президент", "вице-президент"}
        pos_lower_words = {w.lower().strip(".,;:-") for w in pos_words}
        if not pos_lower_words & POSITION_MARKERS:
            return None

    # Содержит слова-маркеры новостей/прозы
    NEWS_WORDS = {"строительства", "строительство", "пятилетки", "предвкушении",
        "победы", "расширение", "сортамента", "продукции", "итоги", "активная",
        "фаза", "трудовые", "будни", "арест", "ареста"}
    for w in pos_lower.split():
        if w.strip(".,;:-") in NEWS_WORDS:
            return None

    return position


# ══════════════════════════════════════════════════════════════════════════════
# ВАЛИДАЦИЯ EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def _is_generic_email(email: str) -> bool:
    """Проверяет, является ли email общим/корпоративным (НЕ личным)."""
    if not email:
        return False

    prefix = email.split("@")[0].lower().strip()

    # Точное совпадение
    if prefix in GENERIC_EMAIL_PREFIXES:
        return True

    # Нормализация (без разделителей)
    normalized = prefix.replace("-", "").replace(".", "").replace("_", "")
    norm_prefixes = {p.replace("-", "").replace(".", "").replace("_", "") for p in GENERIC_EMAIL_PREFIXES}
    if normalized in norm_prefixes:
        return True

    # Короткий префикс (≤3 символа) — аббревиатура отдела
    if len(prefix) <= 3:
        return True

    # Содержит маркеры отделов/филиалов
    dept_markers = {"filial", "otdel", "dept", "unit", "group", "sector", "region",
                    "moscow", "kazan", "spb", "murm", "kola"}
    for marker in dept_markers:
        if marker in prefix:
            return True

    return False


# ══════════════════════════════════════════════════════════════════════════════
# ВАЛИДАЦИЯ ИНН/КПП
# ══════════════════════════════════════════════════════════════════════════════

def _validate_inn(inn: Optional[str]) -> Optional[str]:
    if not inn:
        return None
    digits = re.sub(r"\D", "", inn)
    return digits if len(digits) in (10, 12) else None


def _validate_kpp(kpp: Optional[str]) -> Optional[str]:
    if not kpp:
        return None
    digits = re.sub(r"\D", "", kpp)
    return digits if len(digits) == 9 else None
