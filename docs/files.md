[← Диалог как граф LangGraph](dialog-graph.md) · [Back to README](../README.md)

# Работа с файлами: приём, хранение и парсинг в текст

Веха «Работа с файлами» (закрыта): приём файлов через API, хранение в
S3-совместимом объектном хранилище (MinIO локально через
docker-compose) и извлечение плоского текста из PDF/DOCX/XLSX сразу при
загрузке. Изображения и любые другие медиафайлы (не PDF/DOCX/XLSX)
намеренно игнорируются на этапе парсинга — извлечение текста из них не
предпринимается.

## Модель `File`

`app/modules/files/models/file.py` — метаданные загруженного файла:

| Поле | Описание |
|------|----------|
| `filename` | Исходное имя файла от клиента — только для отображения |
| `content_type` | MIME-тип |
| `size_bytes` | Размер в байтах |
| `storage_key` | Уникальный ключ объекта в S3-бакете |
| `extracted_text` | Плоский текст, извлечённый из PDF/DOCX/XLSX (`None`, если `parse_status != "success"`) |
| `parse_status` | `"success"` / `"skipped"` / `"failed"` — см. "Парсинг в текст" ниже |
| `created_at` | Дата загрузки |

Сами байты файла лежат в S3, не в Postgres — эта таблица только
метаданные-индекс. `storage_key` — сгенерированный идентификатор
(`{uuid4()}{расширение}`), не совпадающий с `filename`: доверять
клиентскому имени файла напрямую как ключу объекта небезопасно (path
traversal, коллизии при одинаковых именах у разных загрузок).

## S3-клиент — `app/infrastructure/s3.py`

Асинхронный клиент на `aioboto3` (async-обёртка над `boto3`/`aiobotocore`)
— соответствует требованию проекта "весь I/O через async/await", как
`asyncpg`/SQLAlchemy async для Postgres.

- `ensure_bucket_exists()` — идемпотентная проверка/создание бакета,
  вызывается при каждом старте приложения (`app/main.py::lifespan`),
  non-fatal — как существующая `_check_db_connection()`.
- `upload_file(key, data, content_type)` — `put_object`.
- `download_file(key)` — `get_object` + чтение тела; поднимает
  `ClientError` для отсутствующего ключа (обрабатывается на уровне
  `FileService`, не здесь).

Локально — MinIO (`docker-compose.yml`, сервис `minio`, консоль на
`http://localhost:9001`), в проде — любое S3-совместимое хранилище,
меняется только конфигурация.

## Парсинг в текст — `app/modules/files/services/file_parser.py`

```python
def parse_to_text(content_type: str, data: bytes) -> tuple[str | None, str]
```

Синхронная функция (все три библиотеки — `pypdf`, `python-docx`,
`openpyxl` — синхронные); `FileService.upload_file` вызывает её через
`asyncio.to_thread(...)`, не блокируя event loop, — тот же приём, что
уже описан для sync-инструментов в [Tool calling у LLM](tool-calling.md).

Диспетчеризация по `content_type` — только три поддерживаемых типа:

- `application/pdf` → `pypdf.PdfReader`, текст всех страниц через `\n`.
- `.../wordprocessingml.document` (DOCX) → `python-docx`, текст всех параграфов через `\n`.
- `.../spreadsheetml.sheet` (XLSX) → `openpyxl`, значения ячеек через таб/перевод строки.

Возвращает `(extracted_text, parse_status)`:

- **`"success"`** — текст извлечён.
- **`"skipped"`** — `content_type` не PDF/DOCX/XLSX (изображения, аудио/видео,
  что угодно ещё). Парсинг **не предпринимается** — это осознанное
  требование вехи, а не недоработка.
- **`"failed"`** — тип поддерживается, но файл повреждён/невалиден.
  Исключение не пробрасывается наружу — `WARN`-лог и всё, чтобы ошибка
  парсинга не роняла саму загрузку файла.

Только плоский текст — без сохранения форматирования/структуры
документа (без таблиц как таблиц, без стилей).

