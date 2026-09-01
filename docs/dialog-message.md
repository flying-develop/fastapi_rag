[← Модуль dialog](dialog.md) · [Back to README](../README.md)

# DialogMessage: история сообщений

Модель, схемы и репозиторий для истории сообщений внутри `Dialog` —
второй план вехи «Диалоги с LLM (базовый чат)», поверх модуля `dialog`
(см. [Модуль dialog](dialog.md)). LangChain-интеграция, сервисный слой
и API-эндпоинт отправки сообщения — вне скоупа, появятся на следующих
планах той же вехи.

## Модель

`app/modules/dialog/models/dialog_message.py` — `DialogMessage(Base)`,
таблица `dialog_messages`:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | `int` | Primary key |
| `dialog_id` | `int` | `ForeignKey("dialogs.id", ondelete="CASCADE")`, индексировано вместе с `created_at` |
| `role` | `str` | `"user"` / `"assistant"` / `"system"` — валидируется на уровне схемы (`DialogMessageCreate`), без DB-constraint |
| `content` | `str` | `Text` (не `varchar` — сообщения могут быть длинными) |
| `created_at` | `datetime` | `server_default=func.now()` |

## Схемы

`app/modules/dialog/schemas/dialog_message.py`:

- `DialogMessageCreate` — `dialog_id`, `role: Literal["user", "assistant", "system"]`, `content`
- `DialogMessageRead` — все поля модели, `from_attributes=True`

## Репозиторий

`app/modules/dialog/repositories/dialog_message_repository.py` —
`DialogMessageRepository`, конструктор принимает `AsyncSession`:

- `append(data: DialogMessageCreate) -> DialogMessage`
- `list_by_dialog(dialog_id: int) -> list[DialogMessage]` — отсортировано по `created_at asc` (хронологический порядок истории — в отличие от `DialogRepository.list_by_user`, который сортирует `desc`)

Как и `DialogRepository`, только `flush()`ит изменения — коммит
происходит в `get_db()` (см. [БД и миграции](db.md)).

## Миграция

Таблица `dialog_messages` добавлена ревизией `6a116c1781a1`
(`down_revision = 3322351eeac7`, таблица `dialogs`):

- FK `dialog_id → dialogs.id` с `ondelete="CASCADE"` — удаление `Dialog`
  удаляет его историю сообщений вместе с ним. Без этого (найдено на
  `/aif-review`) `DialogRepository.delete()` на диалоге с сообщениями
  падал с необработанным `IntegrityError`.
- Индекс `ix_dialog_messages_dialog_id_created_at` на `(dialog_id,
  created_at)` — `list_by_dialog` фильтрует и сортирует именно по этим
  полям; Postgres не индексирует FK-колонки автоматически.

Применяется как обычно — см.
[БД и миграции → Миграции (Alembic)](db.md#миграции-alembic).

## Тесты

`tests/modules/dialog/test_dialog_message_repository.py` — тесты
`DialogMessageRepository` против реального Postgres из docker-compose,
используют ту же фикстуру `db_session` (см.
[Модуль dialog → Тесты](dialog.md#тесты)). Каждый тест сначала создаёт
`Dialog` через `DialogRepository` (FK-требование), затем работает с
сообщениями для этого `dialog_id`.

## See Also

- [Модуль dialog](dialog.md) — модель `Dialog`, `DialogRepository`, паттерн репозитория
- [БД и миграции](db.md) — engine/session, Alembic, тесты через Docker
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — структура модуля
