#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Независимая проверка триггеров на готовой странице Fastboard.

Читает только файл страницы (не сборщик) и ищет поломки, которые не видны в UI,
но делают триггер нерабочим или виджет невидимым.

Использование:
    python check_triggers.py page.json
    python check_triggers.py page.json --strict     # предупреждения = ошибки

Код возврата: 0 — ошибок нет, 1 — есть ошибки (или предупреждения при --strict).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

VALID_STATUS = {"true", "false", "invert"}


def load(path: Path) -> dict:
    """Читает страницу; понимает и чистый JSON, и MCP-обёртку result.content[].text."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "result" in data:
        content = (data.get("result") or {}).get("content") or []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                return json.loads(item["text"])
    return data


def widget_name(w: dict) -> str:
    vs = w.get("viewSettings") or {}
    name = vs.get("name") or w.get("name") or ""
    return str(name)[:48] or "<без имени>"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    strict = "--strict" in sys.argv

    doc = load(path)
    ps = (doc.get("pagesSettings") or [{}])[0]
    page = ps.get("page") or {}
    widgets = ps.get("visualizationsV3") or []
    filters = ps.get("filtersV3") or []
    layers = ((ps.get("indeces") or {}).get("layers")) or []

    errors: list[str] = []
    warnings: list[str] = []
    dead_bindings: list[str] = []

    # ── переменные страницы ────────────────────────────────────────────────
    variables: dict[str, dict] = {}
    for v in page.get("variables") or []:
        vid = v.get("id")
        if not vid:
            errors.append("переменная страницы без id")
            continue
        variables[vid] = v
        if v.get("type") != "boolean":
            warnings.append(f"переменная «{v.get('name')}»: type={v.get('type')!r}, "
                            f"а события рассчитаны на boolean")
        if str(v.get("status")) not in ("true", "false"):
            errors.append(f"переменная «{v.get('name')}»: status={v.get('status')!r}, "
                          f"ожидается 'true' или 'false'")

    # ── виджеты и фильтры ─────────────────────────────────────────────────
    ids: list[str] = []
    writers = receivers = 0

    for w in widgets + filters:
        wid = w.get("id")
        name = widget_name(w) if w in widgets else str(w.get("name") or "<фильтр>")
        if not wid:
            errors.append(f"«{name}»: пустой id")
        ids.append(wid)

        vs = w.get("viewSettings") or {}

        # группировка без группы — виджет не рисуется
        group = vs.get("group") if isinstance(vs.get("group"), dict) else None
        if group and group.get("isGrouped") and not group.get("groupId"):
            errors.append(f"«{name}»: isGrouped=true при groupId=null — виджет не отрисуется; "
                          f"поставьте isGrouped=false")

        events = w.get("events") or {}
        vset = events.get("variablesSettings") or {}
        control = (vset.get("control") or {}).get("view") or {}

        # приёмник
        if control.get("isActive"):
            receivers += 1
            cvid = control.get("variableId")
            if not cvid:
                dead_bindings.append(name)
            elif cvid not in variables:
                errors.append(f"«{name}»: приёмник ссылается на переменную {cvid}, "
                              f"которой нет в page.variables")

        # писатель
        if vset.get("isActive"):
            writers += 1
            writes = vset.get("variables") or []
            if not writes:
                errors.append(f"«{name}»: variablesSettings.isActive=true, но variables[] пуст")
            for rec in writes:
                status = str(rec.get("status"))
                rec_var = rec.get("variableId")
                if status not in VALID_STATUS:
                    errors.append(f"«{name}»: status={status!r}, "
                                  f"допустимо {sorted(VALID_STATUS)}")
                if not rec_var:
                    errors.append(f"«{name}»: запись без variableId")
                elif rec_var not in variables:
                    errors.append(f"«{name}»: пишет переменную {rec_var}, "
                                  f"которой нет в page.variables")
                elif status == "invert" and variables[rec_var].get("type") != "boolean":
                    errors.append(f"«{name}»: invert у не-boolean переменной "
                                  f"«{variables[rec_var].get('name')}»")

        # переход-артефакт
        goto = events.get("goTo") or {}
        if goto.get("isActive") and not goto.get("to"):
            warnings.append(f"«{name}»: goTo.isActive=true, но to=null "
                            f"(полунастроенный переход)")

    # ── уникальность id ───────────────────────────────────────────────────
    seen: set[str] = set()
    for wid in ids:
        if wid and wid in seen:
            errors.append(f"повторяющийся id виджета/фильтра: {wid}")
        seen.add(wid)

    # ── слои ──────────────────────────────────────────────────────────────
    if not layers:
        errors.append("indeces.layers пуст — порядок отрисовки не задан, будут перекрытия")
    else:
        if len(layers) != len(set(layers)):
            errors.append("indeces.layers содержит дубли")
        # Виджеты/фильтры обязаны присутствовать. Лишние id в слоях платформа
        # терпит (в боевых выгрузках встречаются устаревшие записи), поэтому это
        # предупреждение, а не ошибка.
        missing = set(i for i in ids if i) - set(layers)
        if missing:
            warnings.append(f"в слоях нет {len(missing)} объект(ов): "
                            f"{[m[:8] for m in list(missing)[:4]]} — платформа возьмёт "
                            f"для них порядок из массива виджетов (риск перекрытия)")
        groups = {g.get("id") for g in (ps.get("groupsVisualizationsV3") or [])}
        extra = set(layers) - set(i for i in ids if i) - groups
        if extra:
            warnings.append(f"в слоях {len(extra)} лишних id (не виджет/фильтр/группа) — "
                            f"обычно устаревшие записи, работе не мешают")

    # ── отчёт ─────────────────────────────────────────────────────────────
    if dead_bindings:
        preview = ", ".join(f"«{n}»" for n in dead_bindings[:3])
        tail = f" и ещё {len(dead_bindings) - 3}" if len(dead_bindings) > 3 else ""
        warnings.append(
            f"{len(dead_bindings)} виджет(ов) с «мёртвой» привязкой control.view "
            f"(isActive=true, variableId пуст): {preview}{tail}. "
            f"Это остаток конфигурации — почистите до isActive:false")

    print(f"файл: {path.name}")
    print(f"переменных: {len(variables)} | виджетов: {len(widgets)} | фильтров: {len(filters)} "
          f"| писателей: {writers} | приёмников: {receivers} | слоёв: {len(layers)}")

    for e in errors:
        print(f"  ✗ {e}")
    for w in warnings:
        print(f"  ! {w}")

    if not errors:
        print("  ошибок нет")
    if strict and warnings:
        print("  --strict: предупреждения считаются ошибками")
        return 1
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
