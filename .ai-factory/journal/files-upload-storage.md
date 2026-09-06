# Журнал реализации: Работа с файлами

Веха roadmap: «Работа с файлами»
Планы вехи:
- `.ai-factory/plans/files-upload-storage.md` — приём файлов + S3-хранилище (реализован, 10/10).
- `.ai-factory/plans/files-parse-to-text.md` — парсинг PDF/DOCX/XLSX в плоский текст (реализован, 8/8). Закрывает веху.

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

## План 2: Парсинг в плоский текст

### Task 1 — Зависимости для парсинга

- `uv add pypdf python-docx openpyxl` (runtime), `uv add --group dev reportlab` (только для генерации PDF-фикстур в тестах — production-код только читает PDF).
- Проверено, что `docker compose build`/`uv sync --frozen` по умолчанию ставит и `dev`-группу — `reportlab` доступен и в тестах, и в ручном smoke-тесте внутри контейнера.

### Task 2 — Парсер `app/modules/files/services/file_parser.py`

- `parse_to_text(content_type, data) -> (extracted_text, parse_status)` с диспетчеризацией по `content_type` на три поддерживаемых MIME-типа (PDF/DOCX/XLSX); всё остальное → `"skipped"` без попытки чтения байтов. Ошибка парсинга поддерживаемого типа → `"failed"`, `WARN`-лог, исключение не пробрасывается.
- Мелкая находка по стилю (сразу исправлено, не отдельная задача): один `logger.info(...)` вызов был длиннее принятого в проекте стиля — перенесён на несколько строк, по аналогии с прошлым ревью `graph.py`.

### Task 3 — Поля модели + миграция

- `File.extracted_text` (`Text`, nullable), `File.parse_status` (не-nullable строка, без Python/DB enum — тот же принцип, что `DialogMessage.role`).
- Миграция через bind-mount + `chown`, как обычно.
- **Отловленная и исправленная проблема**: в таблице `files` уже была 1 строка (от ручного smoke-теста Плана 1), а автосгенерированная миграция ставила `parse_status` как `NOT NULL` без дефолта — `alembic upgrade head` упал бы на существующей строке. Исправлено вручную (по образцу уже задокументированного паттерна "Manually adjusted post-autogenerate" из миграции `dialog_messages`): `server_default='skipped'` на `add_column`, затем `alter_column(..., server_default=None)` сразу следом — бэкафилл для старых строк без постоянного дефолта в схеме и в ORM-модели.

### Task 4 — Wiring парсинга в `FileService.upload_file`

- `extracted_text, parse_status = await asyncio.to_thread(parse_to_text, content_type, data)` — синхронные библиотеки парсинга выполняются в threadpool, не блокируя event loop (тот же приём, что уже описан для sync-инструментов в `docs/tool-calling.md`).
- `FileCreate`/`FileResponse` дополнены `extracted_text`/`parse_status` — оба поля возвращаются уже в ответе `POST /files`, не только через `GET /files/{id}/metadata`.

### Task 5 — `GET /files/{file_id}/metadata`

- Добавлен `FileService.get_metadata()` — не трогает S3 (в отличие от `download_file()`), только чтение метаданных из БД. Новый роут переиспользует уже существующий обработчик `StoredFileNotFoundError` без изменений.

### Task 6 — Тесты

- `test_file_parser.py`: PDF/DOCX/XLSX генерируются в памяти (`reportlab`/`python-docx`/`openpyxl`), без бинарных fixture-файлов в git; плюс `"skipped"` (изображение) и `"failed"` (битый PDF).
- Расширены `test_file_service.py`/`test_file_router.py` под новые поля/эндпоинт.
- **Отловленная и исправленная проблема**: существующие тесты `test_file_repository.py` (из Плана 1) стали падать с `pydantic.ValidationError` — `FileCreate` теперь требует `extracted_text`/`parse_status`, а старые тесты их не передавали. Обновлены (не переписаны с нуля) под новую сигнатуру.
- Итог: 60/60 (50 было + 10 новых).

### Task 7 — Документация

- `docs/files.md` переписан под завершённую веху (убрана формулировка "первый из двух планов"), добавлен раздел "Парсинг в текст", обновлена таблица полей `File`, примеры `POST /files`/`GET /files/{id}/metadata`.
- `README.md`/`AGENTS.md`/`.ai-factory/DESCRIPTION.md` обновлены (`pypdf`/`python-docx`/`openpyxl`, новый файл `file_parser.py`, новый эндпоинт).

### Task 8 — Финальная проверка

- 60/60 тестов, `docker compose build` перед каждым прогоном (обязательное правило проекта).
- Ручной сквозной smoke-тест — самый информативный шаг: реальные PDF/DOCX/XLSX сгенерированы внутри контейнера (`reportlab`/`python-docx`/`openpyxl`) и скопированы на хост (`docker compose cp`), загружены через `curl -F` с явным `type=...`. Результат для всех трёх — `parse_status: "success"` с корректным `extracted_text`; поддельный PNG (текстовые байты с `type=image/png`) — `parse_status: "skipped"`, `extracted_text: null`, парсер даже не пытался декодировать байты. `GET /files/{id}/metadata` и `404` на несуществующий `id` — проверены отдельно.
- Root-owned `__pycache__` под `migrations/` (тот же артефакт bind-mount команды, что и в Плане 1) — снова подчищено; не блокирующая находка, `.gitignore` уже её покрывает.

**Итог плана:** веха «Работа с файлами» закрыта — модуль `files` теперь принимает, хранит и извлекает плоский текст из PDF/DOCX/XLSX при загрузке, с явным и проверенным игнорированием изображений/медиафайлов и устойчивостью к повреждённым файлам (парсинг никогда не роняет загрузку).
