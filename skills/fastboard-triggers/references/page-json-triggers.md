# Триггеры в JSON страницы Fastboard: полный справочник полей

Снято с боевых выгрузок (`Donor.json` проекта «Кредитный портфель») и живых импортов.

## Каркас страницы

```jsonc
{
  "pagesSettings": [{
    "page": { "id", "name", "color", "image", "variant", "isHidden",
              "variables": [...], "boardSettings": {"sizes": {"width", "height"}},
              "accessSettings", "isShowWorkSpace", "autoRefreshSettings", "isHomePage" },
    "visualizationsV3": [ /* виджеты */ ],
    "groupsVisualizationsV3": [ /* группы; при работе с триггерами обычно пусто */ ],
    "filtersV3": [ /* фильтры */ ],
    "enabledFiltersV3": [ /* включённые фильтры */ ],
    "indeces": { "layers": [ "<id1>", "<id2>", … ], "pageId": "<pageId>" },
    "filterListAgree": []
  }],
  "models": [], "metaModels": []
}
```

`indeces.layers` — **порядок отрисовки снизу вверх**: первый элемент рисуется первым
(оказывается ниже), последний — поверх.

## Переменные страницы

```jsonc
"variables": [
  { "id": "bcb6a980-…", "name": "Триггер 0", "type": "boolean", "status": "true" }
]
```

- `type` — на практике всегда `"boolean"`.
- `status` — строка `"true"` / `"false"`, стартовое значение при загрузке страницы.
- `name` используется только для UI; ссылки идут по `id`.

## `events` виджета

Есть у каждого виджета и фильтра. Поля, не относящиеся к триггерам, всё равно присутствуют
в дефолтном виде.

```jsonc
"events": {
  "goTo":         { "to": null, "isActive": false },
  "goToHref":     { "to": null, "isActive": false, "openWindowType": "self" },
  "activateTo":   { "to": null, "isActive": false },
  "activateObject": { "filters": null, "isActive": false },
  "filterSettings": { "isFiltering": false, "moreThanOne": false,
                      "applyToAllPages": false, "filterInfluences": null,
                      "isInfluenceItself": true, "responseToExternalDrillDown": false },
  "variablesSettings": { … },                       // ← триггеры
  "isReactingToFilter": true,
  "transitionSettings": { … }                       // ← расширенные переходы
}
```

### Переходы

| Поле | Назначение | Заполнение |
|---|---|---|
| `goTo` | переход на страницу дашборда | `to: {id, type:"page"}`, `isActive:true` |
| `goToHref` | внешняя ссылка | `to: "<url>"`, `isActive:true`, `openWindowType:"self"|"blank"` |
| `activateTo` | активировать страницу | `to: "<pageId>"`, `isActive:true` |
| `activateObject` | активировать фильтр по клику | `filters: [{id, elementId, isActive, selectedValues}]` |
| `transitionSettings` | расширенный переход | см. ниже |

```jsonc
"transitionSettings": {
  "isActive": true,
  "typeTransition": "object",        // object — на страницу, hyperlink — по ссылке
  "openWindowType": "self",
  "settings": {
    "object":    { "type": "common", "common": { "pageTo": "<pageId>" }, "separated": { "links": [] } },
    "hyperlink": { "type": "common", "common": { "link": "<url>" }, "database": { "fieldName": null },
                   "separated": { "links": [] } }
  }
}
```

`goTo.isActive:true` при `to:null` — полунастроенный артефакт; считайте переход выключенным.

## `variablesSettings` — сердце триггера

```jsonc
"variablesSettings": {
  "mode": "common",                       // "common"; "separate" — отдельные наборы
  "control": {
    "view": {                             // ← ПРИЁМНИК
      "isActive": false,
      "variableId": "",
      "variableName": ""
    }
  },
  "matches": [],                          // маппинг значений для не-boolean, обычно пуст
  "isActive": false,                      // ← ПИСАТЕЛЬ: включён ли триггер по клику
  "variables": [],                        // ← чтó писать при клике
  "separatedModeVariables": []            // заполняется при mode:"separate"
}
```

### Писатель

```jsonc
"isActive": true,
"variables": [
  { "id": "<uuid записи>", "status": "true",  "variableId": "<id переменной>" },
  { "id": "<uuid записи>", "status": "false", "variableId": "<id другой>" }
]
```

- `status` — присваивание, не сравнение: `"true"` / `"false"` / `"invert"`.
- `id` записи — произвольный uuid (уникален в пределах виджета).
- Одна кнопка пишет сколько угодно переменных; порядок записей не важен.
- `isActive:false` при непустом `variables[]` — пассивная, «выключенная» кнопка (дубль/остаток).

### Приёмник

```jsonc
"control": { "view": { "isActive": true, "variableId": "<id>", "variableName": "Попап детализации" } }
```

Приёмник + писатель одновременно (фон, крестик, закрывающая подложка):

```jsonc
"control": { "view": { "isActive": true, "variableId": "<id>", "variableName": "Попап" } },
"isActive": true,
"variables": [ { "id": "<uuid>", "status": "false", "variableId": "<id>" } ]
```

## `isVisible`

Верхнеуровневый boolean виджета — **стартовое** состояние. Не связан с переменной в файле:
связку «переменная → видимость» движок строит из `control.view` в рантайме.
Скрытые члены попапа: `isVisible:false`; переменная стартует в `"false"`.

## Группировка (критично)

```jsonc
"viewSettings": {
  "group": {
    "groupId": null,
    "isGrouped": false,             // ← ОБЯЗАТЕЛЬНО false, если группы нет
    "positionConfig": { … }
  }
}
```

Если `isGrouped:true`, а `groupId` пуст или самой группы нет в `groupsVisualizationsV3`,
**виджет не отрисовывается**. Доноры часто держат text-виджеты в группах, поэтому после
клонирования и обнуления чужого `groupId` надо явно поставить `isGrouped:false`.

## Позиционирование

```jsonc
"positionConfig": {
  "x": 20, "y": 264, "width": 575, "height": 128,
  "maxWidth": null, "minWidth": null, "maxHeight": null, "minHeight": null,
  "sticking": { "vertical": "flex-start", "horizontal": "flex-start" }
}
```

- `x`, `y` — левый верхний угол на доске, отсчёт от верхнего левого угла страницы.
- `width`/`height` — px. `sticking` — привязка выравнивания (`flex-start`/`center`/`flex-end`).
- Поворота и z-index в `positionConfig` нет — порядок задаётся только `indeces.layers`.
- У фильтров и групп та же схема; у членов группы координаты локальны.

## Попап: геометрия и слои

Типовая раскладка для доски `W×H`:

| Объект | x | y | width | height |
|---|---|---|---|---|
| Стрелка (в углу источника) | `src.x + src.width - 56` | `src.y + 8` | 40 | 40 |
| Подложка | 0 | 0 | W | H |
| Панель | `(W-1000)/2` | `(H-540)/2` | 1000 | 540 |
| Крестик | `panel.x + panel.width - 52` | `panel.y + 10` | 40 | 40 |

Слои снизу вверх: базовые тексты → графики/таблицы → попап (стрелка, подложка, панель, крестик)
→ фильтры.

## Цвета

- Текст: ссылка на палитру `{ "<paletteId>": { "type": "color", "colorId": "<id>", "groupId": "<id>" } }`
  — рабочий вариант на боевых страницах.
- Фон подложки: цвет палитры с `opacity < 100` (полупрозрачность живёт в самом цвете палитры).
- Фон панели: непрозрачный «фон карточки» из палитры.

Подробнее — скилл `fastboard-palettes`.
