# Работа с файлами: приём и S3-хранилище

Branch: none
Created: 2026-09-06

## Original Request

full — первый из двух планов вехи «Работа с файлами»: приём файлов через API и хранение в S3-совместимом хранилище (MinIO локально через docker-compose). Модель/репозиторий File (метаданные: имя, content_type, размер, storage key, дата загрузки), S3-клиент в app/infrastructure/, эндпоинты загрузки и скачивания файла. Хранится сам файл как есть, без парсинга — парсинг PDF/DOCX/XLSX в текст будет во втором плане вехи. Важное ограничение на всю веху (учесть при формулировке второго плана): нужен только плоский текст из документов; изображения и медиафайлы (не PDF/DOCX/XLSX) должны игнорироваться на этапе парсинга, а не пытаться извлекать из них текст.

## Settings

- Testing: yes — тесты на реальном MinIO из docker-compose (по аналогии с `test_db.py` на реальном Postgres), без моков S3-клиента
- Logging: standard — INFO на ключевые события (загрузка/скачивание завершились), тот же уровень детализации, что в модуле `dialog`
- Docs: yes — обязательный чекпоинт документации по завершении (новая страница `docs/files.md`)

## Roadmap Linkage

Milestone: "Работа с файлами"

Rationale: первый из двух планов вехи. Вводит приём файлов и S3-совместимое хранилище (MinIO) — модуль `files` с моделью/репозиторием/сервисом/API для загрузки и скачивания файла как есть, без интерпретации содержимого. Второй план вехи добавит парсинг PDF/DOCX/XLSX в плоский текст поверх уже загруженных файлов; изображения и прочие медиафайлы будут осознанно проигнорированы на этапе парсинга (не этого плана — здесь любой файл принимается и хранится одинаково).

## Commit Plan

`git.enabled: false` в `.ai-factory/config.yaml` — реальные коммиты не создаются. Ниже — логическая группировка тасков для истории в журнале реализации.

1. **Checkpoint 1** (Tasks 1-3): MinIO в docker-compose + конфигурация + S3-клиент.
   `feat(infra): add MinIO service and async S3 client (aioboto3)`
2. **Checkpoint 2** (Tasks 4-6): модуль `files` — модель, репозиторий, сервис, API.
   `feat(files): add File model, repository, service, upload/download endpoints`
3. **Checkpoint 3** (Tasks 7-9): тесты, документация, финальная проверка.
   `test(files): cover S3 client and files module; docs(files): document upload/storage`

## Tasks

### Phase 1: Инфраструктура хранилища

- [x] **Task 1: MinIO в docker-compose + настройки**
  - `docker-compose.yml`: новый сервис `minio` — `image: minio/minio`, `command: server /data --console-address ":9001"`, порты `9000:9000` (S3 API) и `9001:9001` (консоль), volume `minio_data:/data`, healthcheck `["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]` (интервал/таймауты как у `postgres`), env `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` из `.env` (по аналогии с `POSTGRES_USER`/`POSTGRES_PASSWORD`). Добавить `minio_data` в `volumes:`. Сервис `app` — добавить `minio: condition: service_healthy` в `depends_on`.
  - `app/infrastructure/config.py`: добавить в `Settings` — `s3_endpoint_url: str = "http://localhost:9000"`, `s3_access_key: str = "minioadmin"`, `s3_secret_key: str = "minioadmin"`, `s3_bucket: str = "files"`, `s3_region: str = "us-east-1"` (регион не проверяется строго у MinIO, но обязателен для клиента S3 API).
  - `.env.example`: секция про S3/MinIO — `S3_ENDPOINT_URL=http://minio:9000` (хост `minio` — имя сервиса docker-compose, как у `postgres`/`redis`/`qdrant`), `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET=files`, `S3_REGION=us-east-1`, плюс `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` для самого контейнера (в синхронизации с `S3_ACCESS_KEY`/`S3_SECRET_KEY`).
  - На хосте (не через `docker compose run` — теряется при удалении контейнера): `uv add aioboto3`. Пересобрать образ (`docker compose build app`).
  - Логирование не требуется (конфигурация/инфраструктура).

