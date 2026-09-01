# Модуль dialog: модели, репозиторий, схемы (CRUD)

Branch: none
Created: 2026-09-01

## Original Request

Следующий план в рамках вехи «Фундамент работы с БД» (см. .ai-factory/ROADMAP.md, журнал .ai-factory/journal/db-foundation.md). Первый план (SQLAlchemy engine/session + Alembic, план db-foundation-sqlalchemy-alembic) уже реализован и верифицирован. Этот план — второй и последний в этой вехе: модуль dialog со сквозным CRUD через repository-паттерн (модели SQLAlchemy, репозиторий, схемы) поверх уже готовой инфраструктуры app/infrastructure/db.py.

## Settings

- Testing: yes — тесты репозитория на реальном Postgres из docker-compose, без моков (по конвенции предыдущего плана)
- Logging: standard — INFO для ключевых событий репозитория (создание/обновление/удаление), без избыточного DEBUG на каждый шаг
- Docs: yes — обязательный чекпоинт документации по завершении (`/aif-docs`)

## Roadmap Linkage

Milestone: "Фундамент работы с БД"

Rationale: второй и последний план этой вехи. Первый план (`db-foundation-sqlalchemy-alembic`) поднял инфраструктуру (async engine/session, `get_db()`, Alembic). Этот план добавляет первый доменный модуль (`dialog`) со слоями `models/repositories/schemas` поверх этой инфраструктуры, закладывая паттерн repository, который переиспользуют все следующие модули (`rag`, `tasks`, `moderation`, `files`). API-роуты и LangChain-интеграция — вне скоупа, они появятся в следующей вехе «Диалоги с LLM» (модель `DialogMessage` и эндпоинт отправки сообщения — тоже её скоуп, не этого плана). По завершении этого плана веха «Фундамент работы с БД» может быть отмечена как выполненная в `ROADMAP.md`.

## Commit Plan

`git.enabled: false` в `.ai-factory/config.yaml` — реальные коммиты не создаются. Ниже — логическая группировка тасков для истории в журнале реализации.

1. **Checkpoint 1** (Tasks 1-2): модель `Dialog` + Pydantic-схемы.
   `feat(dialog): add Dialog model and schemas`
2. **Checkpoint 2** (Tasks 3-4): репозиторий + миграция Alembic.
   `feat(dialog): add DialogRepository and migration`
3. **Checkpoint 3** (Tasks 5-7): тесты, документация, финальная проверка.
   `test(dialog): add repository tests; docs(dialog): document module`

## Tasks

### Phase 1: Модель и схемы

- [x] **Task 1: SQLAlchemy-модель `Dialog`**
  - Создать `app/modules/dialog/__init__.py` и `app/modules/dialog/models/__init__.py`, `app/modules/dialog/models/dialog.py`.
  - Класс `Dialog(Base)` (импорт `Base` из `app/infrastructure/db.py`), таблица `dialogs`:
    - `id: Mapped[int]` — primary key, autoincrement
    - `user_id: Mapped[int]` — без FK (модуля пользователей ещё нет, как в примере `.ai-factory/ARCHITECTURE.md`)
    - `title: Mapped[str]`
    - `created_at: Mapped[datetime]` — `server_default=func.now()`
    - `updated_at: Mapped[datetime]` — `server_default=func.now()`, `onupdate=func.now()`
  - Логирование не требуется (декларативная модель, без поведения).

- [x] **Task 2: Pydantic-схемы (DTO)**
  - Создать `app/modules/dialog/schemas/__init__.py`, `app/modules/dialog/schemas/dialog.py`.
  - `DialogCreate` — `user_id: int`, `title: str`.
  - `DialogUpdate` — `title: str` (единственное изменяемое поле на этом этапе).
  - `DialogRead` — `id`, `user_id`, `title`, `created_at`, `updated_at`, `model_config = ConfigDict(from_attributes=True)` для конвертации из ORM-объекта.
  - Зависит от Task 1 (использует те же имена полей).

### Phase 2: Репозиторий и миграция

