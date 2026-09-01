[Back to README](../README.md) · [Конфигурация →](configuration.md)

# Быстрый старт

## Предварительные требования

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose (v2, команда `docker compose`)
- Для локальной разработки без Docker: Python 3.12+ и [uv](https://docs.astral.sh/uv/)

## Запуск через Docker (рекомендуется)

```bash
cp .env.example .env
docker compose up -d --build
```

Поднимутся 4 сервиса: `app` (FastAPI на порту 8000), `postgres`, `redis`, `qdrant`.

Проверить, что всё работает:

```bash
curl http://localhost:8000/health
# {"status":"ok"}

docker compose ps
# app и postgres должны быть в статусе "healthy"
```

Логи приложения (структурированный формат `key=value`):

```bash
docker compose logs -f app
```

Остановить стек:

```bash
docker compose down
```

## Локальный запуск без Docker

Полезно для быстрой разработки — БД/Redis/Qdrant всё равно нужны отдельно
(например, через `docker compose up -d postgres redis qdrant`).

```bash
uv sync
cp .env.example .env
# отредактируйте .env — хосты postgres/redis/qdrant заменить на localhost
uv run uvicorn app.main:app --reload
```

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

## Следующие шаги

Дальнейшие возможности (БД, диалоги с LLM, RAG, ...) появляются
поэтапно — см. [Roadmap](../.ai-factory/ROADMAP.md).

## See Also

- [Конфигурация](configuration.md) — переменные окружения
- [БД и миграции](db.md) — engine/session, Alembic, тесты через Docker
- [Модуль dialog](dialog.md) — первый доменный модуль
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — структура проекта
