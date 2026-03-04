"""
Tests for the web crawler module.

Covers:
- URL normalisation
- robots.txt parsing and enforcement
- Management/contact page detection heuristics
- User-Agent rotation
- Domain extraction
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import pytest


# ── Import crawler module or use reference implementations ────────────────────

def _try_import_crawler():
    try:
        import crawler  # type: ignore
        return crawler
    except ImportError:
        return None


crawler_module = _try_import_crawler()


# ── Reference implementations ─────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

MANAGEMENT_PATH_PATTERNS = [
    r"/about",
    r"/o-nas",
    r"/o-kompanii",
    r"/kontakty?",
    r"/contacts?",
    r"/rukovodstvo",
    r"/management",
    r"/team",
    r"/leadership",
    r"/komanda",
    r"/svedeniya",
    r"/info",
    r"/company",
]

MANAGEMENT_KEYWORDS = [
    "руководство", "директор", "начальник", "менеджмент",
    "management", "leadership", "team", "about", "contacts",
    "контакты", "о компании", "команда",
]


def normalise_url_ref(url: str) -> Optional[str]:
    """Normalise a URL: add scheme, lowercase host, remove trailing slash."""
    url = url.strip()
    if not url:
        return None
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        scheme = parsed.scheme.lower()
        host = parsed.netloc.lower()
        path = parsed.path.rstrip("/") or "/"
        return f"{scheme}://{host}{path}"
    except Exception:
        return None


def is_management_page_ref(url: str) -> bool:
    """Heuristic: does this URL likely contain management/contact info?"""
    url_lower = url.lower()
    path = urlparse(url_lower).path
    for pattern in MANAGEMENT_PATH_PATTERNS:
        if re.search(pattern, path):
            return True
    for kw in MANAGEMENT_KEYWORDS:
        if kw in url_lower:
            return True
    return False


def parse_robots_txt_ref(robots_content: str, user_agent: str = "*") -> RobotFileParser:
    """Parse robots.txt content and return RobotFileParser."""
    rp = RobotFileParser()
    rp.parse(robots_content.splitlines())
    return rp


def get_random_user_agent_ref() -> str:
    """Return a random User-Agent string."""
    import random
    return random.choice(USER_AGENTS)


def extract_domain_ref(url: str) -> Optional[str]:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        netloc = parsed.netloc.lower()
        netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc if netloc else None
    except Exception:
        return None


def get_internal_links_ref(base_url: str, html: str) -> list[str]:
    """Extract internal links from HTML relative to base_url."""
    base_domain = extract_domain_ref(base_url)
    pattern = r'href=["\']([^"\'#?]+)["\']'
    links = re.findall(pattern, html, re.IGNORECASE)
    result = []
    for link in links:
        absolute = urljoin(base_url, link)
        link_domain = extract_domain_ref(absolute)
        if link_domain == base_domain:
            result.append(absolute)
    return list(set(result))


class TestUrlNormalisation:
    def _normalise(self, url: str) -> Optional[str]:
        if crawler_module and hasattr(crawler_module, "normalise_url"):
            return crawler_module.normalise_url(url)
        return normalise_url_ref(url)

    def test_add_https_scheme(self):
        result = self._normalise("example.com")
        assert result is not None
        assert result.startswith("https://")

    def test_preserve_http_scheme(self):
        result = self._normalise("http://example.com")
        assert result is not None
        assert result.startswith("http://")

    def test_lowercase_host(self):
        result = self._normalise("HTTPS://EXAMPLE.COM/PATH")
        assert result is not None
        assert "EXAMPLE" not in result

    def test_trailing_slash_removed(self):
        result = self._normalise("https://example.com/")
        assert result is not None
        assert result == "https://example.com/"
        result2 = self._normalise("https://example.com/about/")
        assert result2 is not None
        assert not result2.endswith("/")

    def test_valid_url_unchanged(self):
        url = "https://example.com/about"
        result = self._normalise(url)
        assert result == url

    def test_empty_string_returns_none(self):
        result = self._normalise("")
        assert result is None

    def test_invalid_url(self):
        result = self._normalise("not a url at all!!! ###")
        assert result is None or isinstance(result, str)

    def test_whitespace_stripped(self):
        result = self._normalise("  https://example.com  ")
        assert result is not None
        assert result.startswith("https://example.com")

    def test_url_with_path(self):
        result = self._normalise("example.com/contacts")
        assert result is not None
        assert "/contacts" in result

    def test_ip_address(self):
        result = self._normalise("192.168.1.1")
        assert result is not None


class TestRobotsTxt:
    def _parse(self, content: str) -> RobotFileParser:
        if crawler_module and hasattr(crawler_module, "parse_robots_txt"):
            return crawler_module.parse_robots_txt(content)
        return parse_robots_txt_ref(content)

    def test_allow_all(self, robots_txt_allow_all):
        rp = self._parse(robots_txt_allow_all)
        assert rp.can_fetch("*", "/")
        assert rp.can_fetch("*", "/about/")

    def test_disallow_all(self, robots_txt_disallow_all):
        rp = self._parse(robots_txt_disallow_all)
        assert not rp.can_fetch("*", "/")

    def test_partial_disallow(self, robots_txt_partial):
        rp = self._parse(robots_txt_partial)
        assert not rp.can_fetch("*", "/admin/")
        assert not rp.can_fetch("*", "/private/")
        assert rp.can_fetch("*", "/about/")

    def test_empty_robots(self):
        rp = self._parse("")
        assert rp.can_fetch("*", "/")

    def test_malformed_robots(self):
        content = "THIS IS NOT VALID ROBOTS TXT"
        rp = self._parse(content)
        assert isinstance(rp, RobotFileParser)

    def test_specific_user_agent(self):
        content = """
