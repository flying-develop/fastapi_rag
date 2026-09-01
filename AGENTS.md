# AGENTS.md

> Поддерживай этот файл в актуальном состоянии по мере роста
> структуры проекта.

## Обзор проекта

Учебный перенос AI-сервиса с Laravel (`~/projects/kwork/ai-app`) на
FastAPI + LangChain/LangGraph: диалоги с LLM, RAG по статьям, конвейер
обработки задач и модерация контента. Подробности — в
`.ai-factory/DESCRIPTION.md`.

## Технологический стек

- **Язык:** Python 3.12+
- **Веб-фреймворк:** FastAPI
- **AI-оркестрация:** LangChain + LangGraph
- **База данных:** PostgreSQL
- **ORM/миграции:** SQLAlchemy 2.0 (async) + Alembic
- **Векторная БД:** Qdrant
- **Фоновые задачи:** ARQ + Redis
- **Управление пакетами:** uv
- **Окружение разработки:** Docker / docker-compose

## Структура проекта

В процессе вехи «Фундамент работы с БД» (см. `.ai-factory/ROADMAP.md`,
план `db-foundation-sqlalchemy-alembic`). Целевая архитектура —
Structured Modules (Technical Layer), подробности в
`.ai-factory/ARCHITECTURE.md`; `app/modules/` пока пустой — домены
(dialog, rag, tasks, moderation, files) появятся на следующих вехах,
начиная с `dialog` (следующий план этой же вехи).

```
app/
├── main.py                    # точка входа FastAPI, /health, проверка БД в lifespan
├── modules/                   # доменные модули (пока пусто, см. ARCHITECTURE.md)
└── infrastructure/
    ├── config.py               # Settings (pydantic-settings), get_settings()
    ├── logging.py               # setup_logging(), структурированный key=value формат
    └── db.py                    # async engine/session, Base, get_db()
migrations/                    # Alembic (async), env.py читает DATABASE_URL из Settings
tests/
└── infrastructure/
    └── test_db.py               # тесты engine/session на реальном Postgres из Docker
alembic.ini                    # конфиг Alembic (URL переопределяется в migrations/env.py)
Dockerfile                     # образ приложения (uv, python:3.12-slim)
docker-compose.yml             # app + postgres + redis + qdrant
.env.example                   # шаблон переменных окружения
```

## Ключевые точки входа

| Файл | Назначение |
|------|------------|
| `app/main.py` | FastAPI-приложение, lifespan (логирование + проверка БД при старте), `/health` |
| `app/infrastructure/config.py` | Настройки приложения (`Settings`, `get_settings()`) |
| `app/infrastructure/logging.py` | Структурированное логирование (`setup_logging()`) |
| `app/infrastructure/db.py` | Async engine/session (`Base`, `get_db()`) |
| `migrations/env.py` | Настройка Alembic: URL из `Settings`, `target_metadata = Base.metadata` |
| `docker-compose.yml` | Локальное окружение: app + PostgreSQL + Redis + Qdrant |

## Тесты и миграции — только через Docker

- Тесты: `docker compose up -d postgres`, затем
  `docker compose run --rm app uv run pytest` (реальная БД, без моков).
- Миграции: `docker compose run --rm app uv run alembic upgrade head`
  (или `downgrade <rev>`). Для генерации новой ревизии на хосте нужен
  bind-mount `migrations/`, иначе файл создастся только внутри
  одноразового контейнера и пропадёт вместе с ним:
  `docker compose run --rm -v "$(pwd)/migrations:/srv/app/migrations" app uv run alembic revision --autogenerate -m "<message>"`.

## Документация

| Документ | Путь | Описание |
|----------|------|----------|
| README | `README.md` | Лендинг-страница проекта |
| Быстрый старт | `docs/getting-started.md` | Установка, запуск через Docker и локально |
| Конфигурация | `docs/configuration.md` | Переменные окружения |
| БД и миграции | `docs/db.md` | Async SQLAlchemy engine/session, Alembic, тесты через Docker |
| ARCHITECTURE | `.ai-factory/ARCHITECTURE.md` | Архитектурный паттерн, структура папок, примеры кода |
| DESCRIPTION | `.ai-factory/DESCRIPTION.md` | Спецификация проекта, стек, архитектурные заметки |
| Roadmap | `.ai-factory/ROADMAP.md` | Вехи переноса с Laravel |
| Базовые правила | `.ai-factory/rules/base.md` | Конвенции именования, структура модулей, обработка ошибок |

## AI Context Files

| Файл | Назначение |
|------|------------|
| AGENTS.md | Структурная карта проекта для AI-агентов (этот файл) |
| .ai-factory/DESCRIPTION.md | Спецификация проекта и стек |
| .ai-factory/ARCHITECTURE.md | Архитектура: Structured Modules (Technical Layer) — структура папок, правила зависимостей, примеры кода |
| .ai-factory/rules/base.md | Конвенции именования, структура модулей, обработка ошибок |
| .ai-factory/config.yaml | Конфигурация AI Factory для проекта |

## Правила для агента

- Разбивай составные shell-команды на отдельные шаги вместо
  объединения через `&&`.
  - Неправильно: `git checkout main && git pull`
  - Правильно: сначала `git checkout main`, затем `git pull origin main`
- Проект без git (`.git` отсутствует) — ветки не создаются, все
  изменения делаются напрямую в рабочей директории.
- Локальное окружение (БД, Redis, Qdrant, сам сервис) поднимается
  через Docker / docker-compose, а не напрямую на хосте.
