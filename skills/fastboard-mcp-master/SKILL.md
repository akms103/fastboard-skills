---
name: fastboard-mcp-master
description: Подключение и работа с BI Fastboard через MCP без пользовательского JWT. Эндпоинт {BASE_URL}/api/v3/mcp, авторизация Authorization: Bearer *** (fbpat_), JSON-RPC tools/call. Главный контракт: файлы в arguments.file как строгий объект {contentType, encoding:"base64", data}. Используйте, когда нужно подключиться к Fastboard по MCP, прочитать палитры/страницы/настройки проекта, добавить группу цветов, импортировать страницу или палитру в проект, починить «Multipart tool requires file payload with base64 encoding» или «Текущая сессия более не активна», настроить opencode.json для MCP Fastboard. Триггеры: fastboard mcp, fbpat, import_project_pages, import_palette_groups, storage_upload, «сессия более не активна», paletteId, projectPalettes.
version: 1.0.0
license: CC-BY-4.0
compatibility: "Python 3 (stdlib only). Нужны BASE_URL проекта, PROJECT_ID и личный токен fbpat_ (env FB_MCP / FB_PAT)."
metadata:
  author: team
  version: "1.0.0"
  tags: [fastboard, mcp, jsonrpc, bi, pat, palette, import]
---

# Fastboard через MCP: мастер доступа и операций

Инструкция для нейросети: правила работы, контракт и ловушки, проверенные на живом проекте.
Пользовательская памятка «с нуля» (`USER_GUIDE.md`) в набор скиллов не вложена — если она нужна,
запросить у автора скилла.

## Что это
Fastboard отдаёт доступ по MCP **без пользовательской сессии**: сервер авторизует личный токен проекта (`fbpat_…`). Так можно читать проект и писать в него (палитры, страницы, настройки, модели) — JWT для этого не нужен. JWT требует только REST-фолбэк.

## Данные пользователя и как их использовать
Пользователь присылает (в чат или через переменные окружения `FB_MCP`, `FB_PAT`):
- `BASE_URL` — окружение, например `https://dev.fastboard.online/back`;
- `PROJECT_ID` — борд (первая hex-группа в URL `https://<host>/<PROJECT_ID>/board/<pageId>`);
- `PAT_TOKEN` — личный токен проекта, начинается с `fbpat_`;
- (опц.) `pageId` борда, экспорт эталонной страницы (`*.json`, манифест `pages` + `visualisations`) для снятия формата виджетов-доноров, `colors.json` с группами палитр.

Правила пользования:
- `PROJECT_ID` — это борд, а не страница. Дефолтная первая страница часто `dc056874-305d-11ee-8c70-04d4c47aef75`.
- При импорте с `newPages=true` страница получает **новый id сервера** (тот, что в файле, не сохраняется). Существующие страницы не перетираются.
- Палитра проекта по умолчанию — «Моя палитра 1», id `55f43476-1cd1-11ee-b2df-04d4c47aef75` (зашит одинаково в проектах). Ссылки цвета в файле страницы используют **paletteId** как ключ, тексты уровня темы — **id страницы** как ключ.

## Транспорт (контракт)
```
POST {BASE_URL}/api/v3/mcp
Authorization: Bearer <PAT>
Content-Type: application/json
Accept: application/json, text/event-stream
```
- Тело — обычный JSON-RPC 2.0. Ответ приходит строкой SSE: `event: message` + `data: {…}`.
- Последовательность: `initialize` → `tools/list` → `tools/call`.
- Сервер: `fastboard-mcp` 3.0.0, протокол `2025-06-18`, ~70 инструментов.
- **PAT принимает только MCP-эндпоинт.** На обычный REST он не действует (401 «Текущая сессия более не активна, требуется повторная авторизация»). Для REST нужен свежий сессионный JWT (живёт ~600 секунд).
- `newPages`, `importModels`, `replaceColors` и т.п. в аргументах — **строки** (`"true"`/`"false"`), не булеаны.

