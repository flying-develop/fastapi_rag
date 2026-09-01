# Журнал реализации: Bootstrap проекта

План: `.ai-factory/plans/bootstrap-project.md`
Веха roadmap: «Bootstrap проекта»

## Task 1 — Инициализация Python-проекта через uv

- `uv init --app --no-package --vcs none --no-readme --python 3.12 --name ai-app-python --author-from none`
- ⚠️ Первый запуск `uv init` (без `--vcs none`) по умолчанию создал `.git` — это противоречило `git.enabled: false` в `.ai-factory/config.yaml`. Коммитов не было, поэтому `.git` удалён и `uv init` перезапущен с `--vcs none`.
- `uv init --app` по умолчанию создаёт `src/<package>/` layout — тоже не подошло под архитектуру Structured Modules (`app/modules`, `app/infrastructure`). Пересоздал без `src/`, вручную собрал `app/`, `app/modules/`, `app/infrastructure/` с `__init__.py`.
- `uv add fastapi "uvicorn[standard]" pydantic-settings` — зависимости встали: fastapi 0.141.1, uvicorn 0.52.4, pydantic-settings 2.15.0, pydantic 2.13.4 и транзитивные.
- Добавил `.env` в `.gitignore` (секреты не должны попадать в репозиторий, даже когда git пока выключен).

## Task 2 — Конфигурация приложения (pydantic-settings)

- `app/infrastructure/config.py`: класс `Settings(BaseSettings)` с полями `app_name`, `log_level`, `database_url`, `redis_url`, `qdrant_url`, `openai_api_key` (заготовки под будущие вехи — БД, Redis, Qdrant, LLM пока нигде не используются, кроме самого конфига).
- `get_settings()` с `@lru_cache` — синглтон настроек на процесс.
- `.env.example` в корне со всеми переменными; значения хостов (`postgres`, `redis`, `qdrant`) сразу под docker-compose имена сервисов.
- Проверка: `uv run python -c "from app.infrastructure.config import get_settings; ..."` — конфиг импортируется, дефолты читаются корректно.

## Task 3 — Структурированное логирование

- `app/infrastructure/logging.py`: `KeyValueFormatter` (кастомный `logging.Formatter`) рендерит запись в `key=value ...` строку, включая произвольные `extra`-поля и трейсбеки.
- `setup_logging(log_level)` — конфигурирует root-логгер один раз при старте, уровень полностью управляется `LOG_LEVEL`.
- Проверка вручную: DEBUG/INFO/WARNING/ERROR + `exc_info=True` — формат корректный, extra-поля (`user_id=42 action="login"`) выводятся.

## Task 4 — FastAPI приложение и /health

- `app/main.py`: `FastAPI` с `lifespan`-хендлером — при старте вызывает `setup_logging()` из конфига, логирует старт/готовность `/health`, при остановке логирует shutdown.
- `GET /health` → `{"status": "ok"}`, залогирован каждый вызов (DEBUG).
- Проверка: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8123` в фоне → `curl http://127.0.0.1:8123/health` → `200 OK`, `{"status":"ok"}`. Лог показал корректный старт (`Application startup complete`) и структурированные записи. Процесс остановлен, зависших uvicorn не осталось.

**Чекпоинт коммита (после задач 1-4) пропущен** — в проекте `git.enabled: false`, коммитить пока некуда.

## Task 5 — Dockerfile

- Базовый образ `python:3.12-slim`, `uv` копируется статическим бинарником из `ghcr.io/astral-sh/uv:0.12.3`.
- Слои разделены: сначала `pyproject.toml` + `uv.lock` → `uv sync --frozen` (кэшируемый слой зависимостей), затем `COPY app/`. Проект — `--no-package` (app-style), поэтому отдельного шага "install project" не нужно.
- `.dockerignore`: `.venv`, `__pycache__`, `.git`, `.env`, `.ai-factory`, `.claude`, `*.md`.
- Проверка: `docker build -t ai-app-python:bootstrap-test .` — собрался (~3с с кэшем зависимостей). `docker run` + `curl /health` → `200 OK`, логи структурированные. Тестовый образ и контейнер удалены после проверки.

## Task 6 — docker-compose.yml

- Сервисы: `app` (build из Dockerfile), `postgres:16`, `redis:7`, `qdrant/qdrant`. Volumes для всех трёх бэкендов (`postgres_data`, `redis_data`, `qdrant_data`).
- `app` зависит от `postgres` (`condition: service_healthy`), `redis`/`qdrant` (`service_started`).
- Healthcheck для `app` — сделал через `python -c "urllib.request.urlopen(...)"`, а не `curl`, чтобы не ставить лишний пакет в `python:3.12-slim` (отклонение от буквальной формулировки задачи, но тот же результат — HTTP-проверка `/health`). Healthcheck для `postgres` — `pg_isready`.
- В `.env.example` добавлены `POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB`, синхронизированные с учётными данными в `DATABASE_URL`.
- Для проверки конфига создал реальный `.env` (`cp .env.example .env`) — без него `docker compose config` падает с "env file not found". `docker compose config` резолвится корректно.

## Task 7 — Полный запуск через docker-compose

- `docker compose up -d --build` — весь стек поднялся: `app` и `postgres` в статусе `healthy`, `redis`/`qdrant` — `running` (healthcheck для них не настраивался, вне scope этой вехи).
- `curl http://localhost:8000/health` → `200 OK`, `{"status":"ok"}`.
- Логи `app` показывают корректную инициализацию (структурированные записи, уровень DEBUG) и обработку запросов.
- `docker compose down` — стек остановлен и удалён, volumes оставлены (не трогал, чтобы не терять состояние БД между запусками).

**Итог вехи:** локальное окружение полностью поднимается одной командой (`docker compose up -d --build`), готово как база для следующих вех (работа с БД, диалоги и т.д.).

## Документация (/aif-docs)

- Создан минимальный набор: `README.md` (лендинг, 60 строк), `docs/getting-started.md`, `docs/configuration.md`. Архитектура и описание проекта не дублируются — README ссылается на `.ai-factory/ARCHITECTURE.md` и `.ai-factory/DESCRIPTION.md`.
- `AGENTS.md` обновлён: структура проекта, ключевые точки входа и таблица документации приведены в соответствие с текущим состоянием (раньше там было "проект пока пустой").
- Roadmap: веха «Bootstrap проекта» отмечена `[x]`, добавлена запись в таблицу «Завершено» (2026-08-27).
