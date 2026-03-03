"""
Точка входа FastAPI-приложения.
Настраивает CORS, монтирует роутеры, управляет жизненным циклом Playwright.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import settings
from app.core.task_manager import task_manager

# ── Логирование ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Жизненный цикл приложения ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Управляет запуском и остановкой ресурсов:
    - Playwright браузер
    - Менеджер задач
    """
    logger.info("Запуск Contact Parser Backend...")

    # Создаём директорию результатов
    settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Директория результатов: %s", settings.RESULTS_DIR.resolve())

    # Инициализируем менеджер задач (восстанавливает состояние после перезапуска)
    await task_manager.startup()
    logger.info("Менеджер задач инициализирован.")

    # Инициализируем пул браузеров Playwright
    from app.core.crawler import browser_pool
    await browser_pool.startup()
    logger.info(
        "Playwright запущен (max_browsers=%d, headless=%s)",
        settings.MAX_CONCURRENT_BROWSERS,
        settings.HEADLESS,
    )

    yield  # Приложение работает

    # Завершение работы
    logger.info("Остановка Contact Parser Backend...")

    await browser_pool.shutdown()
    logger.info("Playwright остановлен.")

    await task_manager.shutdown()
    logger.info("Менеджер задач остановлен.")


# ── Создание приложения ────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Создаёт и конфигурирует экземпляр FastAPI."""
    application = FastAPI(
        title="Contact Parser API",
        description=(
            "API для автоматического сбора контактной информации с сайтов компаний. "
            "Поддерживает парсинг имён, должностей, email, телефонов, ИНН/КПП "
            "с экспортом в Excel."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Монтируем основной роутер
    application.include_router(router)

    # Обработчики ошибок
    @application.exception_handler(404)
    async def not_found_handler(request, exc):
        return JSONResponse(
            status_code=404,
            content={"еррор": "Ресурс не найден", "detail": str(exc)},
        )

    @application.exception_handler(500)
    async def internal_error_handler(request, exc):
        logger.exception("Необработанная ошибка сервера: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"еррор": "Внутренняя ошибка сервера", "detail": str(exc)},
        )

    return application


app = create_app()


# ── Корневые маршруты ────────────────────────────────────────────────────────────

@app.get("/", tags=["Система"])
async def root() -> dict:
    """Проверка работоспособности API."""
    return {
        "service": "Contact Parser API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Система"])
async def health() -> dict:
    """Эндпоинт проверки здоровья сервиса."""
    from app.core.crawler import browser_pool
    return {
        "status": "healthy",
        "browser_pool": {
            "active": browser_pool.active_count,
            "max": settings.MAX_CONCURRENT_BROWSERS,
        },
        "tasks": {
            "total": len(task_manager.tasks),
            "running": sum(
                1 for t in task_manager.tasks.values()
                if t.status.value == "running"
            ),
        },
    }


# ── Запуск напрямую ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