- [x] **Task 2: Async S3-клиент — `app/infrastructure/s3.py`**
  - `get_s3_client_session() -> aioboto3.Session` или напрямую фабрика async context manager'а клиента — обёртка над `aioboto3.Session().client("s3", endpoint_url=settings.s3_endpoint_url, aws_access_key_id=..., aws_secret_access_key=..., region_name=...)`.
  - `async def ensure_bucket_exists() -> None` — проверить бакет (`head_bucket`), создать (`create_bucket`), если отсутствует (перехватить `ClientError`/404). Вызывается один раз при старте приложения.
  - `async def upload_file(key: str, data: bytes, content_type: str) -> None` — `put_object(Bucket=..., Key=key, Body=data, ContentType=content_type)`.
  - `async def download_file(key: str) -> bytes` — `get_object` + чтение тела потока; поднимает понятное исключение (например, `FileStorageError`/пробрасывает `ClientError`), если ключ не найден — обработку 404 на уровне сервиса модуля `files` (Task 5), не здесь.
  - Логирование: INFO при успешной загрузке/скачивании (`key`, `size_bytes`), ERROR при ошибке S3-вызова (`key`, `error_type`).
  - Зависит от Task 1.

- [x] **Task 3: Проверка бакета при старте — `app/main.py`**
  - В `lifespan()`: после существующей `_check_db_connection()` вызвать `ensure_bucket_exists()` из `app/infrastructure/s3.py`, по тому же принципу non-fatal (`try/except Exception`, ERROR-лог, приложение не падает) — как `_check_db_connection()`.
  - Зависит от Task 2.

### Phase 2: Модуль `files`

- [x] **Task 4: Модель `File` + миграция**
  - `app/modules/files/models/file.py` — `File(Base)`: `id` (PK), `filename` (str, исходное имя от клиента — только для отображения, не используется как storage key), `content_type` (str), `size_bytes` (int), `storage_key` (str, unique — сгенerированный идентификатор объекта в S3, не совпадает с `filename`, чтобы избежать path traversal/коллизий), `created_at` (datetime, server_default).
  - Alembic-миграция (`docker compose run --rm app uv run alembic revision --autogenerate -m "add files table"`, затем `alembic upgrade head`) — по образцу миграции `dialog_messages`.
  - `app/modules/files/__init__.py`, `app/modules/files/models/__init__.py` — пустые, как у `dialog`.
  - Зависит от Task 1 (для образца структуры — не блокирует по коду).

- [x] **Task 5: `FileRepository` + Pydantic-схемы**
  - `app/modules/files/repositories/file_repository.py` — `FileRepository`: `create(data: FileCreate) -> File`, `get_by_id(file_id: int) -> File | None`. По образцу `DialogRepository`.
  - `app/modules/files/schemas/file.py` — `FileCreate` (DTO репозитория: `filename`, `content_type`, `size_bytes`, `storage_key`), `FileResponse` (API-схема: `id`, `filename`, `content_type`, `size_bytes`, `created_at` — суффикс `Response` по конвенции `.ai-factory/rules/base.md`).
  - `app/modules/files/exceptions.py` — `FileNotFoundError(file_id: int)`.
  - Зависит от Task 4.

- [x] **Task 6: `FileService` — `app/modules/files/services/file_service.py`**
  - `upload_file(filename: str, content_type: str, data: bytes) -> File`: сгенerировать `storage_key` (например, `f"{uuid4()}{Path(filename).suffix}"` — не доверяем исходному `filename` напрямую), вызвать `upload_file()` из `app/infrastructure/s3.py`, затем создать запись через `FileRepository.create(...)`, вернуть `File`.
  - `download_file(file_id: int) -> tuple[File, bytes]`: `FileRepository.get_by_id(file_id)` → если `None`, `FileNotFoundError`; иначе скачать байты через `download_file()` из `app/infrastructure/s3.py` по `storage_key`, вернуть `(File, bytes)`.
  - Логирование: INFO на успешную загрузку/скачивание (`file_id`, `filename`, `size_bytes`), ERROR при сбое S3-вызова (проброс исключения дальше — по аналогии с `try/except Exception` в `DialogService.send_message`).
  - Зависит от Task 3, Task 5.

