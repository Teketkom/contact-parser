# API.md — Документация REST API

**Шифр:** ПАРСЕР.АПИ.001  
**Версия:** 1.0  
**Дата:** 04.03.2026  
**Base URL:** `http://localhost:8000`  

---

## Аутентификация

По умолчанию отключена. Для включения — `API_KEY` в env, затем `X-API-Key: <key>` в запросах.

---

## Эндпоинты

### GET /health

```json
{
  "status": "ok",
  "version": "2.0.0",
  "playwright": "available",
  "llm": {"openai": "available", "gigachat": "available"},
  "uptime_seconds": 3600
}
```

### POST /api/v1/tasks

Создать задачу парсинга.

```json
// Тело запроса:
{
  "mode": 1,
  "urls": ["https://company1.ru", "https://company2.ru"],
  "target_positions": ["Директор", "CEO"],
  "variant": "AUTO"
}

// Ответ 201:
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "mode": 1,
  "urls_count": 2
}
```

### GET /api/v1/tasks/{task_id}

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "stats": {
    "total_urls": 10,
    "processed_urls": 9,
    "total_contacts": 23,
    "precision_estimate": 0.87,
    "recall_estimate": 0.74
  },
  "results": [
    {
      "fio": "Иванов Иван Иванович",
      "position": "Генеральный директор",
      "email": "ivanov@company1.ru",
      "phone": "+79001234567",
      "inn": "7701234567",
      "kpp": "770101001",
      "source_url": "https://company1.ru/contacts",
      "confidence": 0.95,
      "variant_used": "A"
    }
  ],
  "export_url": "/api/v1/tasks/550e8400.../export"
}
```

### GET /api/v1/tasks/{task_id}/export

Скачать результаты в формате .xlsx.

```bash
curl -OJ http://localhost:8000/api/v1/tasks/{task_id}/export
```

### DELETE /api/v1/tasks/{task_id}

Удалить задачу и связанный Excel-файл.

### POST /api/v1/tasks/upload

Создать задачу с загрузкой Excel-файла (multipart/form-data).

```bash
curl -X POST http://localhost:8000/api/v1/tasks/upload \
  -F "file=@companies.xlsx" \
  -F "mode=1" \
  -F 'target_positions=["Директор"]'
```

---

## Ограничения

| Ограничение | Значение |
|---|---|
| Максимум URL за запрос | 10 000 |
| Максимум размер Excel-файла | 10 МБ |
| Время хранения результатов | 24 часа |

**Swagger UI:** http://localhost:8000/docs  
**ReDoc:** http://localhost:8000/redoc

---

*ПАРСЕР.АПИ.001 v1.0 · contact-parser · 04.03.2026*
