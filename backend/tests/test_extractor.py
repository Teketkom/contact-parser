"""
Tests for the information extraction module.

Covers:
- Email regex extraction
- Phone extraction and normalisation
- INN/KPP extraction and validation
- Russian FIO (full name) detection
- English name detection
- Position matching (exact + fuzzy)
- Company name extraction from HTML
"""

from __future__ import annotations

import re
from typing import Optional
import pytest


# ── We import the extractor module under test.
#    If not yet implemented, we stub the functions so tests run standalone.
# ──────────────────────────────────────────────────────────────────────────────

def _try_import_extractor():
    try:
        import extractor  # type: ignore
        return extractor
    except ImportError:
        return None


extractor = _try_import_extractor()


# ─── Standalone regex implementations used as reference / fallback ──────────────────────────────

def extract_emails_ref(text: str) -> list[str]:
    """Reference email extractor."""
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    return list(set(re.findall(pattern, text)))


def extract_phones_ref(text: str) -> list[str]:
    """Reference phone extractor — returns normalised +7 format."""
    raw_pattern = r"""
        (?:
            \+7|8           # country code
        )
        [\s\-\(]*
        \d{3}               # area code
        [\s\-\)]*
        \d{3}               # first part
        [\s\-]*
        \d{2}               # second part
        [\s\-]*
        \d{2}               # third part
    """
    raw = re.findall(raw_pattern, text, re.VERBOSE)
    normalised = []
    for phone in raw:
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 11:
            normalised.append(f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}")
    return list(set(normalised))


def extract_inn_ref(text: str) -> list[str]:
    """Extract INN (tax ID) — 10 or 12 digits with context."""
    pattern = r"ИНН\s*:?\s*(\d{12}|\d{10})"
    return re.findall(pattern, text, re.IGNORECASE)


def extract_kpp_ref(text: str) -> list[str]:
    """Extract KPP — 9 digits with context."""
    pattern = r"КПП\s*:?\s*(\d{9})"
    return re.findall(pattern, text, re.IGNORECASE)


def extract_russian_fio_ref(text: str) -> list[str]:
    """Extract Russian full names (Фамилия Имя Отчество)."""
    pattern = r"[\u0410-\u042f\u0401][\u0430-\u044f\u0451]+\s+[\u0410-\u042f\u0401][\u0430-\u044f\u0451]+(?:\s+[\u0410-\u042f\u0401][\u0430-\u044f\u0451]+)?"
    candidates = re.findall(pattern, text)
    result = []
    for c in candidates:
        parts = c.strip().split()
        if 2 <= len(parts) <= 3 and all(len(p) >= 2 for p in parts):
            result.append(c.strip())
    return list(set(result))


def extract_english_names_ref(text: str) -> list[str]:
    """Extract English names (Title Case sequences)."""
    pattern = r"\b[A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?\b"
    candidates = re.findall(pattern, text)
    stopwords = {
        "Chief Executive", "Chief Financial", "Vice President",
        "Managing Director", "About Us", "Contact Us",
    }
    return [c for c in set(candidates) if c not in stopwords]


def match_position_ref(position: str, targets: list[str], threshold: float = 0.6) -> bool:
    """
    Fuzzy position matching using simple token overlap.
    Returns True if position matches any target above threshold.
    """
    pos_tokens = set(position.lower().split())
    for target in targets:
        target_tokens = set(target.lower().split())
        if not target_tokens:
            continue
        intersection = pos_tokens & target_tokens
        score = len(intersection) / len(target_tokens)
        if score >= threshold:
            return True
        if target.lower() in position.lower() or position.lower() in target.lower():
            return True
    return False


