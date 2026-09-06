# AGENTS.md

> Поддерживай этот файл в актуальном состоянии по мере роста
> структуры проекта.

## Обзор проекта

AI-сервис на FastAPI + LangChain/LangGraph: диалоги с LLM, RAG по
статьям, конвейер обработки задач и модерация контента. Подробности —
в `.ai-factory/DESCRIPTION.md`.

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

Целевая архитектура — Structured Modules (Technical Layer), подробности
в `.ai-factory/ARCHITECTURE.md`. `dialog` — первый доменный модуль, все
слои (`api/services/repositories/models/schemas`) задействованы и
задают паттерн для остальных; `files` — второй модуль по тому же
паттерну; RAG, tasks, moderation появятся на следующих вехах.

```
app/
├── main.py                    # точка входа FastAPI, /health, роутеры, exception handlers
├── modules/
│   └── dialog/                # первый доменный модуль (см. docs/dialog.md, docs/dialog-message.md, docs/dialog-chat.md)
│       ├── api/
│       │   └── router.py       # POST /dialogs/{id}/messages
│       ├── services/
│       │   ├── dialog_service.py  # DialogService.send_message — история → граф LangGraph → сохранить ответ
│       │   ├── graph.py            # build_dialog_graph() — LangGraph-граф диалога (узлы agent/tools, условное рёбро)
│       │   └── tools.py            # DIALOG_TOOLS — get_current_time, пример инструмента
│       ├── models/
│       │   ├── dialog.py       # Dialog(Base)
│       │   └── dialog_message.py  # DialogMessage(Base) — история сообщений
│       ├── repositories/
│       │   ├── dialog_repository.py  # DialogRepository — сквозной CRUD
│       │   └── dialog_message_repository.py  # DialogMessageRepository — append/list_by_dialog
│       ├── schemas/
│       │   ├── dialog.py       # DialogCreate/DialogUpdate/DialogRead
│       │   └── dialog_message.py  # DialogMessageCreate/Read (репозиторий) + CreateRequest/Response (API)
│       └── exceptions.py       # DialogNotFoundError
│   └── files/                  # второй доменный модуль (см. docs/files.md) — приём/хранение/парсинг файлов
│       ├── api/
│       │   └── router.py       # POST /files, GET /files/{id}, GET /files/{id}/metadata
│       ├── services/
│       │   ├── file_service.py    # FileService.upload_file/download_file/get_metadata — S3 + парсинг + метаданные в БД
│       │   └── file_parser.py     # parse_to_text() — PDF/DOCX/XLSX → текст, остальное игнорируется
│       ├── models/
│       │   └── file.py         # File(Base) — метаданные (filename, content_type, size_bytes, storage_key, extracted_text, parse_status)
│       ├── repositories/
│       │   └── file_repository.py  # FileRepository — create/get_by_id
│       ├── schemas/
│       │   └── file.py         # FileCreate (репозиторий) + FileResponse (API)
│       └── exceptions.py       # StoredFileNotFoundError (не FileNotFoundError — не затенять builtin)
└── infrastructure/
    ├── config.py               # Settings (pydantic-settings), get_settings()
    ├── logging.py               # setup_logging(), структурированный key=value формат
    ├── db.py                    # async engine/session, Base, get_db()
    ├── llm.py                   # get_chat_model(), execute_tool_calls(), invoke_with_tools() — переиспользуемый tool-calling паттерн
    └── s3.py                    # ensure_bucket_exists()/upload_file()/download_file() — async S3-клиент (aioboto3, MinIO локально)
migrations/                    # Alembic (async), env.py читает DATABASE_URL из Settings
tests/
├── conftest.py                # db_session fixture (транзакция + rollback между тестами)
├── infrastructure/
│   ├── test_db.py             # тесты engine/session на реальном Postgres из Docker
│   ├── test_llm.py            # тесты invoke_with_tools()/execute_tool_calls() — FakeChatModel из tests/modules/dialog/conftest.py
│   └── test_s3.py             # тесты S3-клиента на реальном MinIO из Docker
└── modules/
    ├── dialog/
    │   ├── conftest.py             # FakeChatModel — без реальных вызовов OpenAI, поддерживает bind_tools/responses
    │   ├── test_dialog_repository.py  # CRUD-тесты DialogRepository
    │   ├── test_dialog_message_repository.py  # тесты DialogMessageRepository
    │   ├── test_dialog_service.py     # тесты DialogService (реальная БД + фейковая LLM)
    │   ├── test_dialog_router.py      # тесты эндпоинта (httpx.AsyncClient + ASGITransport)
    │   ├── test_graph.py              # тесты build_dialog_graph() — agent/tools, многошаговый tool calling, FakeChatModel, без БД
    │   └── test_tools.py              # юнит-тесты get_current_time
    └── files/
        ├── test_file_parser.py      # тесты parse_to_text() — PDF/DOCX/XLSX генерируются в памяти, без БД/MinIO
        ├── test_file_repository.py  # CRUD-тесты FileRepository (реальная БД)
        ├── test_file_service.py     # тесты FileService (реальные MinIO + БД), включая парсинг при загрузке
        └── test_file_router.py      # тесты эндпоинтов (httpx.AsyncClient + ASGITransport, реальные MinIO + БД)
alembic.ini                    # конфиг Alembic (URL переопределяется в migrations/env.py)
Dockerfile                     # образ приложения (uv, python:3.12-slim)
docker-compose.yml             # app + postgres + redis + qdrant + minio
.env.example                   # шаблон переменных окружения
```

