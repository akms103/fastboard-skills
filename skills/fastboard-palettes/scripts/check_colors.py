#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Независимая проверка: применились ли цвета палитры на странице Fastboard.

Отдельный от сборщика модуль: читает только готовый файл страницы и не знает, чем он собран
(сборщик видит лишь те ключи, которые сам проставил). Смотрит четыре места задания —
фон страницы, фоны виджетов, тексты, разрезы и серии показателей — и падает с кодом 1, если:

  * ссылка пустая там, где по ролям она обязана быть (фон страницы, фон виджета, серия);
  * `colorId` не найден ни в одной группе файла палитры;
  * ключ ссылки не равен ожидаемому `paletteId` (ссылку поставили не в тот механизм);
  * встретилась ссылка неизвестной формы.

Запуск:
    python check_colors.py page.json [--palette palettes/gazprom.json] [--palette-id 55f43476-…] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z", re.I)
PLACEHOLDER = "ПОСТАВИТЬ_ИЗ_ПРОЕКТА"

# Где смотреть: (подпись, обязательна ли ссылка, как достать)
def dget(obj, *path):
    """Безопасный проход по вложенным словарям: нет ветки — None, а не исключение.

    Секции у виджетов разные: у текстового нет `header`, у тепловой карты — `axisIncisionSettings`,
    у таблицы — `legendSettings`. Чекер обязан отдавать строку отчёта на такой странице, а не падать.
    """
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


PLACES = (
    ("фон страницы", True, lambda page, w: (page.get("color") or {}).get("color")),
    ("фон виджета", True, lambda page, w: dget(w, "viewSettings", "styleContainerSettings",
                                               "backgroundSettings", "colorSettings", "background", "color")),
    ("заголовок", False, lambda page, w: dget(w, "viewSettings", "header", "fontColor")),
    ("легенда", False, lambda page, w: dget(w, "viewSettings", "legendSettings", "properties", "fontColor")),
    ("подписи разреза (ось)", False, lambda page, w: dget(w, "viewSettings", "axisIncisionSettings",
                                                          "label", "properties", "fontColor")),
    ("числа оси значений", False, lambda page, w: dget(w, "viewSettings", "axisIndicatorSettings",
                                                       "label", "properties", "fontColor")),
)


def describe(ref) -> tuple[str, str, str]:
    """Ссылка → (вид, id цвета, ключ словаря). Пустая — ('пусто', '', '')."""
    if ref is None:
        return "пусто", "", ""
    if isinstance(ref, list):
        first = ref[0] if ref else {}
        return f"массив значений, {len(ref)}", (first.get("colorId") or ""), (first.get("groupId") or "")
    if isinstance(ref, dict):
        for key, value in ref.items():
            if not isinstance(value, dict):
                continue
            if value.get("type") == "palette":
                return "группа палитры", value.get("groupId", ""), key
            if value.get("colorId"):
                return "цвет палитры", value["colorId"], key
            if value.get("level"):
                return f"уровень темы {value['level']}", "", key
    return "непонятная ссылка", "", ""


def palette_ids(palette_path: Path) -> tuple[set[str], str]:
    """Все id палитры (группы + цвета) и её paletteId."""
    sys.path.insert(0, str(Path(__file__).parent))
    from palette import Palette
    pal = Palette.load(palette_path)
    return pal.own_ids(), str(pal.palette_id)


