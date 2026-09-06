# Работа с файлами: парсинг в плоский текст

Branch: none
Created: 2026-09-06

## Original Request

full — второй и последний план вехи «Работа с файлами»: парсинг PDF/DOCX/XLSX в плоский текст поверх уже загруженных файлов (модуль files, app/modules/files/services/file_service.py, модель File). Изображения и любые другие медиафайлы (не PDF/DOCX/XLSX) должны быть проигнорированы на этапе парсинга — не пытаться извлекать из них текст, только явно отметить, что парсинг неприменим. Нужен только плоский текст, без сохранения форматирования/структуры документа. Парсинг встраивается в существующий upload_file() и не должен приводить к падению загрузки файла при ошибке парсинга (файл всё равно сохраняется). Закрывает веху.

## Settings

- Testing: yes — PDF/DOCX/XLSX-файлы генерируются прямо в тестах (`python-docx`/`openpyxl`/`reportlab`, dev-only), без статичных бинарных fixture-файлов в git
- Logging: standard — INFO на успешный/пропущенный парсинг, WARN на ошибку парсинга — тот же уровень, что в остальном модуле `files`
- Docs: yes — обязательный чекпоинт документации по завершении (раздел про парсинг в `docs/files.md`)

## Roadmap Linkage

Milestone: "Работа с файлами"

Rationale: второй и последний план вехи. Первый план ввёл приём/хранение файлов (модель `File`, S3, `POST /files`/`GET /files/{id}`) без интерпретации содержимого. Этот план добавляет извлечение плоского текста из PDF/DOCX/XLSX сразу при загрузке, с явным игнорированием изображений и прочих медиафайлов (не пытаться извлекать из них текст) — закрывает веху.

## Commit Plan

`git.enabled: false` в `.ai-factory/config.yaml` — реальные коммиты не создаются. Ниже — логическая группировка тасков для истории в журнале реализации.

1. **Checkpoint 1** (Tasks 1-2): зависимости + модуль парсера.
   `feat(files): add PDF/DOCX/XLSX text extraction parser`
2. **Checkpoint 2** (Tasks 3-5): модель/миграция + wiring + эндпоинт метаданных.
   `feat(files): store extracted text on upload; add GET /files/{id}/metadata`
3. **Checkpoint 3** (Tasks 6-8): тесты, документация, финальная проверка.
   `test(files): cover text extraction; docs(files): document parsing; close "Работа с файлами" milestone`

## Tasks

### Phase 1: Зависимости и парсер

- [x] **Task 1: Зависимости для парсинга**
  - На хосте (не через `docker compose run` — теряется при удалении контейнера): `uv add pypdf python-docx openpyxl` (runtime), `uv add --group dev reportlab` (только для генерации PDF-фикстур в тестах — production-код читает PDF через `pypdf`, писать PDF не нужно нигде, кроме тестов).
  - Пересобрать образ (`docker compose build app`).
  - Логирование не требуется (зависимости).

- [x] **Task 2: Парсер — `app/modules/files/services/file_parser.py`**
  - Константы MIME-типов: `_PDF_CONTENT_TYPE = "application/pdf"`, `_DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"`, `_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`.
  - `def parse_to_text(content_type: str, data: bytes) -> tuple[str | None, str]` — синхронная функция (CPU-bound библиотеки `pypdf`/`python-docx`/`openpyxl`, все синхронные), возвращает `(extracted_text, parse_status)`:
    - `content_type == _PDF_CONTENT_TYPE` → `pypdf.PdfReader(io.BytesIO(data))`, конкатенировать `page.extract_text()` по всем страницам через `"\n"`. Успех → `(text, "success")`.
    - `content_type == _DOCX_CONTENT_TYPE` → `docx.Document(io.BytesIO(data))`, конкатенировать `paragraph.text` по всем параграфам через `"\n"`. Успех → `(text, "success")`.
    - `content_type == _XLSX_CONTENT_TYPE` → `openpyxl.load_workbook(io.BytesIO(data), data_only=True)`, для каждого листа и каждой строки — значения ячеек через `str(cell)`, склеенные табуляцией, строки — переводом строки. Успех → `(text, "success")`.
    - Любой другой `content_type` (включая изображения и прочие медиафайлы) → **не пытаться парсить**, сразу `(None, "skipped")`.
    - Исключение при парсинге поддерживаемого типа (повреждённый/невалидный файл) → перехватить, `WARN`-лог (`content_type`, `error_type`), вернуть `(None, "failed")` — не пробрасывать исключение выше (загрузка файла не должна падать из-за ошибки парсинга).
  - Логирование: `INFO` при `"success"` (`content_type`, `extracted_length`) и при `"skipped"` (`content_type`); `WARN` при `"failed"` (как выше).
  - Только плоский текст — без сохранения форматирования/структуры (без таблиц как таблиц, без стилей) — синхронно с ограничением из `## Original Request`.
  - Зависит от Task 1.

### Phase 2: Модель, wiring, эндпоинт

- [x] **Task 3: Поля в модели `File` + миграция**
  - `app/modules/files/models/file.py`: добавить `extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)` и `parse_status: Mapped[str]` (значения: `"success"`/`"skipped"`/`"failed"` — как plain-строка, по конвенции проекта для `role`-подобных полей типа `DialogMessage.role`, без Python-enum/DB-enum).
  - Миграция через bind-mount (см. `AGENTS.md`): `docker compose run --rm -v "$(pwd)/migrations:/srv/app/migrations" app uv run alembic revision --autogenerate -m "add extracted_text and parse_status to files"`, затем `chown` файла на хосте, затем `alembic upgrade head`.
  - Зависит от Task 2.

