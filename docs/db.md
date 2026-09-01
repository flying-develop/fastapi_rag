[← Конфигурация](configuration.md) · [Back to README](../README.md) · [Модуль dialog →](dialog.md)

# База данных и миграции

Async SQLAlchemy (engine/session) + Alembic для миграций. Инфраструктура
из вехи «Фундамент работы с БД» — база для доменных модулей (`dialog` и
далее), которые появятся на следующих планах этой же вехи.

## Engine и сессии

`app/infrastructure/db.py`:

- `engine` — async engine (`create_async_engine`), создаётся из
  `Settings.database_url` при импорте модуля, но **не подключается**
  сразу — драйвер инициализируется лениво при первом использовании.
- `Base` — общий декларативный класс для ORM-моделей всех модулей.
  Каждый модуль импортирует его в свои `models/`.
- `get_db()` — FastAPI-зависимость: отдаёт `AsyncSession` на запрос,
  коммитит при успехе, откатывает при исключении, всегда закрывает
  сессию.

При старте приложения (`app/main.py`, `lifespan`) выполняется лёгкая
проверка соединения (`SELECT 1`). Проверка нефатальная: если БД
недоступна, в лог пишется `ERROR`, но приложение всё равно
поднимается — на этом этапе ни один эндпоинт ещё не зависит от БД.

## Миграции (Alembic)

- `alembic.ini` + `migrations/` (async-шаблон).
- `migrations/env.py` берёт `DATABASE_URL` из `Settings` (не из
  `alembic.ini`) и использует `target_metadata = Base.metadata` — по
  мере появления моделей в модулях `autogenerate` увидит их
  автоматически.

## Работа только через Docker

Как и весь дев-процесс в этом проекте, миграции и тесты выполняются
внутри контейнера `app`, а не на хосте.

**Применить миграции:**

```bash
docker compose up -d postgres
docker compose run --rm app uv run alembic upgrade head
```

**Откатить:**

```bash
docker compose run --rm app uv run alembic downgrade -1
# или до конкретной ревизии / до пустой БД:
docker compose run --rm app uv run alembic downgrade base
```

**Создать новую ревизию** — образ приложения одноразовый (`--rm`), поэтому
без bind-mount сгенерированный файл пропадёт вместе с контейнером:

```bash
docker compose run --rm -v "$(pwd)/migrations:/srv/app/migrations" \
  app uv run alembic revision --autogenerate -m "add dialog tables"
```

Если файл после этого принадлежит `root` (контейнер пишет от root),
верните владельца:

```bash
docker run --rm -v "$(pwd)/migrations:/mnt" busybox \
  chown -R "$(id -u):$(id -g)" /mnt
```

## Тесты

```bash
docker compose up -d postgres
docker compose run --rm app uv run pytest
```

Тесты (`tests/infrastructure/test_db.py`) работают против реального
Postgres из docker-compose — без моков, по общему правилу проекта.

Один нюанс pytest-asyncio: `engine` создаётся один раз на процесс
(модуль-level), поэтому все тесты должны жить в одном event loop —
в `pyproject.toml` это `asyncio_default_test_loop_scope = "session"`.
Без этого второй и последующие тесты падают с ошибкой про
"different loop" из-за переиспользования соединений в пуле.

## See Also

- [Конфигурация](configuration.md) — переменная `DATABASE_URL` и учётные данные Postgres
- [Быстрый старт](getting-started.md) — запуск всего стека через Docker
- [Модуль dialog](dialog.md) — первый доменный модуль поверх этой инфраструктуры
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — где `app/infrastructure/` в общей структуре
