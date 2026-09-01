# Архитектура: Structured Modules (Technical Layer)

## Обзор

Лёгкая модульная архитектура: каждый домен (диалоги, RAG, task
pipeline, модерация, файлы) — отдельный модуль со своими роутами,
сервисами, репозиториями и моделями. Внутри модуля — деление по
техническим слоям (`api/services/repositories/models`), без полного
DDD-формализма (Domain/Application/Infrastructure/Presentation).

Это осознанный компромисс: домены достаточно независимы (диалоги, RAG
с отдельными шагами retrieval/rerank/chunking/indexing, несколько
видов модерации — профиль, аватар, обложка профиля, файлы профиля,
сообщения, "хочу"-заявки, и т.д.), но проект ведёт один разработчик —
полный Explicit Architecture (Domain/Application/Infrastructure/
Presentation на каждый bounded context) дал бы слишком много
boilerplate на старте. Structured Modules даёт чёткие границы между
доменами и путь для постепенного роста в сторону Explicit
Architecture, если модуль разрастётся.

## Обоснование выбора

- **Тип проекта:** AI-сервис на FastAPI + LangChain/LangGraph,
  поэтапная разработка.
- **Стек:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (async) + Alembic,
  LangChain/LangGraph, PostgreSQL, Qdrant, ARQ + Redis.
- **Ключевой фактор:** несколько независимых доменов (диалоги, RAG,
  task pipeline, несколько видов модерации, файлы) при соло-команде —
  нужны чёткие границы модулей, но без полного DDD-формализма.

## Структура папок

```
app/
├── modules/                                   # ── ДОМЕННЫЕ МОДУЛИ ──
│   ├── dialog/                                # Диалоги с LLM
│   │   ├── api/
│   │   │   └── router.py                      # FastAPI-роуты модуля
│   │   ├── services/
│   │   │   ├── dialog_service.py               # use cases по Dialog
│   │   │   └── graphs/                         # LangGraph-графы диалога
│   │   ├── repositories/
│   │   │   └── dialog_repository.py            # единственный доступ к БД для модуля
│   │   ├── models/                              # SQLAlchemy ORM-модели
│   │   │   └── dialog.py
│   │   └── schemas/                             # Pydantic-схемы (DTO)
│   │       └── dialog.py
│   │
│   ├── rag/                                    # Индексация статей, поиск, rerank
│   │   ├── api/
│   │   ├── services/
│   │   │   ├── chunker_service.py
│   │   │   ├── indexer_service.py
│   │   │   ├── retriever_service.py
│   │   │   └── rerank_service.py
│   │   ├── repositories/
│   │   ├── models/
│   │   └── schemas/
│   │
│   ├── tasks/                                  # Task pipeline (аналог TaskStatus/TaskStepStatus)
│   │   ├── api/
│   │   ├── services/
│   │   │   └── graphs/                         # LangGraph state machine задач
│   │   ├── repositories/
│   │   ├── models/                             # Task, TaskStep, TaskResult
│   │   └── schemas/
│   │
│   ├── moderation/                             # Конвейеры модерации контента
│   │   ├── api/
│   │   ├── services/                           # по одному сервису на вид модерации
│   │   ├── repositories/
│   │   ├── models/
│   │   └── schemas/
│   │
│   └── files/                                  # Приём, парсинг, хранение файлов
│       ├── api/
│       ├── services/
│       ├── repositories/
│       ├── models/
│       └── schemas/
│
└── infrastructure/                             # ── ИНФРАСТРУКТУРА (сквозная) ──
    ├── db.py                                   # SQLAlchemy engine/session, Alembic env
    ├── redis.py                                # Redis-клиент, конфигурация ARQ
    ├── qdrant.py                               # Qdrant-клиент
    ├── llm.py                                  # инициализация LangChain chat-моделей/embeddings
    ├── config.py                               # настройки (pydantic-settings, .env)
    ├── middleware.py                           # обработчики ошибок, единый формат ответа
    └── logging.py                              # настройка структурированного логирования
```

Миграции Alembic живут в корне `alembic/` (стандартное расположение
для этого инструмента), а не внутри `app/infrastructure/`.

## Правила зависимостей

- **Строгий поток вниз внутри модуля:** `api → services → repositories`.
  Внутренние слои (`repositories`, `models`) никогда не зависят от
  внешних (`api`).
- **Без пропуска слоёв:** роуты (`api/`) не обращаются к
  `repositories` напрямую, только через `services`.
- **Изоляция модулей:** модули могут зависеть от корневого
  `app/infrastructure/` (БД, Redis, Qdrant, LLM, конфиг), но не
  лезут во внутренности друг друга. Межмодульное взаимодействие —
  только через явные методы сервиса другого модуля (например,
  `tasks`-модуль вызывает `moderation`-сервис через его публичный
  интерфейс, а не через его репозиторий).
