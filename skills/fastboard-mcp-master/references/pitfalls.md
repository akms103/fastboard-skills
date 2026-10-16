# Fastboard MCP: таблица проблем и обходов (по опыту живого проекта)

## Транспорт и авторизация

| симптом | причина | обход |
|---|---|---|
| `401 Unauthorized` на `GET /back/api-docs` даже с JWT | swagger за базовой HTTP-auth (realm «Swagger») | спека закрыта; читать контракты из исходников фронта и текста ошибок сервера |
| `401 Текущая сессия более не активна, требуется повторная авторизация` на REST с `fbpat_…` | PAT — только для MCP-эндпоинта, не для REST | на REST брать свежий сессионный JWT; на MCP — PAT |
| `POST /mcp`, `/api/mcp`, `/sse` → 405 от nginx | эти пути раздают только GET (SPA) | MCP живёт под `/back/api/v3/mcp` |
| `POST /back/mcp`, `/back/api/v1/mcp` и пр. → 404 «Cannot POST /mcp» | не те пути | правильный: `${BASE_URL}/api/v3/mcp` |
| JWT `expt - iat = 600` | сессия живёт 10 минут | не хранить JWT; на долгую работу — PAT по MCP |
| в `tools/list` у multipart-инструментов нет ключа `file` | схема собирается только из path/query (projectId, newPages…) | формат не виден в схеме — фиксирован ниже в этом документе |

## Файл в tools/call (главная ловушка)

Ошибка `Multipart tool requires file payload with base64 encoding` возникает, когда файл передан **не** строгим объектом. Сервер проверяет: объект, `contentType` — строка, `encoding === "base64"`, `data` — строка. Иначе считает, что файла нет.

Рабочий конверт:
```json
"file": { "contentType": "application/json", "encoding": "base64", "data": "<base64>" }
```
Отклоняется (проверено на живом сервере): строка base64; `{base64}`; `{data,name,type}`; `[base64]`; data-URI; MCP-часть `resource`/`blob`/`text`; `payload.file`; HTTP-multipart поверх JSON-RPC. Имя файла сервер игнорирует (подставляет по contentType).

## Записи и оптимистичная блокировка

- Перед записью всегда `get_last_settings_timestamp`, иначе конфликт.
- Ключ тела сервер называет в тексте ошибки. Случай: `save_project_palettes` ждёт `projectPalettes` (массив) — ошибка `projectPalettes should not be empty / must be an array`. Читай текст ответа, а не гадай.
- `safe_project_palettes {projectId, projectPalettes:[<палитра>]}` возвращает `Ok`; перечитывай `get_project_palettes` для подтверждения.

## Импорт страницы

- `import_project_pages {projectId, newPages:"true", importModels:"false", file}` → успех: `text:"true"`, без isError.
- Импортированная страница получает **новый id** (в файле id игнорируется) и имя-суффикс `…_copy_1`, если такое имя уже было; существующие страницы не трогаются.
- `import-preview` (dry run) существует — проверить до реального импорта.
- REST-импорт: `POST /back/api/v2/project/pages/{projectId}/import?newPages=&importModels=` с multipart `file` — работает только со свежим JWT (не с PAT).

## Палитра

- Палитра проекта по умолчанию — «Моя палитра 1», `paletteId = 55f43476-1cd1-11ee-b2df-04d4c47aef75` (зашит одинаково). В файле ролей клиента — этот id как ключ.
- Чтение: `get_project_palettes`. Добавление группы: `import_palette_groups {projectId, file, replaceColors:"false"}` (тот же конверт файла) либо `save_project_palettes {projectId, projectPalettes:[…]}`.
- Ссылки цвета в странице: ключ словаря = paletteId. Тексты (fontColor) — ключ = **id страницы**, значение `{type:"color", level:1..5}` (тексты палитрой не красятся — это отдельный механизм).

## Конфиг приложения (MCP не появляется)

Файл `~/.config/gigatool/opencode.json`, сервер `FB_1`. Три типичные поломки:
1. `url` только хост (`https://dev.fastboard.online`) без пути → добавить `/back/api/v3/mcp`.
2. заголовок со лишними кавычками внутри значения (`"\"Bearer …\""`) → убрать: `"Bearer <PAT>"`.
3. старый/просроченный/чужой токен → заменить актуальным.
После правки JSON проверить `json.load`; нужен перезапуск приложения или новая сессия, иначе МCP-инструменты не подгрузятся. Резервную копию конфига делать до правки.

## Мелочи окружения

- PowerShell съедает кавычки в `python -c '…'` — вместо инлайна писать временный `.py` и запускать файлом; кириллица в путях/аргументах — тоже через файл или `--args-file`.
- Консоль Windows по умолчанию cp1251: ставить `PYTHONIOENCODING=utf-8` и не печатать `\u2192`/✓ в stdout.
- Крупные ответы MCP обёрнуты экранированной строкой `"text": "{\"kind\"…}"` — парсить `json.loads` внутреннего текста.