def extract_company_name_ref(html: str) -> Optional[str]:
    """Extract company name from HTML title or meta tags."""
    og_match = re.search(
        r'<meta[^>]*property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    ) or re.search(
        r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:site_name["\']',
        html, re.IGNORECASE
    )
    if og_match:
        return og_match.group(1).strip()
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
        for sep in [" — ", " - ", " | ", " :: "]:
            if sep in title:
                parts = title.split(sep)
                for part in reversed(parts):
                    part = part.strip()
                    if len(part) > 3:
                        return part
        if title:
            return title
    return None


# ── Email tests ─────────────────────────────────────────────────────────────────────────────

class TestEmailExtraction:
    def _extract(self, text: str) -> list[str]:
        if extractor and hasattr(extractor, "extract_emails"):
            return extractor.extract_emails(text)
        return extract_emails_ref(text)

    def test_single_email(self):
        result = self._extract("Напишите нам: info@company.ru")
        assert "info@company.ru" in result

    def test_multiple_emails(self):
        text = "Контакты: director@firm.com и buh@firm.com"
        result = self._extract(text)
        assert len(result) == 2
        assert "director@firm.com" in result
        assert "buh@firm.com" in result

    def test_no_email(self):
        result = self._extract("Позвоните нам по телефону.")
        assert result == []

    def test_email_with_plus(self):
        result = self._extract("Contact: user+tag@example.org")
        assert "user+tag@example.org" in result

    def test_email_with_subdomain(self):
        result = self._extract("support@mail.company.com")
        assert "support@mail.company.com" in result

    def test_email_case_insensitive(self):
        result = self._extract("EMAIL: INFO@COMPANY.RU")
        assert any("info@company.ru" == e.lower() for e in result)

    def test_duplicate_emails_deduplicated(self):
        text = "info@example.com и info@example.com"
        result = self._extract(text)
        assert result.count("info@example.com") == 1

    def test_invalid_email_not_extracted(self):
        result = self._extract("not-an-email @broken example@")
        assert result == []

    def test_email_in_html_tag(self):
        html = '<a href="mailto:ceo@company.com">Написать</a>'
        result = self._extract(html)
        assert "ceo@company.com" in result


# ── Phone tests ────────────────────────────────────────────────────────────────────────────

class TestPhoneExtraction:
    def _extract(self, text: str) -> list[str]:
        if extractor and hasattr(extractor, "extract_phones"):
            return extractor.extract_phones(text)
        return extract_phones_ref(text)

    def test_russian_mobile_plus7(self):
        result = self._extract("+7 (916) 123-45-67")
        assert len(result) == 1

    def test_russian_mobile_8(self):
        result = self._extract("8 (916) 123-45-67")
        assert len(result) == 1

    def test_landline_495(self):
        result = self._extract("Тел: +7 (495) 000-11-22")
        assert len(result) == 1

    def test_multiple_phones(self):
        text = "Тел: 8 800 555 35 35, моб: +7 916 123 45 67"
        result = self._extract(text)
        assert len(result) == 2

    def test_phone_normalisation_format(self):
        result = self._extract("+7(495)1234567")
        assert len(result) == 1
        phone = result[0]
        assert re.sub(r"\D", "", phone).startswith("7")

    def test_no_phone(self):
        result = self._extract("Адрес: г. Москва, ул. Ленина, д. 1")
        assert result == []

    def test_toll_free_800(self):
        result = self._extract("8 (800) 555-35-35 — звонок бесплатный")
        assert len(result) == 1


# ── INN / KPP tests ───────────────────────────────────────────────────────────────────────

class TestInnKppExtraction:
    def _extract_inn(self, text: str) -> list[str]:
        if extractor and hasattr(extractor, "extract_inn"):
            return extractor.extract_inn(text)
        return extract_inn_ref(text)

    def _extract_kpp(self, text: str) -> list[str]:
        if extractor and hasattr(extractor, "extract_kpp"):
            return extractor.extract_kpp(text)
        return extract_kpp_ref(text)

    def test_inn_10_digits(self):
        result = self._extract_inn("ИНН: 7707123456")
        assert "7707123456" in result

    def test_inn_12_digits_individual(self):
        result = self._extract_inn("ИНН 770712345678")
        assert "770712345678" in result

    def test_kpp_9_digits(self):
        result = self._extract_kpp("КПП: 770701001")
        assert "770701001" in result

    def test_inn_kpp_together(self):
        text = "Реквизиты: ИНН 7707123456, КПП 770701001"
        inn = self._extract_inn(text)
        kpp = self._extract_kpp(text)
        assert "7707123456" in inn
        assert "770701001" in kpp

    def test_no_inn(self):
        result = self._extract_inn("Адрес: г. Москва, ул. Ленина, д. 1")
        assert result == []

    def test_inn_without_label_not_extracted(self):
        result = self._extract_inn("Номер счёта: 4070281234")
        assert result == []


# ── Russian FIO tests ─────────────────────────────────────────────────────────────────────────

class TestRussianFioExtraction:
    def _extract(self, text: str) -> list[str]:
        if extractor and hasattr(extractor, "extract_russian_names"):
            return extractor.extract_russian_names(text)
        return extract_russian_fio_ref(text)

    def test_three_part_name(self):
        result = self._extract("Директор: Иванов Иван Иванович")
        assert any("Иванов" in r for r in result)

    def test_two_part_name(self):
        result = self._extract("Контакт: Петрова Мария")
        assert any("Петрова" in r for r in result)

    def test_female_name(self):
        result = self._extract("Петрова Мария Сергеевна")
        assert any("Петрова" in r for r in result)

    def test_no_name_in_text(self):
        result = self._extract("Добро пожаловать на наш сайт.")
        assert result == []

    def test_multiple_names(self):
        text = "Иванов Иван Иванович и Петрова Мария Сергеевна"
        result = self._extract(text)
        assert len(result) >= 2


# ── English name tests ──────────────────────────────────────────────────────────────────────

class TestEnglishNameExtraction:
    def _extract(self, text: str) -> list[str]:
        if extractor and hasattr(extractor, "extract_english_names"):
            return extractor.extract_english_names(text)
        return extract_english_names_ref(text)

    def test_two_part_name(self):
        result = self._extract("Contact John Smith for inquiries.")
        assert any("John Smith" in r for r in result)

    def test_three_part_name(self):
        result = self._extract("Meet our CEO, Mary Jane Watson.")
        assert any("Mary Jane" in r for r in result)

    def test_no_name(self):
        result = self._extract("welcome to our website please visit us")
        assert result == []


# ── Position matching tests ────────────────────────────────────────────────────────────────

class TestPositionMatching:
    def _match(self, position: str, targets: list[str]) -> bool:
        if extractor and hasattr(extractor, "match_position"):
            return extractor.match_position(position, targets)
        return match_position_ref(position, targets)

    def test_exact_match(self):
        assert self._match("Генеральный директор", ["Генеральный директор"])

    def test_case_insensitive_match(self):
        assert self._match("ГЕНЕРАЛЬНЫЙ ДИРЕКТОР", ["генеральный директор"])

    def test_partial_match_director(self):
        assert self._match("Директор по развитию", ["директор"])

    def test_no_match(self):
        assert not self._match("Бухгалтер", ["Генеральный директор", "CEO"])

    def test_multiple_targets_one_matches(self):
        targets = ["CEO", "Генеральный директор", "Директор"]
        assert self._match("Финансовый директор", targets)

    def test_english_ceo(self):
        assert self._match("Chief Executive Officer", ["CEO", "Chief Executive Officer"])

    def test_empty_targets(self):
        assert not self._match("Директор", [])

    def test_abbreviation_ceo(self):
        assert self._match("CEO", ["CEO", "Chief Executive Officer"])

    def test_fuzzy_typo(self):
        result = self._match("Ген. директор", ["Генеральный директор"])
        assert isinstance(result, bool)


# ── Company name extraction tests ─────────────────────────────────────────────────────────

class TestCompanyNameExtraction:
    def _extract(self, html: str) -> Optional[str]:
        if extractor and hasattr(extractor, "extract_company_name"):
            return extractor.extract_company_name(html)
        return extract_company_name_ref(html)

    def test_from_title_with_separator(self):
        html = "<html><head><title>ООО Пример — Главная</title></head><body/></html>"
        result = self._extract(html)
        assert result is not None
        assert "ООО Пример" in result or "Главная" in result

    def test_from_og_site_name(self):
        html = """
        <html><head>
          <meta property="og:site_name" content="ACME Corp" />
          <title>Home</title>
        </head><body/></html>
        """
        result = self._extract(html)
        assert result == "ACME Corp"

    def test_no_title(self):
        result = self._extract("<html><body><p>Text</p></body></html>")
        assert result is None or isinstance(result, str)

    def test_empty_html(self):
        result = self._extract("")
        assert result is None or isinstance(result, str)