## Ключевые точки входа

| Файл | Назначение |
|------|------------|
| `app/main.py` | FastAPI-приложение, lifespan (логирование + проверка БД и S3-бакета при старте), `/health` |
| `app/infrastructure/config.py` | Настройки приложения (`Settings`, `get_settings()`) |
| `app/infrastructure/logging.py` | Структурированное логирование (`setup_logging()`) |
| `app/infrastructure/db.py` | Async engine/session (`Base`, `get_db()`) |
| `app/modules/dialog/repositories/dialog_repository.py` | `DialogRepository` — образец repository-паттерна для остальных модулей |
| `app/modules/dialog/repositories/dialog_message_repository.py` | `DialogMessageRepository` — история сообщений диалога |
| `app/modules/dialog/services/dialog_service.py` | `DialogService.send_message` — история → граф LangGraph → сохранить ответ |
| `app/modules/dialog/services/graph.py` | `build_dialog_graph()` — LangGraph-граф диалога (состояние `DialogState`, узлы `agent`/`tools`, условное рёбро) |
| `app/modules/dialog/api/router.py` | `POST /dialogs/{id}/messages` — первый API-роут проекта |
| `app/infrastructure/llm.py` | `get_chat_model()`, `execute_tool_calls()`, `invoke_with_tools()` — переиспользуемый tool-calling паттерн |
| `app/infrastructure/s3.py` | `ensure_bucket_exists()`, `upload_file()`, `download_file()` — async S3-клиент (`aioboto3`) |
| `app/modules/files/services/file_service.py` | `FileService.upload_file/download_file/get_metadata` — S3 + парсинг + метаданные в БД |
| `app/modules/files/services/file_parser.py` | `parse_to_text()` — PDF/DOCX/XLSX → плоский текст, остальное игнорируется |
| `app/modules/files/api/router.py` | `POST /files`, `GET /files/{id}`, `GET /files/{id}/metadata` |
| `migrations/env.py` | Настройка Alembic: URL из `Settings`, `target_metadata = Base.metadata`; импортирует модели каждого модуля для autogenerate |
| `docker-compose.yml` | Локальное окружение: app + PostgreSQL + Redis + Qdrant + MinIO |

## Тесты и миграции — только через Docker

- Тесты: `docker compose up -d postgres minio`, затем
  `docker compose run --rm app uv run pytest` (реальные БД/MinIO, без моков).
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
| Модуль dialog | `docs/dialog.md` | Модель, репозиторий, схемы — первый доменный модуль |
| DialogMessage | `docs/dialog-message.md` | Модель и репозиторий истории сообщений диалога |
| Диалоги с LLM | `docs/dialog-chat.md` | LangChain, `DialogService`, `POST /dialogs/{id}/messages` |
| Tool calling у LLM | `docs/tool-calling.md` | `invoke_with_tools`, пример-инструмент `get_current_time` |
| Диалог как граф LangGraph | `docs/dialog-graph.md` | `DialogState`, узлы `agent`/`tools`, `build_dialog_graph()` |
| Работа с файлами | `docs/files.md` | Модель `File`, S3-клиент (MinIO), парсинг PDF/DOCX/XLSX в текст, `FileService`, эндпоинты `/files` |
| ARCHITECTURE | `.ai-factory/ARCHITECTURE.md` | Архитектурный паттерн, структура папок, примеры кода |
| DESCRIPTION | `.ai-factory/DESCRIPTION.md` | Спецификация проекта, стек, архитектурные заметки |
| Roadmap | `.ai-factory/ROADMAP.md` | Вехи развития проекта |
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
