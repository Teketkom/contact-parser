# TESTING.md — Стратегия тестирования

**Шифр:** ПАРСЕР.ТСТ.001  
**Версия:** 1.0  
**Дата:** 04.03.2026  

---

## 1. Цели тестирования

| Цель | Метрика | Целевое значение |
|---|---|---|
| Корректность извлечения | Precision | ≥ 80% |
| Полнота извлечения | Recall | ≥ 70% |
| Надёжность | Покрытие кода | ≥ 70% |
| Производительность | Время/сайт | ≤ 30 сек |

---

## 2. Инструменты

| Инструмент | Назначение |
|---|---|
| `pytest` | Основной фреймворк |
| `pytest-asyncio` | Поддержка asyncio |
| `pytest-cov` | Покрытие кода |
| `respx` | Мок HTTP |
| `fastapi.testclient` | Интеграционные тесты |

---

## 3. Запуск тестов

```bash
cd backend

# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ --cov=app --cov-report=html

# Только unit-тесты
pytest -m unit

# Только интеграционные
pytest -m integration
```

---

## 4. Структура тестов

```
backend/tests/
├── conftest.py            # Общие фикстуры
├── test_extractor.py     # Тесты Variant A & B
├── test_crawler.py       # URL нормализация, robots.txt
├── test_exporter.py      # Excel-экспорт
├── test_blacklist.py     # Проверка чёрного списка
└── test_api.py            # API-эндпоинты
```

---

*ПАРСЕР.ТСТ.001 v1.0 · contact-parser · 04.03.2026*