- [x] **Task 3: `DialogRepository`**
  - Создать `app/modules/dialog/repositories/__init__.py`, `app/modules/dialog/repositories/dialog_repository.py`.
  - Класс `DialogRepository`, конструктор принимает `AsyncSession` (паттерн — как в `.ai-factory/ARCHITECTURE.md`).
  - Методы:
    - `async def create(self, data: DialogCreate) -> Dialog` — создаёт, `session.add` + `flush` (коммит — снаружи, в `get_db()`), лог `INFO` с `dialog_id` после `flush`.
    - `async def get_by_id(self, dialog_id: int) -> Dialog | None`.
    - `async def list_by_user(self, user_id: int) -> list[Dialog]` — отсортировано по `created_at desc`.
    - `async def update(self, dialog_id: int, data: DialogUpdate) -> Dialog | None` — возвращает `None`, если диалог не найден; лог `INFO` при успешном обновлении.
    - `async def delete(self, dialog_id: int) -> bool` — возвращает `False`, если диалог не найден; лог `INFO` при успешном удалении.
  - Логирование: `INFO` на create/update/delete (аналог `logging: standard` из Settings), без DEBUG на каждый SELECT.
  - Зависит от Task 1, Task 2.

- [x] **Task 4: Alembic-миграция для таблицы `dialogs`**
  - Через Docker с bind-mount (см. `docs/db.md`):
    `docker compose run --rm -v "$(pwd)/migrations:/srv/app/migrations" app uv run alembic revision --autogenerate -m "add dialogs table"`.
  - `down_revision` должен указывать на текущий head (`df364b45a5ac`).
  - Проверить сгенерированный файл вручную (autogenerate не всегда точен), поправить владельца файла при необходимости (root → host user, см. паттерн из прошлого плана).
  - Применить: `docker compose run --rm app uv run alembic upgrade head`, проверить `downgrade -1` + повторный `upgrade head`.
  - Зависит от Task 1.

### Phase 3: Тесты, документация, проверка

- [x] **Task 5: Тесты репозитория**
  - Создать `tests/modules/dialog/__init__.py` (или без него, если `pythonpath`-конфигурация не требует — свериться с текущей структурой `tests/`), `tests/modules/dialog/test_dialog_repository.py`.
  - Первый `tests/conftest.py` в проекте (сейчас его нет): фикстура `db_session`, отдающая `AsyncSession` из `async_session_factory`, и очистка таблицы `dialogs` после каждого теста (`DELETE FROM dialogs` или `TRUNCATE`), чтобы тесты были независимы друг от друга.
  - Тесты (реальный Postgres из docker-compose, без моков — по конвенции проекта):
    - `test_create_persists_dialog`
    - `test_get_by_id_returns_none_when_missing`
    - `test_list_by_user_returns_only_that_users_dialogs_ordered_by_created_at_desc`
    - `test_update_changes_title`
    - `test_update_returns_none_when_missing`
    - `test_delete_removes_dialog_and_returns_true`
    - `test_delete_returns_false_when_missing`
  - Зависит от Task 3, Task 4 (нужна применённая миграция).

- [x] **Task 6: Документация (обязательный чекпоинт)**
  - Через `/aif-docs`: описать модуль `dialog` — модель, репозиторий, паттерн для будущих модулей.
  - Решить на чекпоинте: отдельная страница (`docs/dialog.md`) или раздел в `docs/db.md` — уточнить у пользователя, как в предыдущем плане.
  - Обновить `AGENTS.md` (структура проекта, таблица ключевых точек входа) и `README.md` при необходимости.
  - Зависит от Task 1-5 (документируется финальное состояние).

- [x] **Task 7: Финальная проверка**
  - Полный прогон тестов в Docker: `docker compose up -d postgres`, `docker compose run --rm app uv run pytest`.
  - Проверить компиляцию (`python -m py_compile` или импорт модуля), отсутствие TODO/debug-маркеров.
  - Проверить состояние Alembic: `docker compose run --rm app uv run alembic current` — должен быть head новой ревизии.
  - Опустить стек (`docker compose down`), убедиться, что не осталось файлов, принадлежащих root.
  - Зависит от Task 1-6.
