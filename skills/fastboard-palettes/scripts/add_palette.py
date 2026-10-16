#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создаёт группу цветов в colors.json (реестр палитр Fastboard).

Формы записи цвета — можно смешивать в одной команде:

    "#0079c2:Газпром синий:100"      hex-first: h/l/s считаются из hex
    210 50 70 "#0055a4" "синий"      позиционная: h/l/s заданы вручную

`opacity` опускается — будет 100. Если в позиционной форме задан и `opacity`, он допустим
только у последнего цвета: иначе число неотличимо от оттенка следующего цвета, и скрипт
останавливается с подсказкой, а не разбирает аргументы наугад.

Если заданы и h/l/s, и hex, скрипт сверяет их и предупреждает о расхождении больше 2° —
частая ошибка при копировании значений из пикера.

Использование:
    python add_palette.py colors.json "Газпром" "#0079c2:Газпром синий:100" "#4fa3db:светлый"
    python add_palette.py colors.json "Заказчик" 203 38 100 "#0079c2" "основной"
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

HEX_RE = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


def _is_num(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def hex_to_hsl(hexv: str) -> tuple[float, float, float]:
    """hex → (h 0–360, l 0–100, s 0–100). Округление до одного знака."""
    import colorsys
    h = hexv.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return round(hh * 360, 1), round(ll * 100, 1), round(ss * 100, 1)


def _check_hex(hexv: str) -> str:
    import re
    if not re.match(HEX_RE, hexv):
        raise SystemExit(f"цвет {hexv!r} не похож на hex вида #rrggbb")
    return hexv.lower()


def _check_opacity(value: str) -> int:
    try:
        opacity = int(float(value))
    except ValueError:
        raise SystemExit(f"opacity {value!r} — не число")
    if not 0 <= opacity <= 100:
        raise SystemExit(f"opacity {value!r} вне диапазона 0–100")
    return opacity


def _color(h: float, l: float, s: float, hexv: str, name: str, opacity: int) -> dict:
    """Собирает цвет и сверяет h/l/s с hex: расхождение больше 2° — предупреждение."""
    ch, cl, cs = hex_to_hsl(hexv)
    if abs(h - ch) % 360 > 2 or abs(l - cl) > 2 or abs(s - cs) > 2:
        print(f"  ! {name or hexv}: задано h/l/s {h}/{l}/{s}, из hex {hexv} выходит "
              f"{ch}/{cl}/{cs} — проверьте, что цвет скопирован верно", file=sys.stderr)
    return {"h": h, "l": l, "s": s, "id": str(uuid.uuid4()), "hex": hexv,
            "name": name, "opacity": opacity}


def parse_colors(tokens: list[str]) -> list[dict]:
    """Разбор аргументов командной строки в список цветов."""
    colors: list[dict] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]

        # ── форма 1: "#hex[:имя[:opacity]]" ──
        if token.startswith("#"):
            parts = token.split(":")
            hexv = _check_hex(parts[0])
            name = parts[1].strip() if len(parts) > 1 else ""
            opacity = 100
            if len(parts) > 2:
                opacity = _check_opacity(parts[2])
            elif len(parts) > 3:
                raise SystemExit(f"{token!r}: слишком много частей, ждём '#hex:имя:opacity'")
            h, l, s = hex_to_hsl(hexv)
            colors.append({"h": h, "l": l, "s": s, "id": str(uuid.uuid4()),
                           "hex": hexv, "name": name, "opacity": opacity})
            i += 1
            continue

        # ── форма 2: H L S "#hex" "имя" ──
        if _is_num(token):
            if i + 4 >= len(tokens) or not tokens[i + 3].startswith("#"):
                raise SystemExit(
                    f"не понимаю цвет, начиная с {token!r}: в позиционной форме нужно "
                    f"H L S \"#hex\" \"имя\" (получено: {tokens[i:i + 5]})")
            h, l, s = float(tokens[i]), float(tokens[i + 1]), float(tokens[i + 2])
            hexv, name = _check_hex(tokens[i + 3]), tokens[i + 4]
            i += 5
            if i < len(tokens) and _is_num(tokens[i]):
                raise SystemExit(
                    f"после цвета «{name}» стоит число {tokens[i]!r}: это или opacity этого цвета, "
                    f"или оттенок следующего — неоднозначно. Напишите opacity внутри hex-формы: "
                    f"\"{hexv}:{name}:{tokens[i]}\"")
            colors.append(_color(h, l, s, hexv, name, 100))
            continue

        raise SystemExit(f"не понимаю аргумент {token!r}: ждём '#hex:имя:opacity' "
                         f"или H L S \"#hex\" \"имя\"")

    if not colors:
        raise SystemExit("не передано ни одного цвета")
    return colors


def add_group(path: str, name: str, colors: list[dict]) -> dict:
    """Дописывает группу в colors.json (файл создаётся, если его нет)."""
    p = Path(path)
    groups = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    if not isinstance(groups, list):
        raise SystemExit(f"{path}: ожидался массив групп на верхнем уровне")
    group = {"id": str(uuid.uuid4()), "name": name, "colors": colors}
    groups.append(group)
    p.write_text(json.dumps(groups, ensure_ascii=False), encoding="utf-8")
    return group


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    path, name, tokens = sys.argv[1], sys.argv[2], sys.argv[3:]
    group = add_group(path, name, parse_colors(tokens))
    print(f"группа «{name}» добавлена в {path}")
    print(f"  groupId = {group['id']}")
    print(f"  цветов: {len(group['colors'])}")
    for c in group["colors"]:
        print(f"    h{c['h']:<6} l{c['l']:<6} s{c['s']:<6} {c['hex']:<9} "
              f"opacity {c['opacity']:<4} {c['name']}")
        print(f"      colorId = {c['id']}")
    print("  эти id подставляются в файл ролей: python palette.py <файл ролей>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