- ✅ `app/modules/tasks/services/task_service.py` вызывает
  `app/modules/moderation/services/*Service.classify(...)`
- ❌ `app/modules/tasks/repositories/*` импортирует что-либо из
  `app/modules/moderation/repositories/*`

## Взаимодействие слоёв/модулей

- Роуты FastAPI (`api/`) валидируют вход через Pydantic-схемы,
  вызывают один-два метода сервиса, формируют ответ.
- Сервисы (`services/`) содержат бизнес-логику и оркестрацию,
  включая LangChain/LangGraph цепочки и графы; получают зависимости
  через конструктор (DI через `Depends` в FastAPI).
- Репозитории (`repositories/`) — единственная точка доступа к БД
  через SQLAlchemy; инкапсулируют построение запросов и маппинг в
  модели/DTO.
- Фоновые задачи (ARQ-воркеры) вызывают те же сервисы, что и API —
  бизнес-логика не дублируется между HTTP- и worker-путём.

## Ключевые принципы

1. **Границы модулей:** каждый модуль инкапсулирует один домен.
   У модуля есть публичный интерфейс (сервисы) — остальные модули
   используют только его, не заглядывая во внутренности.
2. **Лёгкая инверсия зависимостей:** сервисы получают зависимости
   через конструктор/`Depends`; интерфейсы репозиториев (Protocol/ABC)
   приветствуются для будущего перехода к Explicit Architecture.
3. **Domain awareness:** сервисы — оркестраторы (Application
   Services); при росте бизнес-правил их стоит выносить в отдельные
   доменные объекты/функции внутри модуля, а не разрастать сервис.
4. **Infrastructure минимальна:** `app/infrastructure/` содержит
   только сквозные технические concerns (БД, Redis, Qdrant, LLM,
   конфиг, логирование) — никакой бизнес-логики.

## Code Organization Note

- **Новый функционал:** весь новый код следует структуре модулей,
  описанной в этом документе.
- **Существующий код:** проект пока пуст — структура применяется
  с первого коммита, без legacy-исключений.

## Примеры кода

### Репозиторий и модель (SQLAlchemy)

```python
# app/modules/dialog/models/dialog.py
from sqlalchemy.orm import Mapped, mapped_column
from app.infrastructure.db import Base

class Dialog(Base):
    __tablename__ = "dialogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    title: Mapped[str]


# app/modules/dialog/repositories/dialog_repository.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.dialog.models.dialog import Dialog

class DialogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, dialog_id: int) -> Dialog | None:
        result = await self._session.execute(
            select(Dialog).where(Dialog.id == dialog_id)
        )
        return result.scalar_one_or_none()

    async def save(self, dialog: Dialog) -> None:
        self._session.add(dialog)
        await self._session.flush()
```

### Сервис, использующий LangGraph, и роут FastAPI

```python
# app/modules/dialog/services/dialog_service.py
class DialogService:
    def __init__(self, repository: DialogRepository, graph: DialogGraph) -> None:
        self._repository = repository
        self._graph = graph

    async def send_message(self, dialog_id: int, text: str) -> DialogMessage:
        dialog = await self._repository.get_by_id(dialog_id)
        if dialog is None:
            raise DialogNotFoundError(dialog_id)

        result = await self._graph.ainvoke({"dialog": dialog, "input": text})
        await self._repository.save(dialog)
        return result["message"]


# app/modules/dialog/api/router.py
router = APIRouter(prefix="/dialogs")

@router.post("/{dialog_id}/messages", response_model=DialogMessageResponse)
async def send_message(
    dialog_id: int,
    payload: DialogMessageCreateRequest,
    service: DialogService = Depends(get_dialog_service),
) -> DialogMessageResponse:
    message = await service.send_message(dialog_id, payload.text)
    return DialogMessageResponse.model_validate(message)
```

## Антипаттерны

- ❌ **Анемичные репозитории с бизнес-логикой в роутах** — валидация
  бизнес-правил и оркестрация не должны жить в `api/`.
- ❌ **Пропуск слоёв** — роут, вызывающий репозиторий напрямую, минуя
  сервис.
- ❌ **Восходящие зависимости** — `repositories/` или `models/`,
  импортирующие что-то из `services/` или `api/`.
- ❌ **Циклические зависимости между модулями** — модуль `tasks`
  импортирует внутренности `moderation`, а `moderation` — внутренности
  `tasks`. Использовать общие схемы/события вместо этого.
- ❌ **God-сервис** — один сервис, обрабатывающий все use case'ы
  нескольких доменов сразу.
