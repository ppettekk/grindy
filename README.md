# Grindy

Агрегатор подработки для подростков 14–18 лет. Telegram WebApp + бот.

Источники: hh.ru, SuperJob (по API), Авито и Работа.ру (парсинг, заглушки в MVP).
AI-модерация спама на Google Gemini.

## Стек

- Backend: Python 3.11, FastAPI, SQLAlchemy 2.x async, PostgreSQL, APScheduler
- Bot: aiogram 3.x
- Frontend: React 18 + Vite + TypeScript + TailwindCSS
- AI: Google Gemini (`gemini-2.5-flash`)

## Быстрый старт

1. Скопируй `.env.example` в `.env` и заполни ключи (`BOT_TOKEN`, `GEMINI_API_KEY`, опционально `SUPERJOB_API_KEY`, `HH_USER_AGENT`, `WEBAPP_URL`).
2. `docker compose up --build`
3. Backend: http://localhost:8000 (Swagger: `/docs`)
4. Frontend dev: http://localhost:5173
5. Бот стартует автоматически в контейнере `bot`.

## Структура

```
grindy/
├── backend/
│   ├── app/        # FastAPI + SQLAlchemy + парсеры + scheduler
│   └── bot/        # aiogram 3.x
├── frontend/       # React + Vite + Tailwind WebApp
├── docker-compose.yml
└── .env.example
```

## Локально без Docker

Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Bot:
```bash
cd backend
python -m bot.main
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Бэкап БД

В `docker-compose.yml` есть сервис `db-backup` (`prodrigestivill/postgres-backup-local`).
Он каждый день в 03:00 (Europe/Moscow) делает `pg_dump -Fc` и кладёт в `./backups/` на VPS.

**Ротация** (по умолчанию):
- 7 дневных
- 4 недельных
- 6 месячных
- старее удаляется автоматически

**Структура папки:**
```
backups/
├── daily/   grindy-20260506.sql.gz, ...
├── weekly/  grindy-2026-W18.sql.gz, ...
├── monthly/ grindy-202604.sql.gz, ...
└── last/    последний дамп каждой ротации (симлинками)
```

**Сделать бэкап вручную (вне расписания):**
```bash
docker compose exec -T db pg_dump -Fc -U grindy grindy | gzip > backups/manual-$(date +%F-%H%M).sql.gz
```

**Восстановление:**
```bash
# 1) останавливаем приложение, чтобы не было записей в БД
docker compose stop backend bot

# 2) дроп и пересоздание схемы
docker compose exec -T db psql -U grindy -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 3) распакуй .gz если архивирован, и восстанавливаем custom-формат:
gunzip -c backups/daily/grindy-20260506.sql.gz | docker compose exec -T db pg_restore -U grindy -d grindy --no-owner

# 4) поднимаем приложение
docker compose start backend bot
```

Папка `./backups/` подмонтирована на хост: её можно отдельно архивировать или копировать на другой сервер через `rsync`/`scp`.
Для загрузки в S3 добавь переменные `BACKUP_S3_*` и второй контейнер с `rclone`.

## Этапы

MVP в этом репозитории содержит скелет всех частей: модели, API, парсеры hh/SuperJob/Avito/Rabota.ru, AI-модерация, бот с онбордингом и расписанием рассылок, WebApp с лентой/деталями/фильтрами/сохранёнными/настройками, лендинг работодателей.
