#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Роли палитры: файл ролей → ссылки для страницы Fastboard.

Зачем: палитра проекта — это реестр цветов, а странице нужны ссылки «палитра → группа → цвет»
в конкретных местах. Роли фиксируют это соответствие один раз на проект.

Разновидности ролей (разные механизмы платформы!):

  * палитровые — `page_background`, `widget_background`, `incision_palette`, `series_1…4`:
    в файле ролей нужны `groupId` (и `colorId`, кроме разреза), на страницу уезжает ссылка
    `{"<paletteId>": {"type": "color", "groupId": …, "colorId": …}}`
    или для группы целиком `{"<paletteId>": {"type": "palette", "groupId": …}}`;
  * текстовые — `header_text`, `caption_text`, `value_text`, `unit_text`:
    тексты красятся уровнями темы, а не палитрой: `{"<pageId>": {"type": "color", "level": 1…5}}`.
    `hex` у них нужен только макету.

Проверка файла ролей:

    python palette.py palettes/gazprom.json

Использование из сборщика:

    from palette import Palette, ROLE_SERIES, ROLE_WIDGET_BG, ROLE_INCISION
    pal = Palette.load("palettes/gazprom.json")
    assert not pal.validate(), "палитра заполнена не полностью"
    page["color"] = {"color": pal.color_ref(ROLE_PAGE_BG), "isActive": True}
    ind["settings"]["elementSettings"]["colorBySettings"]["elementColor"] = pal.color_ref(ROLE_SERIES[0])
    inc["colorBySettingsValueAndElement"]["colorBySettingsElement"]["elementColor"] = \\
        pal.palette_ref(ROLE_INCISION)          # категории берут цвета из группы
    props["fontColor"] = {PAGE_ID: pal.color_scope(ROLE_HEADER)}   # текст — уровень темы
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z", re.I)

ROLE_PAGE_BG = "page_background"
ROLE_WIDGET_BG = "widget_background"
ROLE_INCISION = "incision_palette"
ROLE_SERIES = ["series_1", "series_2", "series_3", "series_4"]
PALETTE_ROLES = [ROLE_PAGE_BG, ROLE_WIDGET_BG, ROLE_INCISION] + ROLE_SERIES

ROLE_HEADER = "header_text"
ROLE_CAPTION = "caption_text"
ROLE_VALUE = "value_text"
ROLE_UNIT = "unit_text"
TEXT_ROLES = [ROLE_HEADER, ROLE_CAPTION, ROLE_VALUE, ROLE_UNIT]

ROLES = PALETTE_ROLES + TEXT_ROLES
PLACEHOLDER = "ПОСТАВИТЬ_ИЗ_ПРОЕКТА"

# Уровни темы для текстов по умолчанию: заголовки темнее, подписи светлее
DEFAULT_LEVELS = {ROLE_HEADER: 4, ROLE_CAPTION: 3, ROLE_VALUE: 1, ROLE_UNIT: 2}


