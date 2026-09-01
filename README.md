# ai-app-python

> AI-сервис на FastAPI + LangChain/LangGraph: диалоги с LLM, RAG по
> статьям, модерация контента.

Сервис развивается поэтапно, от простого ядра к сложным сценариям.
Полное описание целей и вех — в
[.ai-factory/DESCRIPTION.md](.ai-factory/DESCRIPTION.md) и
[.ai-factory/ROADMAP.md](.ai-factory/ROADMAP.md).

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/health
# {"status":"ok"}
```

Подробности — в [docs/getting-started.md](docs/getting-started.md).

## Возможности (на текущем этапе)

- **FastAPI-приложение** — скелет с `/health`-эндпоинтом.
- **Конфигурация через переменные окружения** — `pydantic-settings`, единый `.env`.
- **Структурированное логирование** — уровень управляется `LOG_LEVEL`.
- **Локальное окружение в Docker** — `app` + PostgreSQL + Redis + Qdrant одной командой.
- **Async SQLAlchemy + Alembic** — engine/session (`app/infrastructure/db.py`), миграции — см. [docs/db.md](docs/db.md).
- **Модуль dialog** — первый доменный модуль (модель, репозиторий, схемы), паттерн для остальных модулей — см. [docs/dialog.md](docs/dialog.md).

Остальные возможности (диалоги с LLM, RAG, task pipeline, модерация)
появляются поэтапно — см. [roadmap](.ai-factory/ROADMAP.md).

## Пример

```bash
curl -i http://localhost:8000/health
```

```
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok"}
```

---

## Документация

| Раздел | Описание |
|--------|----------|
| [Быстрый старт](docs/getting-started.md) | Установка, запуск через Docker и локально |
| [Конфигурация](docs/configuration.md) | Переменные окружения |
| [БД и миграции](docs/db.md) | Async SQLAlchemy engine/session, Alembic-миграции, тесты через Docker |
| [Модуль dialog](docs/dialog.md) | Модель, репозиторий, схемы — первый доменный модуль |
| [Архитектура](.ai-factory/ARCHITECTURE.md) | Паттерн Structured Modules, структура папок, правила зависимостей |
| [Описание проекта](.ai-factory/DESCRIPTION.md) | Цели, стек, вехи |
| [Roadmap](.ai-factory/ROADMAP.md) | Вехи развития проекта |

## Лицензия

Личный проект, без формальной лицензии.
