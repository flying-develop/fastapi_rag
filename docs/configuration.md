[← Быстрый старт](getting-started.md) · [Back to README](../README.md) · [БД и миграции →](db.md)

# Конфигурация

Все настройки читаются из переменных окружения (`.env` в корне проекта,
см. `.env.example`) через `app/infrastructure/config.py`
(`Settings`, pydantic-settings).

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `APP_NAME` | `ai-app-python` | Имя приложения (используется как заголовок FastAPI) |
| `LOG_LEVEL` | `DEBUG` | Уровень логирования (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `DATABASE_URL` | `postgresql+asyncpg://projects:projects@postgres:5432/ai_app` | Строка подключения к PostgreSQL (используется начиная с вехи «Фундамент работы с БД») |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `projects` / `projects` / `ai_app` | Учётные данные для контейнера `postgres`; должны совпадать с `DATABASE_URL` |
| `REDIS_URL` | `redis://redis:6379/0` | Подключение к Redis (используется начиная с вехи фоновых задач) |
| `QDRANT_URL` | `http://qdrant:6333` | Подключение к Qdrant (используется начиная с вех RAG) |
| `OPENAI_API_KEY` | — (пусто) | Ключ OpenAI (используется начиная с вехи «Диалоги с LLM») |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Название chat-модели OpenAI — см. [Диалоги с LLM](dialog-chat.md) |

## Хосты в Docker vs локально

Значения по умолчанию в `.env.example` рассчитаны на запуск через
`docker compose` — хосты (`postgres`, `redis`, `qdrant`) совпадают с
именами сервисов в `docker-compose.yml`. Для запуска без Docker
замените их на `localhost` (с портами, под которыми сервисы
проброшены наружу).

## See Also

- [Быстрый старт](getting-started.md) — установка и запуск
- [БД и миграции](db.md) — как используется `DATABASE_URL`
- [Диалоги с LLM](dialog-chat.md) — `OPENAI_API_KEY`/`OPENAI_CHAT_MODEL`
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — где и как используется конфигурация
