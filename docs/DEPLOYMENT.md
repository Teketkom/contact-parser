# DEPLOYMENT.md — Руководство по развёртыванию

**Шифр:** ПАРСЕР.ДЕП.001  
**Версия:** 1.0  
**Дата:** 04.03.2026  

---

## 1. Требования

| Компонент | Минимум | Рекомендуется |
|---|---|---|
| CPU | 2 ядра | 4 ядра |
| RAM | 2 ГБ | 4 ГБ |
| Диск (SSD) | 10 ГБ | 20 ГБ |
| ОС | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS |
| Docker | 24.0+ | 24.0+ |
| Docker Compose | 2.20+ | 2.20+ |

---

## 2. Быстрый старт (Docker Compose)

```bash
# 1. Клонировать
git clone https://github.com/Teketkom/contact-parser.git
cd contact-parser

# 2. Настроить
cp .env.example .env
nano .env  # Указать OPENAI_API_KEY, GIGACHAT_CREDENTIALS

# 3. Запустить
docker compose up -d --build

# 4. Проверить
curl http://localhost:8000/health
```

**Доступные URL:**
| Сервис | URL |
|---|---|
| Фронтенд | http://localhost:3000 |
| API (Swagger) | http://localhost:8000/docs |
| Healthcheck | http://localhost:8000/health |

---

## 3. Обновление

```bash
git pull origin main
docker compose down
docker compose up -d --build
```

---

## 4. SSL/HTTPS

```bash
sudo certbot --nginx -d your-domain.ru
```

---

## 5. Устранение неполадок

```bash
# Playwright не запускается:
docker compose exec backend playwright install-deps chromium

# Задача зависла:
docker compose restart backend

# Нет места:
docker image prune -a -f
```

---

*ПАРСЕР.ДЕП.001 v1.0 · contact-parser · 04.03.2026*
