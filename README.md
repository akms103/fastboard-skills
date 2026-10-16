# agent-skills

Репозиторий командных скиллов для агентских систем. Один источник правды — папка `skills/`,
один формат — открытый стандарт [Agent Skills](https://agentskills.io/specification)
(`SKILL.md` + YAML-frontmatter). Из этой же папки репозиторий подключается как **tap** в Hermes,
как каталог скиллов в Claude Code, Codex CLI и Cursor.

## Структура

```
agent-skills/
├── AGENTS.md                  # правила репозитория для агентов (читается Codex, Cursor, Grok, Gemini CLI, ...)
├── CLAUDE.md                  # короткий указатель для Claude Code
├── CONTRIBUTING.md            # процесс: ветка → проверки → PR → мерж
├── skills/                    # ★ единственный источник правды
│   ├── dashboard-build/       # скилл: дашборд под ключ (бриф → предпросмотр → сборка)
│   │   ├── SKILL.md
│   │   ├── references/        # длинные методички, грузятся по требованию
│   │   ├── templates/         # скелеты: HTML-предпросмотр, сборщик страницы
│   │   ├── scripts/           # проверки, запускаемые скиллом
│   │   └── agents/openai.yaml # необязательная витрина для Codex/ChatGPT
│   └── bi-dashboard-styleguide/  # скилл: стиль дашборда и проверка стиля
│       ├── SKILL.md
│       ├── references/        # принципы, токены, нормализация настроек, правила проверки
│       ├── templates/         # стартовый файл токенов
│       └── scripts/           # чекер стиля готовой страницы
│   ├── fastboard-palettes/    # скилл: палитры Fastboard (создать → роли → применить → проверить)
│   │   ├── SKILL.md
│   │   ├── references/        # логика применения, формат colors.json и цветовых ссылок
│   │   ├── templates/         # скелет файла ролей палитры
│   │   └── scripts/           # создание группы цветов, файл ролей, независимый чекер цветов
│   └── fastboard-mcp-master/  # скилл: доступ к Fastboard по MCP на личном токене fbpat_
│       ├── SKILL.md
│       ├── references/        # таблица проблем и обходов (транспорт, файл, записи, конфиг)
│       └── scripts/           # клиент MCP: tools / schema / call
├── scripts/
│   ├── install.mjs            # разложить skills/ по каталогам агентских систем
│   └── validate-skills.mjs    # проверка frontmatter по спецификации Agent Skills
├── skills.sh.json             # категории для Skills Hub в Hermes
└── .github/
    ├── workflows/validate.yml # CI: валидатор + сухой прогон установщика
    └── pull_request_template.md
```

Каталоги `.claude/skills/`, `.cursor/skills/`, `.agents/skills/`, `.hermes/skills/` внутри
репозитория **не коммитятся** — их создаёт установщик (ссылками на `skills/`, чтобы не было
расхождений между копиями).

## Скиллы

### `dashboard-build` — дашборд под ключ

Цепочка: факты из файлов → бриф вопросами → HTML-предпросмотр в реальных координатах доски →
сборщик страницы BI → приёмка с независимой проверкой. Внутри: цепочка вопросов и типовые
противоречия, спецификация предпросмотра, инварианты сборщика, специфика Fastboard, скелет
HTML-предпросмотра, скелет сборщика и `check_page.py`.
Отдельный режим — точечная правка чужой живой страницы, когда сборщика нет: карта «что просят
в UI → куда лезть в JSON» и доказательная проверка правки (изменённых путей ровно N, лишних 0).

### `bi-dashboard-styleguide` — стиль дашборда

Чистый нейтральный стиль как контракт: принципы с источниками → токены (отступы 4/12/20/40, шкала
кеглей 12/14/16/20/28, роли уровней темы, форма) → внедрение в сборщик → нормализация донорских
настроек виджетов → проверка чекером (`check_style.py`, 16 правил, код 1 при нарушениях).
Внутри: разбор источников (Carbon, Few, Databricks, Digital Agency, Red Hat), таблицы токенов
с привязкой к ключам формата страницы, список донорского наследия (шрифты, сетка, чужие тексты,
blur, рамки, зум, анимация), правила проверки, стартовый файл токенов и независимый чекер.

### `fastboard-palettes` — палитры: создать → роли → применить → проверить

Четыре артефакта, которые остаются в проекте: `colors.json` (реестр групп цветов), файл ролей
(фон страницы, фон виджета, серии, разрез, тексты), собранная страница, где нет ни одного hex —
только ссылки `paletteId → groupId → colorId`, и отчёт независимого чекера.
Внутри: форматы `colors.json` и обеих цветовых ссылок, карта «что где в JSON страницы», порядок
обработки (сантайз → нормализация → палитра, иначе чистка сносит цвета), скрипт создания группы
цветов, файл ролей, `check_colors.py` (код 1 при мёртвых ссылках) и таблица «что подтверждено
на импорте, а что требует образца».

### `fastboard-mcp-master` — доступ к Fastboard по MCP

Проект читается и правится **без пользовательской сессии**: MCP-эндпоинт `<BASE_URL>/api/v3/mcp`
авторизует личный токен проекта (`fbpat_…`), JSON-RPC `tools/call`. Внутри: строгий конверт файла
`{contentType, encoding:"base64", data}` (на любую другую форму сервер отвечает
«Multipart tool requires file payload with base64 encoding»), обязательный порядок записи
с `get_last_settings_timestamp`, таблица проблем «симптом → причина → обход» (401 на REST с PAT,
405/404 на чужих путях, MCP не появился в сессии) и клиент `scripts/fb_mcp.py` с командами
`tools` / `schema` / `call --file`. Рядом — памятка для человека `references/USER_GUIDE.md`:
какие данные собрать (BASE_URL, PROJECT_ID, PAT) и какое сообщение передать агенту.

Что из этого запускается руками — в разделе «Проверки внутри скилла»; как отдать команде —
в разделе «Подключение».

## Куда смотрит каждая система

| Система | Личный уровень | Уровень проекта | Каталог скиллов |
| --- | --- | --- | --- |
| Hermes Agent | `~/.hermes/skills/` | `.agents/skills/` (нужен `hermes skills trust`) | `~/.hermes/skills/` — родной; tap-репозиторий ставит в него же |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` | свой, `.agents/skills` не читает |
| Codex CLI | `~/.agents/skills/` (устаревшее, но читаемое — `~/.codex/skills/`) | `.agents/skills/` (от рабочего каталога до корня репо) | `.agents/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` | `.cursor/skills/` (с 2.4) |
| Прочие (Gemini CLI, Goose, OpenCode, Copilot, …) | по своей документации | читают `AGENTS.md` | поддержка стандарта `SKILL.md` | 

Общего автообнаружения нет: формат один, а пути у всех разные — поэтому установщик
раскладывает ссылки во все каталоги сразу.

## Подключение

### 1. Как tap в Hermes (для всей команды)

```bash
hermes skills tap add sn0wy-owl/fastboard-skills     # один раз
hermes skills search dashboard                 # найти
hermes skills install sn0wy-owl/fastboard-skills/dashboard-build
hermes skills install sn0wy-owl/fastboard-skills/bi-dashboard-styleguide
hermes skills install sn0wy-owl/fastboard-skills/fastboard-palettes
hermes skills install sn0wy-owl/fastboard-skills/fastboard-mcp-master
hermes skills update                           # подтянуть новые версии
```

### 2. Установщиком — во все системы сразу

```bash
node scripts/install.mjs --scope user            # в личные каталоги всех систем
node scripts/install.mjs --scope project         # в каталоги текущего проекта
node scripts/install.mjs --target claude,codex   # выборочно
node scripts/install.mjs --mode copy             # копией, а не ссылкой (если ссылки запрещены)
node scripts/install.mjs --dry-run               # показать, что будет сделано
```

По умолчанию создаются **ссылки** (на Windows — junctions, прав администратора не требуют),
поэтому правка скилла в `skills/` сразу видна всем агентам. `--mode copy` — для сред, где
ссылки запрещены; копии надо переустанавливать после обновления.

После установки на уровне проекта: Claude Code и Codex видят скиллы сразу; Hermes — после
доверия к репозиторию. Автоопределение корня проекта иногда не срабатывает (например, при
запуске из MSYS-оболочки), тогда путь передаётся явно:

```bash
hermes skills trust "C:/путь/к/agent-skills"
hermes skills untrust "C:/путь/к/agent-skills"   # отозвать
```

### 3. Вручную, если нужно

```bash
# Claude Code, личный уровень
ln -s "$PWD/skills/dashboard-build" ~/.claude/skills/dashboard-build      # macOS/Linux
mklink /J "%USERPROFILE%\.claude\skills\dashboard-build" "%CD%\skills\dashboard-build"  # cmd

# Hermes: общий каталог скиллов через конфиг
hermes config set skills.external_dirs '["~/agents/agent-skills/skills"]'
```

## Как пользоваться скиллом

Скилл не нужно «запускать»: агент сам подгружает его, когда задача совпала с `description`.
Но можно вызвать и явно — синтаксис у систем разный:

| Система | Явный вызов | Где посмотреть, что скилл виден |
| --- | --- | --- |
| Hermes Agent | `/dashboard-build сделай лист по продажам`, `/bi-dashboard-styleguide сведи стиль к нейтральному` — слэш-командой; можно сцепить несколько: `/dashboard-build /bi-dashboard-styleguide …` | `hermes skills list` (личные и установленные); для репозитория — `hermes skills trust <путь>` печатает, сколько проектных скиллов найдено |
| Claude Code | `/dashboard-build` — скиллы и старые команды из `.claude/commands/` работают одинаково | список слэш-команд в сессии |
| Codex CLI | `$dashboard-build` или выбор из списка по `$` | там же, в автодополнении по `$` |
| Cursor | из слэш-меню (поддержка скиллов с 2.4) | слэш-меню |

Пример запроса, на который скилл срабатывает сам:

> Сделай дашборд по продажам за 8 месяцев: выручка, заказы, средний чек, динамика по каналам.

Дальше агент идёт по цепочке из `SKILL.md`: сначала выясняет факты из файлов, потом задаёт
вопросы, потом собирает HTML-предпросмотр — и только потом страницу платформы.

### Проверки внутри скилла

Шаблон сборщика и валидатор страницы запускаются и вручную — так проверяют свои правки и так
можно быстро увидеть, что скилл рабочий:

```bash
cd skills/dashboard-build
python3 templates/builder.py --out page.json     # сборка + самопроверки
python3 scripts/check_page.py page.json          # независимая проверка результата

cd skills/bi-dashboard-styleguide
python3 scripts/check_style.py page.json         # стиль: 16 правил, код 1 при нарушениях

cd skills/fastboard-palettes
python3 scripts/add_palette.py colors.json "Заказчик" "#0079c2:основной" "#4fa3db:светлый"
python3 scripts/palette.py palette-roles.json    # файл ролей: что заполнено, что ждёт id
python3 scripts/check_colors.py page.json --palette palette-roles.json   # цвета доехали?

cd skills/fastboard-mcp-master
FB_PAT=fbpat_… FB_MCP=https://<хост>/back/api/v3/mcp python3 scripts/fb_mcp.py tools
```

(файл `page.json` — рабочий артефакт, в git не попадает)

### Обновление

| Как подключено | Как получить обновление |
| --- | --- |
| Hermes, через tap | `hermes skills check` затем `hermes skills update` |
| Установщиком, `--mode link` (по умолчанию) | ничего: правка в репозитории видна сразу (сделай `git pull`) |
| Установщиком, `--mode copy` | повторить `node scripts/install.mjs --scope user` (или `--scope project`) |

## Как добавить скилл

Полный процесс (ветка, PR, версионирование, definition of done) — в [`CONTRIBUTING.md`](CONTRIBUTING.md).
Коротко:

1. `mkdir -p skills/<имя>` — имя каталога = `name:` во frontmatter, только строчные буквы,
   цифры и одиночные дефисы.
2. Написать `SKILL.md`: обязательны `name` и `description`. `description` — это триггер, по
   которому агент решает, грузить скилл или нет: пиши «что делает + когда применять», а не
   заголовок.
3. Длинные методички — в `references/`, готовые к использованию файлы — в `templates/`,
   исполняемые проверки — в `scripts/`. Всё это лежит рядом со `SKILL.md` и грузится по
   требованию, а не целиком.
4. Проверить: `node scripts/validate-skills.mjs`.
5. Закоммитить и открыть PR. Каталоги-ссылки внутри репозитория не коммитятся — их восстановит
   установщик.

Правило репозитория: **скилл — это процедура, а не лог.** Никаких номеров задач, дат и
историй инцидентов; только шаги, инварианты и грабли, которые повторятся.

## Проверка

```bash
node scripts/validate-skills.mjs        # frontmatter + ссылки на файлы
```

CI гоняет то же самое на каждый push и pull request.

## Лицензия

CC-BY-4.0 (см. `LICENSE`) — скиллы можно свободно копировать и адаптировать внутри компании
и за её пределами, с указанием авторства.