## `FileService`

`app/modules/files/services/file_service.py`:

- `upload_file(filename, content_type, data) -> File` — генерирует
  `storage_key`, загружает байты в S3, вызывает `parse_to_text()`, затем
  создаёт запись метаданных (включая `extracted_text`/`parse_status`)
  через `FileRepository`.
- `get_metadata(file_id) -> File` — только метаданные (без обращения к
  S3) — то, что нужно `GET /files/{id}/metadata` ниже.
- `download_file(file_id) -> tuple[File, bytes]` — находит метаданные по
  `id` (`StoredFileNotFoundError`, если нет — намеренно не
  `FileNotFoundError`, чтобы не затенять одноимённое встроенное
  исключение Python), скачивает байты из S3 по `storage_key`.

## API-эндпоинты

`app/modules/files/api/router.py`:

**`POST /files`** — `multipart/form-data`, поле `file`:

```bash
curl -X POST http://localhost:8000/files -F "file=@report.pdf"
```

Успех (`201`) — парсинг уже выполнен к моменту ответа:

```json
{
  "id": 1,
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "size_bytes": 48213,
  "extracted_text": "...текст из PDF...",
  "parse_status": "success",
  "created_at": "2026-09-06T12:00:00Z"
}
```

**`GET /files/{file_id}/metadata`** — те же метаданные (включая
`extracted_text`/`parse_status`), без байтов файла:

```bash
curl http://localhost:8000/files/1/metadata
```

**`GET /files/{file_id}`** — отдаёт сырые байты файла с исходными
`Content-Type`/`Content-Disposition` (метаданные сюда не входят —
для них `.../metadata` выше):

```bash
curl -OJ http://localhost:8000/files/1
```

Файл не найден (`404`, оба эндпоинта):

```json
{"detail": "File 1 not found"}
```

## Конфигурация

См. также [Конфигурация](configuration.md).

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `S3_ENDPOINT_URL` | `http://minio:9000` (докер) | Адрес S3-совместимого хранилища |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `minioadmin` / `minioadmin` | Учётные данные S3-клиента |
| `S3_BUCKET` | `files` | Имя бакета |
| `S3_REGION` | `us-east-1` | Регион (не проверяется строго у MinIO, но обязателен для клиента) |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | `minioadmin` / `minioadmin` | Учётные данные контейнера `minio`; должны совпадать с `S3_ACCESS_KEY`/`S3_SECRET_KEY` |

## Тесты

Реальный MinIO из docker-compose, без моков S3-клиента (тот же подход,
что и для Postgres — см. [БД и миграции](db.md)):

- `tests/infrastructure/test_s3.py` — `ensure_bucket_exists()`/`upload_file()`/`download_file()` напрямую.
- `tests/modules/files/test_file_parser.py` — `parse_to_text()` для PDF/DOCX/XLSX (файлы генерируются в памяти через `reportlab`/`python-docx`/`openpyxl`, без бинарных fixture-файлов в git), плюс `"skipped"` для изображений и `"failed"` для повреждённого файла.
- `tests/modules/files/test_file_repository.py` — CRUD `FileRepository` на реальной БД.
- `tests/modules/files/test_file_service.py` — `upload_file`/`download_file` сквозняком (MinIO + БД), включая `StoredFileNotFoundError` и результат парсинга (`success`/`skipped`/`failed`, включая то, что ошибка парсинга не роняет загрузку).
- `tests/modules/files/test_file_router.py` — `POST /files`/`GET /files/{id}`/`GET /files/{id}/metadata` через `httpx.AsyncClient` + `ASGITransport`.

## See Also

- [Диалог как граф LangGraph](dialog-graph.md) — предыдущая веха
- [Tool calling у LLM](tool-calling.md) — тот же приём (`asyncio.to_thread`) для запуска sync-кода вне event loop
- [БД и миграции](db.md) — паттерн репозитория, тесты на реальном Postgres
- [Конфигурация](configuration.md) — `S3_*`/`MINIO_*` переменные
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — паттерн Structured Modules