- [x] **Task 7: API-эндпоинты — `app/modules/files/api/router.py`**
  - `POST /files` — `UploadFile` (FastAPI, `multipart/form-data`), читает `await file.read()`, вызывает `FileService.upload_file(file.filename, file.content_type, data)`, возвращает `FileResponse` (`201`).
  - `GET /files/{file_id}` — вызывает `FileService.download_file(file_id)`, возвращает `Response(content=data, media_type=file.content_type, headers={"Content-Disposition": f'attachment; filename="{file.filename}"'})`; `404` при `FileNotFoundError` (обработчик в `app/main.py`, по образцу `handle_dialog_not_found`).
  - DI: `get_file_service(session: AsyncSession = Depends(get_db)) -> FileService` — по образцу `get_dialog_service` в `app/modules/dialog/api/router.py`.
  - Зарегистрировать роутер (`files_router`) в `app/main.py` (`app.include_router`), добавить обработчик `FileNotFoundError` (`404`).
  - Зависит от Task 6.

### Phase 3: Тесты, документация, проверка

- [x] **Task 8: Тесты**
  - `tests/infrastructure/test_s3.py` — `ensure_bucket_exists()`/`upload_file()`/`download_file()` на реальном MinIO из docker-compose (по образцу `test_db.py` на реальном Postgres, без моков).
  - `tests/modules/files/conftest.py`, `tests/modules/files/test_file_repository.py` — CRUD `FileRepository` на реальной БД (по образцу `test_dialog_repository.py`).
  - `tests/modules/files/test_file_service.py` — `upload_file`/`download_file` сквозняком через реальные MinIO+БД (включая `FileNotFoundError` для несуществующего `file_id`).
  - `tests/modules/files/test_file_router.py` — эндпоинты через `httpx.AsyncClient` + `ASGITransport` (по образцу `test_dialog_router.py`): успешная загрузка/скачивание, `404` для отсутствующего файла.
  - Зависит от Task 7.

- [x] **Task 9: Документация (обязательный чекпоинт)**
  - Новая страница `docs/files.md`: модель `File`, S3-клиент (`app/infrastructure/s3.py`, MinIO для локальной разработки), `FileService`, эндпоинты `POST /files`/`GET /files/{id}`, конфигурация (`S3_ENDPOINT_URL` и т.п.), явная заметка, что это только приём/хранение — парсинг содержимого будет во втором плане вехи.
  - Обновить `README.md` (новая фича + строка в таблице документации), `AGENTS.md` (дерево структуры — новый модуль `files`, `app/infrastructure/s3.py`, новый сервис `minio` в `docker-compose.yml`; таблица точек входа; таблица документации).
  - Через `/aif-docs`.
  - Зависит от Task 1-8.

- [x] **Task 10: Финальная проверка**
  - Пересобрать образ (`docker compose build app`) перед прогоном тестов — обязательно после любых изменённых/новых файлов.
  - `docker compose up -d postgres minio`, `docker compose run --rm app uv run alembic upgrade head`, `docker compose run --rm app uv run pytest` — полный прогон, включая новые тесты.
  - Проверить компиляцию/импорт новых модулей, отсутствие TODO/debug-маркеров.
  - Ручная сквозная проверка: `docker compose up -d --build`, `curl /health` → `200 OK`; при наличии времени — ручная загрузка/скачивание файла через `curl -F` (без блокировки на этом, если окружение не позволяет).
  - `docker compose down`, убедиться, что не осталось файлов, принадлежащих root.
  - Зависит от Task 1-9.