- [x] **Task 4: Wiring парсинга в `FileService.upload_file`**
  - `app/modules/files/schemas/file.py`: добавить `extracted_text: str | None` и `parse_status: str` в `FileCreate` и в `FileResponse`.
  - `app/modules/files/repositories/file_repository.py::create`: передать `extracted_text`/`parse_status` в конструктор `File(...)`.
  - `app/modules/files/services/file_service.py::upload_file`: после успешной загрузки в S3 (перед сохранением метаданных) вызвать `extracted_text, parse_status = await asyncio.to_thread(parse_to_text, content_type, data)` — синхронный, потенциально CPU-тяжёлый парсинг выполняется в threadpool, не блокируя event loop (тот же принцип, что уже описан для sync-инструментов в `docs/tool-calling.md`). Передать оба значения в `FileCreate(...)`.
  - Логирование: не дублировать логи парсера — `parse_to_text`/`file_parser.py` уже логирует свой результат; `FileService` продолжает логировать `file uploaded` как раньше, можно добавить `parse_status` в `extra`.
  - Зависит от Task 3.

- [x] **Task 5: `GET /files/{file_id}/metadata`**
  - `app/modules/files/api/router.py`: новый роут `GET /files/{file_id}/metadata` → `FileResponse` (метаданные + `extracted_text`/`parse_status`, без байтов файла — в отличие от существующего `GET /files/{file_id}`, который отдаёт сырые байты и не меняется).
  - `404` через уже существующий обработчик `StoredFileNotFoundError` в `app/main.py` — переиспользуется, без изменений.
  - Зависит от Task 4.

### Phase 3: Тесты, документация, проверка

- [x] **Task 6: Тесты**
  - `tests/modules/files/test_file_parser.py`:
    - PDF: сгенерировать простой PDF с текстом через `reportlab.pdfgen.canvas.Canvas` (dev-зависимость) в память (`io.BytesIO`), проверить `parse_to_text` возвращает `("success",...)` и текст содержит ожидаемую строку.
    - DOCX: `docx.Document()` → `add_paragraph("...")` → сохранить в `io.BytesIO()`, проверить `"success"` и текст.
    - XLSX: `openpyxl.Workbook()` → записать значения в пару ячеек → сохранить в `io.BytesIO()`, проверить `"success"` и текст.
    - Изображение/медиа: `content_type="image/png"` с произвольными байтами (парсер не должен даже пытаться их декодировать) → `(None, "skipped")`.
    - Повреждённый файл поддерживаемого типа: `content_type="application/pdf"` с байтами `b"not a real pdf"` → `(None, "failed")`, без исключения наружу.
  - `tests/modules/files/test_file_service.py`: расширить (или добавить тесты) — `upload_file` с DOCX/XLSX-содержимым сохраняет `extracted_text`/`parse_status="success"` в возвращённом `File`; загрузка с `content_type="image/png"` → `parse_status="skipped"`, `extracted_text is None`; загрузка не падает при `parse_status="failed"` (файл всё равно сохранён и доступен для скачивания).
  - `tests/modules/files/test_file_router.py`: тест на `GET /files/{id}/metadata` — `200` с `extracted_text`/`parse_status` в теле; `404` для отсутствующего `id` (переиспользует уже протестированное поведение `StoredFileNotFoundError`).
  - Зависит от Task 5.

- [x] **Task 7: Документация (обязательный чекпоинт)**
  - `docs/files.md`: новый раздел "Парсинг в текст" — `file_parser.py::parse_to_text()`, поддерживаемые типы (PDF/DOCX/XLSX), явное игнорирование изображений/медиа (`parse_status="skipped"`), обработка ошибок парсинга (`"failed"`, не приводит к падению загрузки), новые поля `File.extracted_text`/`File.parse_status`, новый эндпоинт `GET /files/{id}/metadata`. Отметить, что веха «Работа с файлами» закрыта этим планом.
  - Обновить `README.md`/`AGENTS.md` (новый файл `file_parser.py`, новый эндпоинт в таблице точек входа, обновлённое описание модуля `files` в дереве структуры), `.ai-factory/DESCRIPTION.md` (добавить `pypdf`/`python-docx`/`openpyxl` в раздел "Технологический стек").
  - Через `/aif-docs`.
  - Зависит от Task 1-6.

- [x] **Task 8: Финальная проверка**
  - Пересобрать образ (`docker compose build app`) перед прогоном тестов.
  - `docker compose up -d postgres minio`, `docker compose run --rm app uv run alembic upgrade head`, `docker compose run --rm app uv run pytest` — полный прогон.
  - Проверить компиляцию/импорт новых модулей, отсутствие TODO/debug-маркеров.
  - Ручная сквозная проверка: `docker compose up -d --build`, `curl /health` → `200 OK`; при наличии времени — реальная загрузка PDF/DOCX/XLSX и изображения через `curl -F`, проверка `GET /files/{id}/metadata` на каждый (без блокировки на этом, если окружение не позволяет).
  - `docker compose down`, убедиться, что не осталось файлов, принадлежащих root.
  - Зависит от Task 1-7.
