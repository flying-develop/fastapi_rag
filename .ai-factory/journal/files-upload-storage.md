# Журнал реализации: Работа с файлами

Веха roadmap: «Работа с файлами»
Планы вехи:
- `.ai-factory/plans/files-upload-storage.md` — приём файлов + S3-хранилище (реализован, 10/10).
- Второй план (ещё не создан) — парсинг PDF/DOCX/XLSX в плоский текст; изображения и медиафайлы должны быть проигнорированы на этапе парсинга (не пытаться извлекать из них текст).

## План 1: Приём и S3-хранилище

### Task 1 — MinIO в docker-compose + настройки

- `docker-compose.yml`: сервис `minio` (`minio/minio`, `server /data --console-address ":9001"`, порты 9000/9001, healthcheck через `curl`), `app` теперь зависит от `minio: condition: service_healthy`.
- `app/infrastructure/config.py`: `s3_endpoint_url`/`s3_access_key`/`s3_secret_key`/`s3_bucket`/`s3_region` в `Settings`.
- `.env.example` и `.env` (реальный, не в git) — секция S3/MinIO, `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` в синхронизации с `S3_ACCESS_KEY`/`S3_SECRET_KEY`.
- На хосте: `uv add aioboto3` (та же причина, что и раньше — `docker compose run` теряет изменения `pyproject.toml`/`uv.lock`).

### Task 2 — Async S3-клиент — `app/infrastructure/s3.py`

- `ensure_bucket_exists()`/`upload_file()`/`download_file()` на `aioboto3`. Фреш-клиент на каждый вызов (`_client()` — async context manager), а не один долгоживущий — по рекомендации `aioboto3` (сессия `aiohttp` не должна жить дольше запроса).
- `head_bucket` + `create_bucket` для идемпотентной проверки бакета — код ошибки "нет бакета" проверяется по обоим вариантам (`404`/`NoSuchBucket`), т.к. отличается между реализациями S3.

### Task 3 — Проверка бакета при старте — `app/main.py`

- `_check_s3_bucket()` по образцу `_check_db_connection()` — non-fatal, ERROR-лог при сбое, приложение не падает.

### Task 4 — Модель `File` + миграция

- `app/modules/files/models/file.py`: `filename`/`content_type`/`size_bytes`/`storage_key` (unique)/`created_at`.
- **Тот же класс проблемы, что и в вехе "Фундамент работы с БД"**: `docker compose run --rm app uv run alembic revision --autogenerate` без bind-mount создаёт файл только внутри одноразового контейнера — он пропадает при удалении. Исправлено сразу (без лишней попытки) через `docker compose run --rm -v "$(pwd)/migrations:/srv/app/migrations" app uv run alembic revision --autogenerate -m "add files table"`, затем `chown` файла (создан от имени root внутри контейнера).
- Автогенерация не потребовала ручной правки — колонки совпали с моделью 1:1.

### Task 5 — `FileRepository` + схемы + исключение

- `FileRepository.create`/`get_by_id` по образцу `DialogRepository`.
- `FileCreate` (репозиторий) / `FileResponse` (API, суффикс `Response`).
- **Осознанное отклонение от буквального текста плана**: исключение названо `StoredFileNotFoundError`, а не `FileNotFoundError`, как было в плане — `FileNotFoundError` затеняет одноимённое встроенное исключение Python (поднимается `open()` и т.п.), что могло бы привести к путанице/багам при `except FileNotFoundError` в другом коде.

### Task 6 — `FileService`

- `upload_file`: генерирует `storage_key` (`{uuid4()}{расширение}` — не доверяет `filename` клиента напрямую), грузит в S3, затем создаёт метаданные.
- `download_file`: находит метаданные, скачивает байты по `storage_key`, поднимает `StoredFileNotFoundError`, если записи нет.

### Task 7 — API-эндпоинты

- `POST /files` (`multipart/form-data`), `GET /files/{id}` (сырые байты, `Content-Type`/`Content-Disposition`). DI `get_file_service` по образцу `get_dialog_service`.
- **Отловленная и исправленная проблема**: `UploadFile` в FastAPI требует `python-multipart` — без него `from app.main import app` падает с `RuntimeError: Form data requires "python-multipart"` уже при импорте приложения (не только при реальном запросе). Добавлено `uv add python-multipart`.
- Обработчик `StoredFileNotFoundError` → `404` в `app/main.py`, по образцу `handle_dialog_not_found`.

### Task 8 — Тесты

- `tests/infrastructure/test_s3.py`, `tests/modules/files/test_file_repository.py`/`test_file_service.py`/`test_file_router.py` — реальные MinIO+Postgres, без моков (как договаривались в настройках плана).
- **Мелкая правка теста, не баг кода**: `Response(media_type="text/plain")` у Starlette добавляет `; charset=utf-8` по умолчанию — тест на `Content-Type` изменён на `.startswith("text/plain")`.
- Итог: 50/50 (40 старых + 10 новых).

### Task 9 — Документация

- Новая страница `docs/files.md`; обновлены `docs/dialog-graph.md` (ссылка вперёд), `docs/configuration.md` (переменные `S3_*`/`MINIO_*`), `README.md`, `AGENTS.md`.
- Заодно поправлена устаревшая формулировка "пока один узел `agent`" в `README.md`/`AGENTS.md`, оставшаяся неисправленной со времён первого плана вехи LangGraph (обнаружено при проверке актуальности документации, не входило явно в план — минимальная точечная правка).
- `.ai-factory/DESCRIPTION.md`: добавлена запись про `aioboto3`/MinIO в разделе "Технологический стек".

### Task 10 — Финальная проверка

- **Отловленная и исправленная проблема (баг кода, не теста)**: `logger.debug("uploading file", extra={"filename": filename, ...})` — `filename` является зарезервированным атрибутом `LogRecord` (имя файла исходного кода вызова лога), из-за чего `extra={"filename": ...}` поднимает `KeyError: "Attempt to overwrite 'filename' in LogRecord"`. **Не была поймана прогоном pytest**, потому что тестовое окружение не вызывает `setup_logging(DEBUG)` — `logger.debug(...)` — no-op при уровне выше DEBUG, `makeRecord` не вызывается, коллизия не проявляется. Обнаружено только через ручной сквозной smoke-тест (`curl -X POST /files`) на полном стеке с `LOG_LEVEL=DEBUG` по умолчанию из `docker-compose.yml`. Исправлено переименованием ключа в `uploaded_filename` во всех трёх местах `file_service.py`. **Урок на будущее**: проверять новые `extra={...}` ключи логов на пересечение с зарезервированными атрибутами `LogRecord` (`filename`, `module`, `msg`, `args`, `levelname`, `pathname`, `lineno`, `funcName`, `created`, `process`, ...) — pytest по умолчанию этого не ловит, только ручной прогон с реальным уровнем логирования.
- Ручной сквозной тест (после исправления): `curl -X POST /files -F "file=@..."` → `201` с метаданными, `curl /files/{id}` → `200` с побайтово идентичным содержимым, `curl /files/999999` → `404`.
- Root-owned `__pycache__` под `migrations/` (от bind-mount команды autogenerate) — подчищено (`rm` через контейнер с `--user root`), сам каталог в `.gitignore`, так что не блокирующая находка.

**Итог плана:** модуль `files` — приём и хранение в S3-совместимом хранилище (MinIO), полный сквозной путь `POST /files` → `GET /files/{id}` работает, 50/50 тестов проходят. Веха «Работа с файлами» пока не закрыта — второй план (парсинг PDF/DOCX/XLSX в плоский текст, с явным игнорированием изображений/медиафайлов) ещё предстоит.