class Palette:
    """Палитра проекта: группы цветов + роли (что куда ставится)."""

    def __init__(self, doc: dict, path: Path | None = None):
        self.path = path
        self.doc = doc
        self.name = doc.get("name") or (path.stem if path else "палитра")
        self.palette_id = doc.get("paletteId")
        self.source = doc.get("source", "")
        self.roles = doc.get("roles", {})
        self.groups: dict[str, dict] = {}
        self.groups_errors: list[str] = []
        groups_file = doc.get("groupsFile")
        if groups_file:
            gp = (path.parent / groups_file) if path else Path(groups_file)
            if gp.exists():
                for g in json.loads(gp.read_text(encoding="utf-8")):
                    if g.get("id"):
                        self.groups[g["id"]] = g
            else:
                # не падаем трейсбеком: файл групп может ещё не существовать
                self.groups_errors.append(
                    f"groupsFile «{groups_file}» не найден рядом с файлом ролей ({gp})")
        for g in doc.get("groups", []):
            if g.get("id"):
                self.groups[g["id"]] = g

    @classmethod
    def load(cls, path: str | Path) -> "Palette":
        p = Path(path)
        return cls(json.loads(p.read_text(encoding="utf-8")), p)

    # ─── проверка ─────────────────────────────────────────────────────────────
    def validate(self) -> list[str]:
        """Список проблем. Пустой список — палитру можно применять."""
        problems: list[str] = list(self.groups_errors)
        if not self.palette_id or not UUID_RE.match(str(self.palette_id)):
            problems.append(f"paletteId={self.palette_id!r}: нужен id палитры проекта — "
                            f"он ключ словаря со ссылкой на цвет")
        for role in PALETTE_ROLES:
            spec = self.roles.get(role, {})
            if not spec:
                problems.append(f"роль {role}: не описана")
                continue
            if not spec.get("hex"):
                problems.append(f"роль {role}: нет оттенка — макету нечего красить")
            checks = [("groupId", spec.get("groupId"))]
            if role != ROLE_INCISION:            # разрез берёт цвета из группы целиком
                checks.append(("colorId", spec.get("colorId")))
            for label, value in checks:
                if value == PLACEHOLDER or not value:
                    problems.append(f"роль {role}: {label} не заполнен")
                elif not UUID_RE.match(str(value)):
                    problems.append(f"роль {role}: {label}={value!r} не похож на uuid")
            gid = spec.get("groupId")
            if gid and gid != PLACEHOLDER:
                if gid not in self.groups:
                    problems.append(f"роль {role}: группы {gid} нет среди загруженных групп")
                elif spec.get("colorId") and spec["colorId"] != PLACEHOLDER:
                    ids = {c.get("id") for c in self.groups[gid].get("colors", [])}
                    if ids and spec["colorId"] not in ids:
                        problems.append(f"роль {role}: цвета {spec['colorId']} нет в группе {gid}")
        for role in TEXT_ROLES:
            spec = self.roles.get(role, {})
            if not spec:
                continue
            if not spec.get("hex"):
                problems.append(f"роль {role}: нет оттенка для макета")
            if not isinstance(spec.get("level"), int):
                problems.append(f"роль {role}: нужен level 1–5 — тексты красятся уровнями темы")
        for role in self.roles:
            if role not in ROLES:
                problems.append(f"роль {role}: неизвестная роль")
        return problems

    # ─── ссылки для файла страницы ────────────────────────────────────────────
    def color_ref(self, role: str) -> dict:
        """Конкретный цвет из группы: серии, фоны, подписи значений."""
        spec = self.roles[role]
        return {self.palette_id: {"type": "color", "groupId": spec["groupId"],
                                  "colorId": spec["colorId"]}}

    def palette_ref(self, role: str) -> dict:
        """Группа целиком: категории разреза, фон — цвета берутся из группы по порядку."""
        spec = self.roles[role]
        return {self.palette_id: {"type": "palette", "groupId": spec["groupId"]}}

    def color_values(self, role: str, values: list[str]) -> list[dict]:
        """Сегменты по значениям: `[{value, colorId, groupId}]`, цвета группы по кругу."""
        spec = self.roles[role]
        colors = self.groups.get(spec["groupId"], {}).get("colors", [])
        out = []
        for i, value in enumerate(values):
            if colors:
                out.append({"value": value, "colorId": colors[i % len(colors)]["id"],
                            "groupId": spec["groupId"]})
            else:
                out.append({"value": value, "colorId": spec.get("colorId"),
                            "groupId": spec["groupId"]})
        return out

    def color_scope(self, role: str) -> dict:
        """Уровень темы для текста: `{type: "color", level: N}` (ключ ставит сборщик)."""
        return {"type": "color", "level": self.level(role)}

    def level(self, role: str) -> int:
        return int(self.roles.get(role, {}).get("level", DEFAULT_LEVELS[role]))

    def hex(self, role: str) -> str:
        """Оттенок для HTML-макета. В страницу hex не попадает."""
        return self.roles.get(role, {}).get("hex") or "#000000"

    def own_ids(self) -> set[str]:
        """id, легально живущие в файле страницы: палитра, её группы и цвета."""
        ids = {str(self.palette_id)} if self.palette_id and UUID_RE.match(str(self.palette_id)) else set()
        ids |= set(self.groups)
        for g in self.groups.values():
            ids |= {c.get("id") for c in g.get("colors", []) if c.get("id")}
        for spec in self.roles.values():
            for k in ("groupId", "colorId"):
                v = spec.get(k)
                if v and v != PLACEHOLDER and UUID_RE.match(str(v)):
                    ids.add(str(v))
        return ids

    def describe(self) -> str:
        return (f"{self.name} | paletteId={self.palette_id} | групп {len(self.groups)} | "
                f"цветов {sum(len(g.get('colors', [])) for g in self.groups.values())}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("укажите файл ролей: python palette.py palettes/gazprom.json")
        return 2
    pal = Palette.load(sys.argv[1])
    print("палитра:", pal.describe())
    problems = pal.validate()
    for p in problems:
        print("  ✗", p)
    if problems:
        print(f"\nзаполнить осталось: {len(problems)} — сборку не начинать")
        return 1
    print("  палитра заполнена: id групп и цветов на месте")
    print("  цвет серии:    ", json.dumps(pal.color_ref(ROLE_SERIES[0]), ensure_ascii=False))
    print("  фон виджета:   ", json.dumps(pal.color_ref(ROLE_WIDGET_BG), ensure_ascii=False))
    print("  разрез (группа):", json.dumps(pal.palette_ref(ROLE_INCISION), ensure_ascii=False))
    print("  разрез (значения):", json.dumps(pal.color_values(ROLE_INCISION, ["К1", "К2"]),
                                            ensure_ascii=False))
    print("  текст (уровень):", json.dumps({ROLE_HEADER: pal.color_scope(ROLE_HEADER)},
                                           ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
