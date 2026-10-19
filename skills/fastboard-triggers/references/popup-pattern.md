# Паттерн «попап по триггеру»: разобранный пример

Проверено на импорте: клик по «⤢» открывает затемнение с панелью, клик по затемнению и по «✖»
закрывает. Одна переменная, четыре объекта.

## Состав

Доска 1600×900. Переменная `Попап детализации`, `status: "false"`.

| # | Объект | Позиция (x,y,w,h) | `isVisible` | Роль |
|---|---|---|---|---|
| 1 | Карточка-источник | 40, 40, 1000, 420 | `true` | — |
| 2 | Стрелка «⤢» | 984, 48, 40, 40 | `true` | писатель `true` |
| 3 | Подложка (на всю доску) | 0, 0, 1600, 900 | `false` | приёмник + писатель `false` |
| 4 | Панель детализации | 300, 180, 1000, 540 | `false` | приёмник |
| 5 | Крестик «✖» | 1244, 188, 40, 40 | `false` | приёмник + писатель `false` |

Стрелка позиционируется относительно карточки: `x = card.x + card.width - 56`, `y = card.y + 8`.
Крестик — относительно панели: `x = panel.x + panel.width - 52`, `y = panel.y + 10`.
Размер активатора 36–40 px: меньше — трудно попасть, больше — перекрывает данные.

## Слои

```jsonc
"indeces": { "layers": [
  "<карточка>",
  …прочие базовые тексты и графики/таблицы…,
  "<стрелка>", "<подложка>", "<панель>", "<крестик>",
  …фильтры…
], "pageId": "<pageId>" }
```

Попап идёт **после** контента: подложка должна накрыть карточки, панель — подложку,
крестик — панель.

## JSON: писатель (стрелка)

```jsonc
{
  "isVisible": true,
  "positionConfig": { "x": 984, "y": 48, "width": 40, "height": 40, … },
  "viewSettings": {
    "name": "Открыть детализацию (⤢)",
    "text": { "text": "⤢", "isShow": true, "fontSize": 30 },
    "group": { "groupId": null, "isGrouped": false, … },
    "styleContainerSettings": { "showBackground": false }
  },
  "events": {
    "variablesSettings": {
      "mode": "common",
      "control": { "view": { "isActive": false, "variableId": "", "variableName": "" } },
      "matches": [],
      "isActive": true,
      "variables": [ { "id": "<uuid>", "status": "true", "variableId": "<varId>" } ],
      "separatedModeVariables": []
    }
  }
}
```

## JSON: подложка (приёмник + писатель)

```jsonc
{
  "isVisible": false,
  "positionConfig": { "x": 0, "y": 0, "width": 1600, "height": 900, … },
  "viewSettings": {
    "name": "Подложка затемнения (попап)",
    "group": { "groupId": null, "isGrouped": false, … },
    "styleContainerSettings": {
      "showBackground": true,
      "backgroundSettings": {
        "isShow": true,
        "blur": 0,
        "colorSettings": { "background": {
          "color": { "<paletteId>": { "type": "color",
                                       "colorId": "<цвет с opacity 45>",
                                       "groupId": "<группа>" } },
          "isShow": true } }
      }
    }
  },
  "events": {
    "variablesSettings": {
      "mode": "common",
      "control": { "view": { "isActive": true, "variableId": "<varId>",
                              "variableName": "Попап детализации" } },
      "matches": [],
      "isActive": true,
      "variables": [ { "id": "<uuid>", "status": "false", "variableId": "<varId>" } ],
      "separatedModeVariables": []
    }
  }
}
```

## JSON: панель (только приёмник)

```jsonc
{
  "isVisible": false,
  "positionConfig": { "x": 300, "y": 180, "width": 1000, "height": 540, … },
  "viewSettings": {
    "name": "Панель детализации (попап)",
    "text": { "text": "{{v}}", "isShow": true, "fontSize": 22 },
    "group": { "groupId": null, "isGrouped": false, … },
    "styleContainerSettings": {
      "showBackground": true,
      "backgroundSettings": { "isShow": true,
        "colorSettings": { "background": { "color": { "<paletteId>": { "type": "color",
          "colorId": "<«фон карточки», opacity 100>", "groupId": "<группа>" } }, "isShow": true } } },
      "borderSettings": { "isActive": true, "width": 1, "radius": 8 }
    }
  },
  "dataSettings": {
    "variables": [ { "id": "<uuid>", "name": "v",
      "settings": { "textPropertiesSettings": { "text": { "text": "Детализация…", "isShow": true } } } } ]
  },
  "events": {
    "variablesSettings": {
      "mode": "common",
      "control": { "view": { "isActive": true, "variableId": "<varId>",
                              "variableName": "Попап детализации" } },
      "matches": [], "isActive": false, "variables": [], "separatedModeVariables": []
    }
  }
}
```

## JSON: крестик (приёмник + писатель)

Как подложка, но `isVisible:false`, маленький размер, фон выключен
(`showBackground:false`), а `variables[]` пишет `false`. Обязательно с `control.view`,
иначе крестик не появится вместе с панелью.

## Типичные ошибки и их цена

| Ошибка | Симптом |
|---|---|
| `isGrouped:true` без `groupId` | не видно ни карточки, ни стрелки, ни панели; таблицы видны |
| Стрелка-писатель без `control.view` | это норма: писателю подписка не нужна |
| Крестик без `control.view` | крестик никогда не появится (он скрыт) |
| Подложка без `control.view` | фон не появляется, закрывать нечего |
| Фон подложки белый/непрозрачный | «белая заглушка» вместо затемнения |
| Попап в начале `layers` | стрелку и панель перекрывают карточки |
| `variableId` не совпадает с `page.variables` | клик «ничего не делает» |
| `status:"invert"` у не-boolean | поведение не определено |
