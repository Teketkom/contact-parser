"""
Модуль конфигурации приложения.
Загружает параметры из переменных окружения и .env файла.
Настроен для работы с Perplexity API (Вариант B / AI mode).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM (Perplexity API) ─────────────────────────────────────────────────
    LLM_PROVIDER: str = Field(
        default="perplexity",
        description="Провайдер LLM: perplexity | openai | gigachat | qwen",
    )
    LLM_API_KEY: Optional[str] = Field(
        default=None,
        description="API-ключ для выбранного провайдера LLM",
    )
    LLM_MODEL: str = Field(
        default="sonar",
        description="Название модели для вызовов LLM",
    )
    LLM_BASE_URL: str = Field(
        default="https://api.perplexity.ai",
        description="Базовый URL для OpenAI-совместимого API",
    )
    LLM_TIMEOUT: float = Field(
        default=300.0,
        description="Тайм-аут запроса к LLM (секунды)",
    )
    LLM_MAX_TOKENS_PER_REQUEST: int = Field(
        default=4096,
        description="Максимум токенов на один запрос к LLM",
    )
    LLM_SESSION_TOKEN_BUDGET: int = Field(
        default=1_000_000,
        description="Суммарный бюджет токенов на сессию парсинга",
    )

    # ── GigaChat specific ────────────────────────────────────────────────────
    GIGACHAT_SCOPE: str = Field(
        default="GIGACHAT_API_PERS",
        description="Область видимости GigaChat API",
    )
    GIGACHAT_VERIFY_SSL: bool = Field(
        default=False,
        description="Проверять SSL-сертификат GigaChat",
    )

    # ── Crawler ──────────────────────────────────────────────────────────────
    MAX_CONCURRENT_BROWSERS: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Максимальное число одновременных браузерных контекстов",
    )
    REQUEST_DELAY_MIN: float = Field(
        default=1.0,
        ge=0.0,
        description="Минимальная задержка между запросами (секунды)",
    )
    REQUEST_DELAY_MAX: float = Field(
        default=5.0,
        ge=0.0,
        description="Максимальная задержка между запросами (секунды)",
    )
    MAX_PAGES_PER_SITE: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Максимальное число страниц, просматриваемых на одном сайте",
    )
    PAGE_TIMEOUT: int = Field(
        default=30000,
        ge=5_000,
        le=120_000,
        description="Тайм-аут загрузки страницы (миллисекунды)",
    )
    PROXY_URL: Optional[str] = Field(
        default=None,
        description="URL прокси-сервера (например http://user:pass@host:port)",
    )
    RESPECT_ROBOTS_TXT: bool = Field(
        default=True,
        description="Соблюдать правила robots.txt",
    )
    HEADLESS: bool = Field(
        default=True,
        description="Запускать браузер в headless-режиме",
    )

    # ── Storage ──────────────────────────────────────────────────────────────
    RESULTS_DIR: Path = Field(
        default=Path("Результаты_парсинга"),
        description="Корневая директория для сохранения результатов",
    )
    TASKS_STATE_FILE: Path = Field(
        default=Path("tasks_state.json"),
        description="Файл хранения состояния задач для восстановления после перезапуска",
    )

    # ── API ───────────────────────────────────────────────────────────────────
    API_HOST: str = Field(default="0.0.0.0", description="Хост FastAPI-сервера")
    API_PORT: int = Field(default=8000, description="Порт FastAPI-сервера")
    DEBUG: bool = Field(default=False, description="Режим отладки")
    CORS_ORIGINS: list[str] = Field(
        default=["*"],
        description="Список разрешённых CORS-источников",
    )

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")
    LOG_FORMAT: str = Field(
        default="text",
        description="Формат логов: text | json",
    )

    @field_validator("REQUEST_DELAY_MAX")
    @classmethod
    def validate_delay_max(cls, v: float, info) -> float:
        """Максимальная задержка должна быть не меньше минимальной."""
        min_val = info.data.get("REQUEST_DELAY_MIN", 1.0)
        if v < min_val:
            raise ValueError(
                f"REQUEST_DELAY_MAX ({v}) должен быть >= REQUEST_DELAY_MIN ({min_val})"
            )
        return v

    @field_validator("RESULTS_DIR", mode="before")
    @classmethod
    def make_results_dir(cls, v) -> Path:
        """Преобразует строку в Path."""
        return Path(v)

    @field_validator("TASKS_STATE_FILE", mode="before")
    @classmethod
    def make_state_file(cls, v) -> Path:
        """Преобразует строку в Path."""
        return Path(v)


# Синглтон настроек
settings = Settings()