def main() -> int:
    ap = argparse.ArgumentParser(description="Проверка применения цветов палитры")
    ap.add_argument("page", help="файл страницы Fastboard (*.json)")
    ap.add_argument("--palette", help="файл ролей/палитры: сверить colorId с её группами")
    ap.add_argument("--palette-id", help="ожидаемый ключ ссылок: id палитры проекта")
    ap.add_argument("--json", action="store_true", help="отчёт машинно")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    doc = json.loads(Path(args.page).read_text(encoding="utf-8"))
    page = doc["pagesSettings"][0]
    widgets = page.get("visualizationsV3") or []
    allowed: set[str] = set()
    expected_key = args.palette_id
    if args.palette:
        allowed, pal_id = palette_ids(Path(args.palette))
        expected_key = expected_key or pal_id

    problems: list[str] = []
    summary: list[str] = []
    page_id = str(page["page"].get("id") or "")

    def check(label: str, ref, widget_name: str, required: bool) -> None:
        kind, cid, key = describe(ref)
        summary.append(f"{widget_name:32} {label:24} {kind:18} {(cid or key)[:8]}")
        if kind == "непонятная ссылка":
            problems.append(f"{widget_name}: «{label}» — ссылка неизвестной формы")
        if required and kind == "пусто":
            problems.append(f"{widget_name}: «{label}» пусто, хотя по ролям цвет обязателен")
        if kind.startswith("уровень темы"):
            # уровень темы — другой механизм: ключ ссылки обязан быть id страницы
            if page_id and UUID_RE.match(page_id) and key and key != page_id:
                problems.append(f"{widget_name}: «{label}» — уровень темы ключуется id страницы "
                                f"{page_id[:8]}…, а стоит {key[:8]}…")
        elif expected_key and key and key != expected_key:
            problems.append(f"{widget_name}: «{label}» — ключ ссылки {key[:8]}… вместо paletteId "
                            f"{expected_key[:8]}…")
        if cid and allowed and cid not in allowed:
            problems.append(f"{widget_name}: «{label}» — id {cid[:8]}… не найден в группах палитры")
        if kind == "цвет палитры" and not cid:
            problems.append(f"{widget_name}: «{label}» — ссылка на цвет без colorId")

    # уровень страницы — только фон страницы; фон виджета и тексты проверяются в цикле по виджетам
    for label, required, getter in PLACES[:1]:
        check(label, getter(page["page"], widgets[0] if widgets else {}), "страница", required)

    for w in widgets:
        name = str(dget(w, "viewSettings", "name") or w.get("id") or "виджет")[:32]
        # текстовый виджет — не график: фона по ролям у него может не быть, серий и разрезов нет
        is_text = str(w.get("visualisationType") or "") == "text"
        for label, required, getter in PLACES[1:]:
            check(label, getter(page["page"], w), name, required and not is_text)
        for i, ind in enumerate(dget(w, "dataSettings", "indicators") or []):
            check(f"серия {i + 1}",
                  dget(ind, "settings", "elementSettings", "colorBySettings", "elementColor"), name, True)
            check(f"подписи значений {i + 1}",
                  dget(ind, "settings", "showValue", "colorBySettings", "elementColor"), name, False)
        incs = dget(w, "dataSettings", "incisions") or []
        if not incs:
            if not is_text:
                problems.append(f"{name}: нет разрезов — цвета категорий проверить нечем")
            continue
        inc = incs[0]
        check("разрез (группа)",
              dget(inc, "colorBySettingsValueAndElement", "colorBySettingsElement", "elementColor"),
              name, False)
        if isinstance(inc.get("colors"), list) and inc["colors"]:
            summary.append(f"{name:32} разрез (значения)       массив значений, {len(inc['colors'])} "
                           f"{(inc['colors'][0].get('colorId') or '')[:8]}")
            for item in inc["colors"]:
                if allowed and item.get("colorId") and item["colorId"] not in allowed:
                    problems.append(f"{name}: значение «{item.get('value')}» — цвет "
                                    f"{item['colorId'][:8]}… вне палитры")

    # разные серии — разные цвета: иначе стопка читается как одна серия
    for w in widgets:
        clrs = []
        for ind in dget(w, "dataSettings", "indicators") or []:
            _, cid, _ = describe(dget(ind, "settings", "elementSettings", "colorBySettings", "elementColor"))
            clrs.append(cid)
        if len(set(c for c in clrs if c)) < len([c for c in clrs if c]):
            problems.append(f"{str(dget(w, 'viewSettings', 'name') or 'виджет')[:32]}: у серий повторяются цвета")

    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems, "places": summary},
                         ensure_ascii=False, indent=1))
    else:
        print(f"страница «{page['page']['name']}», виджетов {len(widgets)}"
              f"{', палитра сверена' if allowed else ', палитра не задана — id не проверялись'}")
        for line in summary:
            print("  " + line)
        for p in problems:
            print("  ✗ " + p, file=sys.stderr)
        print("ИТОГ:", "ок — ссылки на цвета на месте" if not problems
              else f"проблем {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
