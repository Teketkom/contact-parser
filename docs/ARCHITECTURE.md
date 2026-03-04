# ARCHITECTURE.md — Архитектура системы «Парсер контактной информации»

**Шифр:** ПАРСЕР.АРХ.001  
**Версия:** 1.0  
**Дата:** 04.03.2026  

---

## 1. Обзор архитектуры

Система реализована по **трёхуровневой клиент-серверной архитектуре** с разделением на:

1. **Фронтенд** — React-приложение (SPA), работающее в браузере пользователя
2. **Бэкенд** — FastAPI-сервис, реализующий бизнес-логику парсинга
3. **Внешние сервисы** — LLM-провайдеры (OpenAI, GigaChat) и браузерный движок (Playwright/Chromium)

---

## 2. Детальный поток данных

### 2.1 Основной конвейер обработки

```
1. URL Нормализация
2. Blacklist Check
3. Robots.txt Проверка
4. Page Discovery
5. Rendering (Crawler)
6. Section Detection
7. Extraction (Variant A / Variant B)
8. Post-Processing
9. Excel Export
```

### 2.2 Логика выбора варианта извлечения

```
VARIANT A (регекс/DOM) → если Precision < 80% или Recall < 70% → VARIANT B (LLM fallback)
```

---

## 3. Описание ключевых модулей

### 3.1 crawler.py

**Ответственность:** загрузка и рендеринг веб-страниц.

- `CrawlerConfig` — конфиг
- `RobotsChecker` — проверка robots.txt
- `PageRenderer` — рендеринг (Playwright / aiohttp)
- `SiteCrawler` — главный класс

### 3.2 extractor.py

**Ответственность:** извлечение контактных данных из HTML.

- `VariantAExtractor` — regex/DOM
- `VariantBExtractor` — LLM
- `AutoExtractor` — автовыбор A/B

### 3.3 llm_client.py

**Ответственность:** взаимодействие с LLM-провайдерами.

- `OpenAIClient` — GPT-4o-mini
- `GigaChatClient` — резервный
- `LLMClientFactory` — фабрика

### 3.4 task_manager.py

**Ответственность:** управление жизненным циклом задач.

- `TaskStatus`: PENDING → RUNNING → DONE / FAILED
- `TaskManager`: очередь AsyncIO

---

## 4. Схема данных

```python
class Contact(BaseModel):
    fio: str | None = None
    position: str | None = None
    email: str | None = None
    phone: str | None = None
    inn: str | None = None
    kpp: str | None = None
    source_url: str
    confidence: float = 1.0
    variant_used: str = "A"
```

---

## 5. Инфраструктура

### Требования к серверу

| Параметр | Минимум | Рекомендуется |
|---|---|---|
| CPU | 2 ядра | 4 ядра |
| RAM | 2 ГБ | 4 ГБ |
| Диск | 10 ГБ | 20 ГБ |
| ОС | Ubuntu 22.04+ | Ubuntu 22.04 LTS |

---

*ПАРСЕР.АРХ.001 v1.0 · contact-parser · 04.03.2026*
