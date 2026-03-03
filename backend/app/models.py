"""
Pydantic-модели данных приложения.
Определяет схемы для контактов, задач парсинга и результатов.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ── Перечисления ─────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    """Статус задачи парсинга."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ParseMode(int, Enum):
    """Режим парсинга."""
    SITES_WITH_TARGET_POSITIONS = 1  # Сайты + целевые должности
    SITES_ALL_POSITIONS = 2          # Сайты + все должности
    AUTO_SEARCH = 3                  # Автопоиск компаний


class ExtractionVariant(str, Enum):
    """Вариант извлечения данных."""
    CLASSIC = "A"   # Регулярные выражения + DOM
    AI = "B"        # LLM-экстракция


class FallbackReason(str, Enum):
    """Причина переключения на резервный вариант извлечения."""
    LLM_TIMEOUT = "llm_timeout"
    LLM_HTTP_ERROR = "llm_http_error"
    TOKEN_BUDGET_EXHAUSTED = "token_budget_exhausted"
    LLM_UNAVAILABLE = "llm_unavailable"


# ── Контактные данные ──────────────────────────────────────────────────────────────

class SocialLinks(BaseModel):
    """Ссылки на социальные сети контакта."""
    vk: Optional[str] = None
    telegram: Optional[str] = None
    linkedin: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None
    ok: Optional[str] = None  # Одноклассники


class ContactRecord(BaseModel):
    """Запись о контакте, извлечённом с сайта компании."""

    # Компания
    company_name: Optional[str] = Field(None, description="Название компании")
    site_url: Optional[str] = Field(None, description="URL сайта компании")
    inn: Optional[str] = Field(None, description="ИНН организации (10 или 12 цифр)")
    kpp: Optional[str] = Field(None, description="КПП организации (9 цифр)")
    company_email: Optional[str] = Field(None, description="Общий email компании")

    # Должность
    position_raw: Optional[str] = Field(None, description="Должность как указана на сайте")
    position_normalized: Optional[str] = Field(None, description="Нормализованная должность из словаря")

    # Персона
    full_name: Optional[str] = Field(None, description="ФИО (Фамилия Имя Отчество)")
    personal_email: Optional[str] = Field(None, description="Личный email контакта")
    phone: Optional[str] = Field(None, description="Номер телефона в формате E.164")
    phone_raw: Optional[str] = Field(None, description="Номер телефона в исходном виде")

    # Соцсети
    social_links: SocialLinks = Field(default_factory=SocialLinks)

    # Метаданные страницы
    source_url: Optional[str] = Field(None, description="URL страницы-источника")
    page_language: Optional[str] = Field(None, description="Язык страницы (ISO 639-1)")
    scan_date: datetime = Field(default_factory=datetime.utcnow, description="Дата и время сканирования")

    # Статус и комментарии
    status: str = Field(default="ok", description="Статус записи")
    comment: Optional[str] = Field(None, description="Комментарий или причина ошибки")

    # Вариант извлечения
    extraction_variant: ExtractionVariant = Field(
        default=ExtractionVariant.CLASSIC,
        description="Вариант, которым были извлечены данные",
    )

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, v: Optional[str]) -> Optional[str]:
        """Проверяет формат ИНН (10 или 12 цифр)."""
        if v is not None:
            digits = v.strip()
            if not digits.isdigit() or len(digits) not in (10, 12):
                return None
        return v

    @field_validator("kpp")
    @classmethod
    def validate_kpp(cls, v: Optional[str]) -> Optional[str]:
        """Проверяет формат КПП (9 цифр)."""
        if v is not None:
            digits = v.strip()
            if not digits.isdigit() or len(digits) != 9:
                return None
        return v


# ── Входные данные задачи ────────────────────────────────────────────────────────────

class SiteEntry(BaseModel):
    """Запись о сайте для парсинга."""
    url: str = Field(..., description="URL сайта")
    company_name: Optional[str] = Field(None, description="Название компании (если известно)")
    inn: Optional[str] = Field(None, description="ИНН (если известен)")