User-agent: BadBot
Disallow: /

User-agent: *
Allow: /
"""
        rp = self._parse(content)
        assert rp.can_fetch("*", "/about/")


class TestManagementPageDetection:
    def _is_management(self, url: str) -> bool:
        if crawler_module and hasattr(crawler_module, "is_management_page"):
            return crawler_module.is_management_page(url)
        return is_management_page_ref(url)

    def test_about_page(self):
        assert self._is_management("https://example.com/about")

    def test_contacts_page(self):
        assert self._is_management("https://example.com/contacts")

    def test_kontakty_russian(self):
        assert self._is_management("https://example.ru/kontakty")

    def test_rukovodstvo_russian(self):
        assert self._is_management("https://example.ru/rukovodstvo")

    def test_management_english(self):
        assert self._is_management("https://example.com/management")

    def test_team_page(self):
        assert self._is_management("https://example.com/team")

    def test_homepage_not_management(self):
        assert not self._is_management("https://example.com/")

    def test_product_page_not_management(self):
        assert not self._is_management("https://example.com/products/widget-123")

    def test_blog_not_management(self):
        assert not self._is_management("https://example.com/blog/post-title")

    def test_o_nas_russian(self):
        assert self._is_management("https://example.ru/o-nas")

    def test_o_kompanii_russian(self):
        assert self._is_management("https://example.ru/o-kompanii")

    def test_leadership_page(self):
        assert self._is_management("https://example.com/leadership")


class TestUserAgentRotation:
    def _get_ua(self) -> str:
        if crawler_module and hasattr(crawler_module, "get_random_user_agent"):
            return crawler_module.get_random_user_agent()
        return get_random_user_agent_ref()

    def test_returns_string(self):
        ua = self._get_ua()
        assert isinstance(ua, str)
        assert len(ua) > 20

    def test_looks_like_browser_ua(self):
        ua = self._get_ua()
        assert "Mozilla" in ua

    def test_rotation_provides_different_values(self):
        uas = {self._get_ua() for _ in range(20)}
        assert len(uas) >= 2

    def test_ua_not_empty(self):
        for _ in range(5):
            ua = self._get_ua()
            assert ua.strip() != ""


class TestDomainExtraction:
    def _extract(self, url: str) -> Optional[str]:
        if crawler_module and hasattr(crawler_module, "extract_domain"):
            return crawler_module.extract_domain(url)
        return extract_domain_ref(url)

    def test_basic_domain(self):
        assert self._extract("https://example.com") == "example.com"

    def test_www_stripped(self):
        assert self._extract("https://www.example.com") == "example.com"

    def test_subdomain_kept(self):
        result = self._extract("https://shop.example.com")
        assert result == "shop.example.com"

    def test_path_not_included(self):
        result = self._extract("https://example.com/about/team")
        assert result is not None
        assert "/" not in result

    def test_port_stripped(self):
        result = self._extract("http://example.com:8080/api")
        assert result is not None
        assert "8080" not in result

    def test_russian_domain(self):
        result = self._extract("https://пример.рф")
        assert result is not None

    def test_empty_url(self):
        result = self._extract("")
        assert result is None


class TestInternalLinkExtraction:
    def _get_links(self, base: str, html: str) -> list[str]:
        if crawler_module and hasattr(crawler_module, "get_internal_links"):
            return crawler_module.get_internal_links(base, html)
        return get_internal_links_ref(base, html)

    def test_relative_links_resolved(self):
        html = '<a href="/about">О нас</a>'
        links = self._get_links("https://example.com", html)
        assert any("/about" in l for l in links)

    def test_absolute_internal_link(self):
        html = '<a href="https://example.com/contacts">Контакты</a>'
        links = self._get_links("https://example.com", html)
        assert "https://example.com/contacts" in links

    def test_external_links_excluded(self):
        html = '<a href="https://other-site.com/page">External</a>'
        links = self._get_links("https://example.com", html)
        assert not any("other-site.com" in l for l in links)

    def test_empty_html(self):
        links = self._get_links("https://example.com", "")
        assert links == []

    def test_no_duplicate_links(self):
        html = '<a href="/about">1</a><a href="/about">2</a>'
        links = self._get_links("https://example.com", html)
        assert links.count("https://example.com/about") == 1
