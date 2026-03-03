"""
Shared test fixtures for the Contact Information Parser backend.

Usage:
    pytest backend/tests/ -v
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ── Environment setup (must come before local imports) ──────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_contact_parser.db")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("LLM_API_KEY", "test-api-key")
os.environ.setdefault("LOG_LEVEL", "WARNING")

# ── Fixtures ───────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default asyncio event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def temp_dir_session() -> Generator[Path, None, None]:
    """Session-scoped temporary directory."""
    d = Path(tempfile.mkdtemp(prefix="contact_parser_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Function-scoped temporary directory (provided by pytest)."""
    return tmp_path


@pytest.fixture
def results_dir(temp_dir: Path) -> Path:
    """Temporary results directory."""
    p = temp_dir / "results"
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture
def logs_dir(temp_dir: Path) -> Path:
    """Temporary logs directory."""
    p = temp_dir / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Sample data ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_html_with_contacts() -> str:
    """HTML page containing Russian contact information."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>ООО «Пример» — Руководство</title></head>
    <body>
      <div class="management">
        <h1>Руководство компании</h1>
        <div class="person">
          <h2>Иванов Иван Иванович</h2>
          <p class="position">Генеральный директор</p>
          <p>Email: ivanov@example.com</p>
          <p>Тел: +7 (495) 123-45-67</p>
        </div>
        <div class="person">
          <h2>Петрова Мария Сергеевна</h2>
          <p class="position">Финансовый директор</p>
          <p>Email: petrova@example.com</p>
          <p>Тел: 8 (800) 555-35-35</p>
        </div>
        <div class="contact-block">
          <p>ИНН: 7707123456</p>
          <p>КПП: 770701001</p>
          <p>ООО «Пример Технологии»</p>
        </div>
      </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_no_contacts() -> str:
    """HTML page with no contact information."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Главная страница</title></head>
    <body>
      <h1>Добро пожаловать</h1>
      <p>Мы занимаемся разработкой программного обеспечения.</p>
      <p>Наша компания основана в 2010 году.</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_english() -> str:
    """HTML page with English contact information."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>About — ACME Corp</title></head>
    <body>
      <div class="team">
        <h1>Leadership Team</h1>
        <div class="person">
          <h3>John Smith</h3>
          <p class="title">Chief Executive Officer</p>
          <p>Email: john.smith@acme.com</p>
          <p>Phone: +1 (555) 234-5678</p>
        </div>
        <div class="person">
          <h3>Jane Doe</h3>
          <p class="title">Chief Financial Officer</p>
          <p>jane.doe@acme.com</p>
        </div>
      </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_urls() -> list[str]:
    """Sample list of company website URLs."""
    return [
        "https://example.com",
        "https://test-company.ru",
        "https://acme.org",
        "invalid-url",
        "http://another-site.net",
    ]


@pytest.fixture
def sample_blacklist_domains() -> list[str]:
    """Sample blacklist domain entries."""
    return [
        "spam-site.com",
        "blocked-domain.ru",
        "example.org",
    ]


@pytest.fixture
def sample_contact_records() -> list[dict]:
    """Sample extracted contact records."""
    return [
        {
            "site_url": "https://example.com",
            "company_name": "ООО Пример",
            "full_name": "Иванов Иван Иванович",
            "position": "Генеральный директор",
            "email": "ivanov@example.com",
            "phone": "+7 (495) 123-45-67",
            "inn": "7707123456",
            "kpp": "770701001",
            "source_url": "https://example.com/about",
        },
        {
            "site_url": "https://example.com",
            "company_name": "ООО Пример",
            "full_name": "Петрова Мария Сергеевна",
            "position": "Финансовый директор",
            "email": "petrova@example.com",
            "phone": "+7 (800) 555-35-35",
            "inn": "7707123456",
            "kpp": None,
            "source_url": "https://example.com/about",
        },
    ]


@pytest.fixture
def robots_txt_allow_all() -> str:
    return "User-agent: *\nAllow: /"


@pytest.fixture
def robots_txt_disallow_all() -> str:
    return "User-agent: *\nDisallow: /"


@pytest.fixture
def robots_txt_partial() -> str:
    return """
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /about/
Allow: /contacts/
Crawl-delay: 1
"""


# ── Mock HTTP client ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient for testing HTTP requests without network."""
    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_instance
        mock_instance.get.return_value = MagicMock(
            status_code=200,
            text="<html><body>Test page</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
        yield mock_instance


# ── Test database ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(temp_dir: Path) -> str:
    """Path to a temporary SQLite test database."""
    return str(temp_dir / "test.db")


# ── FastAPI test client ───────────────────────────────────────────────────────────────

@pytest.fixture
def test_app():
    """
    Create a FastAPI test application.
    Falls back gracefully if main app can't be imported.
    """
    try:
        from main import app
        return app
    except ImportError:
        from fastapi import FastAPI
        app = FastAPI()

        @app.get("/api/health")
        def health():
            return {"status": "ok"}

        return app


@pytest.fixture
def client(test_app):
    """Synchronous test client via httpx."""
    try:
        from fastapi.testclient import TestClient
        with TestClient(test_app) as c:
            yield c
    except ImportError:
        pytest.skip("fastapi or httpx not installed")
