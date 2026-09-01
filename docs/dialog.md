[← БД и миграции](db.md) · [Back to README](../README.md) · [DialogMessage →](dialog-message.md)

# Модуль dialog

Первый доменный модуль поверх инфраструктуры из [БД и миграции](db.md) —
модель `Dialog`, Pydantic-схемы и `DialogRepository` со сквозным CRUD.
Задаёт паттерн repository, который переиспользуют все следующие модули
(`rag`, `tasks`, `moderation`, `files`) — см.
[Архитектура](../.ai-factory/ARCHITECTURE.md).

API-роуты и интеграция с LangChain — вне скоупа этого модуля на данном
этапе, появятся на следующей вехе.

## Модель

`app/modules/dialog/models/dialog.py` — `Dialog(Base)`, таблица `dialogs`:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `int` | Primary key |
| `user_id` | `int` | Без FK — модуля пользователей ещё нет |
| `title` | `str` | Заголовок диалога |
| `created_at` | `datetime` | `server_default=func.now()` |
| `updated_at` | `datetime` | `server_default`/`onupdate=func.now()` |

## Схемы

`app/modules/dialog/schemas/dialog.py`:

- `DialogCreate` — `user_id`, `title`
- `DialogUpdate` — `title` (единственное изменяемое поле на этом этапе)
- `DialogRead` — все поля модели, `from_attributes=True` для конвертации из ORM

## Репозиторий

`app/modules/dialog/repositories/dialog_repository.py` — `DialogRepository`,
конструктор принимает `AsyncSession`:

- `create(data: DialogCreate) -> Dialog`
- `get_by_id(dialog_id: int) -> Dialog | None`
- `list_by_user(user_id: int) -> list[Dialog]` — отсортировано по `created_at desc`
- `update(dialog_id: int, data: DialogUpdate) -> Dialog | None` — `None`, если не найден
- `delete(dialog_id: int) -> bool` — `False`, если не найден

Репозиторий только `flush()`ит изменения — коммит происходит в `get_db()`
(см. [БД и миграции](db.md)), а не внутри репозитория.

## Миграция

Таблица `dialogs` добавлена ревизией `3322351eeac7` (`down_revision =
df364b45a5ac`, baseline). Применяется как обычно — см.
[БД и миграции → Миграции (Alembic)](db.md#миграции-alembic).

Важный нюанс для будущих модулей: `migrations/env.py` собирает
`target_metadata` из `Base.metadata`, но модель регистрируется на
`Base.metadata` только если её модуль реально импортирован — поэтому
`env.py` явно импортирует `app.modules.dialog.models.dialog`. При
добавлении новой модели в новый модуль такой импорт нужно добавить и
для него.

## Тесты

`tests/modules/dialog/test_dialog_repository.py` — CRUD-тесты
`DialogRepository` против реального Postgres из docker-compose
(см. [БД и миграции → Тесты](db.md#тесты)).

Изоляция между тестами — через `tests/conftest.py::db_session`: сессия
на транзакции, откатывается (`rollback()`) в конце теста. Так как
репозиторий только `flush()`ит, откат отменяет все записи теста без
`TRUNCATE`.

Один нюанс pytest-asyncio, специфичный для async-фикстур: помимо
`asyncio_default_test_loop_scope` (уже был выставлен в `session` в
прошлом плане), фикстуры вроде `db_session` управляются отдельной
настройкой `asyncio_default_fixture_loop_scope` — без неё async-фикстура
получает свой собственный event loop, отличный от того, где создан
пул соединений `engine`, и падает с `RuntimeError: ... attached to a
different loop`. В `pyproject.toml` обе настройки теперь выставлены в
`session`.

## See Also

- [БД и миграции](db.md) — engine/session, Alembic, тесты через Docker
- [DialogMessage](dialog-message.md) — история сообщений диалога
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — паттерн Structured Modules, границы модулей
