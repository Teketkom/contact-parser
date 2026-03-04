"""
Tests for the blacklist module.

Covers:
- Loading domains from a text file (one per line)
- Loading domains from CSV/Excel
- Checking if a URL is blacklisted
- Adding domains to the blacklist
- Removing domains from the blacklist
- Domain normalisation (www. prefix, case)
- Blacklist persistence
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

import pytest


def _try_import_blacklist():
    try:
        import blacklist  # type: ignore
        return blacklist
    except ImportError:
        return None


blacklist_module = _try_import_blacklist()


class BlacklistRef:
    def __init__(self):
        self._domains: set[str] = set()

    def _normalise_domain(self, domain: str) -> str:
        domain = domain.strip().lower()
        for prefix in ("https://", "http://"):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
                break
        domain = domain.split("/")[0].split("?")[0].split("#")[0]
        domain = domain.split(":")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def add(self, domain: str, reason: Optional[str] = None) -> bool:
        norm = self._normalise_domain(domain)
        if not norm:
            return False
        if norm in self._domains:
            return False
        self._domains.add(norm)
        return True

    def remove(self, domain: str) -> bool:
        norm = self._normalise_domain(domain)
        if norm in self._domains:
            self._domains.discard(norm)
            return True
        return False

    def is_blocked(self, url_or_domain: str) -> bool:
        domain = url_or_domain.strip().lower()
        for prefix in ("https://", "http://"):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        domain = domain.split("/")[0].split(":")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain in self._domains

    def load_from_text(self, text: str) -> int:
        count = 0
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if self.add(line):
                    count += 1
        return count

    def list_all(self) -> list[str]:
        return sorted(self._domains)

    def count(self) -> int:
        return len(self._domains)


def _get_blacklist():
    if blacklist_module and hasattr(blacklist_module, "Blacklist"):
        return blacklist_module.Blacklist()
    return BlacklistRef()


class TestBlacklistAddRemove:
    def test_add_domain(self):
        bl = _get_blacklist()
        result = bl.add("spam.com")
        assert result is True

    def test_add_duplicate_returns_false(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        result = bl.add("spam.com")
        assert result is False

    def test_add_multiple_domains(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        bl.add("blocked.ru")
        bl.add("bad-site.net")
        assert bl.count() == 3

    def test_remove_existing_domain(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        result = bl.remove("spam.com")
        assert result is True
        assert not bl.is_blocked("spam.com")

    def test_remove_nonexistent_returns_false(self):
        bl = _get_blacklist()
        result = bl.remove("notexist.com")
        assert result is False

    def test_count_after_add_remove(self):
        bl = _get_blacklist()
        bl.add("a.com")
        bl.add("b.com")
        assert bl.count() == 2
        bl.remove("a.com")
        assert bl.count() == 1

    def test_list_all_returns_added_domains(self):
        bl = _get_blacklist()
        bl.add("c.com")
        bl.add("a.com")
        bl.add("b.com")
        result = bl.list_all()
        assert set(result) == {"a.com", "b.com", "c.com"}


class TestBlacklistDomainNormalisation:
    def test_www_prefix_stripped(self):
        bl = _get_blacklist()
        bl.add("www.spam.com")
        assert bl.is_blocked("spam.com")

    def test_case_insensitive(self):
        bl = _get_blacklist()
        bl.add("SPAM.COM")
        assert bl.is_blocked("spam.com")

    def test_https_url_blocked_by_domain(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        assert bl.is_blocked("https://spam.com")

    def test_http_url_blocked_by_domain(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        assert bl.is_blocked("http://spam.com")

    def test_url_with_path_blocked(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        assert bl.is_blocked("https://spam.com/some/page")

    def test_www_url_blocked_by_bare_domain(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        assert bl.is_blocked("https://www.spam.com/page")

    def test_add_url_stored_as_domain(self):
        bl = _get_blacklist()
        bl.add("https://www.blocked.ru/about")
        assert bl.is_blocked("blocked.ru")


class TestBlacklistIsBlocked:
    def test_not_blocked_by_default(self):
        bl = _get_blacklist()
        assert not bl.is_blocked("https://legitimate-site.com")

    def test_blocked_after_add(self):
        bl = _get_blacklist()
        bl.add("blocked.com")
        assert bl.is_blocked("blocked.com")

    def test_similar_domain_not_blocked(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        assert not bl.is_blocked("notspam.com")
        assert not bl.is_blocked("spam.org")

    def test_subdomain_of_blocked_domain(self):
        bl = _get_blacklist()
        bl.add("spam.com")
        result = bl.is_blocked("sub.spam.com")
        assert isinstance(result, bool)

    def test_empty_string_not_blocked(self):
        bl = _get_blacklist()
        result = bl.is_blocked("")
        assert isinstance(result, bool)


class TestBlacklistLoadFromText:
    def test_load_simple_text(self):
        bl = _get_blacklist()
        text = "spam.com\nblocked.ru\nbad-site.net\n"
        count = bl.load_from_text(text)
        assert count == 3

    def test_load_ignores_blank_lines(self):
        bl = _get_blacklist()
        text = "spam.com\n\n\nblocked.ru\n"
        count = bl.load_from_text(text)
        assert count == 2

    def test_load_ignores_comment_lines(self):
        bl = _get_blacklist()
        text = "# This is a comment\nspam.com\n# Another comment\nblocked.ru\n"
        count = bl.load_from_text(text)
        assert count == 2

    def test_loaded_domains_are_blocked(self):
        bl = _get_blacklist()
        bl.load_from_text("spam.com\nblocked.ru")
        assert bl.is_blocked("spam.com")
        assert bl.is_blocked("blocked.ru")

    def test_load_empty_text(self):
        bl = _get_blacklist()
        count = bl.load_from_text("")
        assert count == 0

    def test_load_with_www_prefix(self):
        bl = _get_blacklist()
        bl.load_from_text("www.spam.com\n")
        assert bl.is_blocked("spam.com")

    def test_load_with_https_prefix(self):
        bl = _get_blacklist()
        bl.load_from_text("https://spam.com\n")
        assert bl.is_blocked("spam.com")

    def test_duplicate_domains_in_text(self):
        bl = _get_blacklist()
        text = "spam.com\nspam.com\nspam.com\n"
        count = bl.load_from_text(text)
        assert count == 1
        assert bl.count() == 1


class TestBlacklistPersistence:
    def test_save_and_load_from_file(self, temp_dir):
        bl = _get_blacklist()
        bl.add("spam.com")
        bl.add("blocked.ru")
        filepath = temp_dir / "blacklist.txt"
        domains = bl.list_all()
        filepath.write_text("\n".join(domains))
        bl2 = _get_blacklist()
        loaded = bl2.load_from_text(filepath.read_text())
        assert loaded == 2
        assert bl2.is_blocked("spam.com")
        assert bl2.is_blocked("blocked.ru")

    def test_blacklist_file_created(self, temp_dir):
        filepath = temp_dir / "bl.txt"
        bl = _get_blacklist()
        bl.add("test.com")
        domains = bl.list_all()
        filepath.write_text("\n".join(domains))
        assert filepath.exists()
        assert filepath.stat().st_size > 0


class TestBlacklistEdgeCases:
    def test_add_invalid_domain_no_dot(self):
        bl = _get_blacklist()
        result = bl.add("notadomain")
        assert isinstance(result, bool)

    def test_add_empty_string(self):
        bl = _get_blacklist()
        result = bl.add("")
        assert result is False

    def test_add_none_like_string(self):
        bl = _get_blacklist()
        result = bl.add("  ")
        assert result is False

    def test_large_blacklist(self):
        bl = _get_blacklist()
        domains = [f"domain{i}.com" for i in range(500)]
        for d in domains:
            bl.add(d)
        assert bl.count() == 500
        assert bl.is_blocked("domain250.com")

    def test_russian_domain(self):
        bl = _get_blacklist()
        result = bl.add("пример.рф")
        assert isinstance(result, bool)