class ParseTaskRequest(BaseModel):
    """Запрос на создание задачи парсинга."""
    mode: ParseMode = Field(..., description="Режим парсинга (1, 2 или 3)")
    variant: ExtractionVariant = Field(
        default=ExtractionVariant.CLASSIC,
        description="Вариант извлечения данных (A или B)",
    )
    target_positions: list[str] = Field(
        default_factory=list,
        description="Целевые должности для режима 1 (список строк)",
    )
    search_queries: list[str] = Field(
        default_factory=list,
        description="Поисковые запросы для режима 3",
    )
    sites: list[SiteEntry] = Field(
        default_factory=list,
        description="Список сайтов (используется когда файл не загружается)",
    )


# ── Прогресс и статус ──────────────────────────────────────────────────────────────

class TaskProgress(BaseModel):
    """Прогресс выполнения задачи парсинга."""
    total_sites: int = Field(default=0, description="Общее число сайтов")
    processed_sites: int = Field(default=0, description="Обработано сайтов")
    total_pages: int = Field(default=0, description="Всего страниц просмотрено")
    contacts_found: int = Field(default=0, description="Найдено контактов")
    errors: int = Field(default=0, description="Число ошибок")
    current_site: Optional[str] = Field(None, description="Текущий обрабатываемый сайт")
    current_page: Optional[str] = Field(None, description="Текущая обрабатываемая страница")
    percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Процент выполнения")
    elapsed_seconds: float = Field(default=0.0, description="Прошло секунд с начала")
    eta_seconds: Optional[float] = Field(None, description="Оставшееся время (оценка)")
    llm_tokens_used: int = Field(default=0, description="Использовано токенов LLM")
    fallback_count: int = Field(default=0, description="Число переключений на резервный вариант")


class ParseTask(BaseModel):
    """Задача парсинга контактов."""
    task_id: UUID = Field(default_factory=uuid4, description="Уникальный идентификатор задачи")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Текущий статус")
    mode: ParseMode = Field(..., description="Режим парсинга")
    variant: ExtractionVariant = Field(
        default=ExtractionVariant.CLASSIC,
        description="Вариант извлечения",
    )
    target_positions: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    sites: list[SiteEntry] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    progress: TaskProgress = Field(default_factory=TaskProgress)

    result_file: Optional[str] = Field(None, description="Путь к файлу результатов (.xlsx)")
    log_file: Optional[str] = Field(None, description="Путь к файлу логов ошибок")
    error_message: Optional[str] = Field(None, description="Сообщение об ошибке (если статус failed)")


class ParseResult(BaseModel):
    """Результат парсинга для одного сайта."""
    site_url: str
    company_name: Optional[str] = None
    contacts: list[ContactRecord] = Field(default_factory=list)
    pages_crawled: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    extraction_variant_used: ExtractionVariant = ExtractionVariant.CLASSIC
    fallback_events: list[dict[str, Any]] = Field(default_factory=list)


# ── WebSocket сообщения ──────────────────────────────────────────────────────────────

class WSMessageType(str, Enum):
    """Тип WebSocket-сообщения."""
    PROGRESS = "progress"
    LOG = "log"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class WSMessage(BaseModel):
    """WebSocket-сообщение о прогрессе задачи."""
    type: WSMessageType
    task_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Ответы API ──────────────────────────────────────────────────────────────────

class TaskResponse(BaseModel):
    """Ответ API при создании/получении задачи."""
    task_id: str
    status: TaskStatus
    mode: ParseMode
    variant: ExtractionVariant
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress: TaskProgress
    result_file: Optional[str] = None
    log_file: Optional[str] = None
    error_message: Optional[str] = None


class BlacklistUploadResponse(BaseModel):
    """Ответ при загрузке файла чёрного списка."""
    added: int = Field(..., description="Добавлено новых записей")
    total: int = Field(..., description="Всего записей в чёрном списке")
    message: str


class ErrorResponse(BaseModel):
    """Стандартный ответ об ошибке."""
    error: str
    detail: Optional[str] = None