## Группы инструментов
- **Чтение `get_*`** (никогда не меняют состояние): `get_project_pages`, `get_first_page_id`, `get_project_palettes`, `get_project_palette_links`, `get_page_visualisations`, `get_page_filters`, `get_page_layers`, `get_global_variables`, `get_project_settings`, `get_project_config`, `get_project_models`, `get_project_themes`, `get_data`, `list_sources`, `data_catalog_*`, `qa_*` и др.
- **Запись `save_*`**: меняют ресурс проекта. **Перед любой записью вызывать `get_last_settings_timestamp({projectId})`** (оптимистичная блокировка). Ключ тела в аргументах называет сервер (см. питфолл про ошибки). Пример подтверждённый: `save_project_palettes` ждёт `{ projectId, projectPalettes: [ <палитра> ] }` (именно `projectPalettes`, не `palette`).
- **Импорт/экспорт файлов (`import_*`, `export_*`) и `storage_upload`**: multipart — см. конверт файла ниже.

## Жёсткий конверт файла (важнее всего)
Multipart-инструменты (`import_project_pages`, `import_palette_groups`, `storage_upload`) принимают файл **только** так:
```json
"file": {
  "contentType": "application/json",   // MIME; не "type", не "name"
  "encoding": "base64",                 // литерал, обязателен
  "data": "<чистый base64, без data:-префикса>"
}
```
Всё остальное сервер считает за «файла нет» и отвечает ошибочно одинаково:
> `Multipart tool requires file payload with base64 encoding`

Что **отклоняется** (проверено): строка base64; `{base64}`; `{data,name,type}` (не хватает `contentType` и `encoding`); массив `[base64]`; data-URI `data:…;base64,…`; MCP-часть `resource`/`blob`; `payload.file`; передача `file` на уровне HTTP-multipart поверх JSON-RPC. Сервер имя файла не читает — подставляет `mcp-upload.json`/`.zip`/`.bin` по `contentType`.

Готовые вызовы:
- страница: `{ projectId, newPages:"true", importModels:"false", file }`;
- палитра: `{ projectId, file, replaceColors:"false" }`;
- хранилище: `{ folderId, file }`;
- zip: `contentType:"application/zip"` + base64 архива.
Успех импорта страницы — ответ `text:"true"` без `isError`.

## Порядок записи (обязательный)
1. `get_last_settings_timestamp({projectId})`;
2. прочитать текущее состояние (`get_project_pages` / `get_project_palettes` / …);
3. изменить копию (добавить группу, новую страницу);
4. записать: `save_project_palettes` / `import_project_pages` / …;
5. перечитать и показать результат.

## Ловушки и обходы
Полная таблица — в `references/pitfalls.md`. Ключевые:
| симптом | причина | обход |
|---|---|---|
| `Multipart tool requires file payload with base64 encoding` | файл не в строгом конверте | использовать ровно `{contentType, encoding:"base64", data}` |
| 401 «Текущая сессия более не активна» на REST с PAT | PAT — только MCP-токен | на REST брать свежий JWT; на MCP — PAT |
| MCP-инструментов нет в сессии | url только хост, лишние кавычки в заголовке, старый токен | полный путь, чистое `Bearer …`, перезапуск приложения (MCP грузится на старте сессии) |
| save падает без понятной причины | неверный ключ тела | прочитать текст ошибки: сервер называет ожидаемое поле (`projectPalettes must be an array` и т.п.) |
| импортированная страница с другим id | сервер переназначает id при `newPages=true` | это норма; подтверждать `get_project_pages` |
| цвета на импортированной странице не проявились | тема не ссылается на палитру | проверить `get_project_palette_links`, что активная тема связана с «Моя палитра 1» |

## Конфиг приложения (чтобы MCP был «из коробки»)
Файл `~/.config/gigatool/opencode.json`. Запись-пример:
```json
"mcp": { "FB_1": { "type": "remote",
  "url": "https://<host>/back/api/v3/mcp",
  "enabled": true,
  "headers": { "Authorization": "Bearer <PAT>" } } }
```
Три правила: url — **полный путь**, не хост; в значении заголовка **нет лишних кавычек** внутри строки; верный и актуальный PAT. После правки — перезапуск приложения (или новая сессия), иначе инструменты не появятся.

## Инструментарий скилла
- `scripts/fb_mcp.py` — готовый клиент: `tools`, `schema <имя>`, `call <имя> [--project id] [--args-file f] [--file путь [--content-type ct]] [--save f]`. `--file` сам собирает правильный конверт. Токен — из `FB_PAT`, адрес — из `FB_MCP`.

## Как отдавать результат
- Называй эндпоинт и аргументы, цитируй ответ сервера; что не подтверждено платформой — помечай.
- Для записей показывай подтверждение чтением (страница появилась в `projectPages`, группа в `groups`).
- Если PAT засветился в чате/git — напомни перевыпустить после работы.