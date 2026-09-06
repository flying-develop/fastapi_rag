[← Диалог как граф LangGraph](dialog-graph.md) · [Back to README](../README.md)

# Работа с файлами: приём и хранение

Первый из двух планов вехи «Работа с файлами» — приём файлов через API
и хранение в S3-совместимом объектном хранилище (MinIO локально через
docker-compose). Файл хранится как есть, без интерпретации содержимого
— парсинг PDF/DOCX/XLSX в плоский текст (с явным игнорированием
изображений и прочих медиафайлов) будет во втором плане вехи.

## Модель `File`

`app/modules/files/models/file.py` — метаданные загруженного файла:

| Поле | Описание |
|------|----------|
| `filename` | Исходное имя файла от клиента — только для отображения |
| `content_type` | MIME-тип |
| `size_bytes` | Размер в байтах |
| `storage_key` | Уникальный ключ объекта в S3-бакете |
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

## `FileService`

`app/modules/files/services/file_service.py`:

- `upload_file(filename, content_type, data) -> File` — генерирует
  `storage_key`, загружает байты в S3, затем создаёт запись метаданных
  через `FileRepository`.
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

Успех (`201`):

```json
{
  "id": 1,
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "size_bytes": 48213,
  "created_at": "2026-09-06T12:00:00Z"
}
```

**`GET /files/{file_id}`** — отдаёт сырые байты файла с исходными
`Content-Type`/`Content-Disposition`:

```bash
curl -OJ http://localhost:8000/files/1
```

Файл не найден (`404`):

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
- `tests/modules/files/test_file_repository.py` — CRUD `FileRepository` на реальной БД.
- `tests/modules/files/test_file_service.py` — `upload_file`/`download_file` сквозняком (MinIO + БД), включая `StoredFileNotFoundError`.
- `tests/modules/files/test_file_router.py` — `POST /files`/`GET /files/{id}` через `httpx.AsyncClient` + `ASGITransport`.

## See Also

- [Диалог как граф LangGraph](dialog-graph.md) — предыдущая веха
- [БД и миграции](db.md) — паттерн репозитория, тесты на реальном Postgres
- [Конфигурация](configuration.md) — `S3_*`/`MINIO_*` переменные
- [Архитектура](../.ai-factory/ARCHITECTURE.md) — паттерн Structured Modules
