"""fb_widget_names.py — именование объектов страницы Fastboard.

Режимы:
  propose <pages.json> [-o map.csv] [--blocks blocks.json] [--max-len 30]
      Черновая карта: блоки (по координатам + переменным видимости), тип, SQL-колонки фильтров.
      Имя = «<Имя блока> · <тип> <назначение>».  Назначение и имя блока доводятся вручную.
  apply <pages.json> map.csv -o out.json [--force]
      Применить колонку proposed_name. Меняет ТОЛЬКО поля имени.

blocks.json — правка блока в одном месте, до пересборки карты:
  {"B1": "Шапка", "B2": "Генплан", ...}   (id блоков печатает режим propose)

Карта: CSV: kind,id,old_name,type,block_id,block_name,proposed_name,basis,size,pos,flags
Формат экспорта: одна строка, json.dumps(..., ensure_ascii=False, separators=(',',':')),
без завершающего перевода строки — скрипт воспроизводит и проверяет его байт-в-байт.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys

DUMP = dict(ensure_ascii=False, separators=(",", ":"))
MAX_LEN = 30

ROLE_BY_TYPE = {"svg": "Схема", "gantt": "Ганта", "heatmap": "Теплокарта",
                "pie": "Круговая", "map": "Карта", "indicator": "KPI"}
SERVICE_NAMES = {"фото 0", "фото 1", "показатель", "показатель 0", "value", "значение"}
PLACEHOLDER_TEXTS = {"заголовок", "подзаголовок", "подсказка", "текст", "", "х"}
WEAK_LABELS = {"блок", "графики", "value", "меню", "текст"}
BLOCK_TRIM = [("Выполнение ГПР по этажам и БС", "ГПР по БС"),
              ("Прогресс по Объекту", "Прогресс"),
              ("Детализация прогресса", "Прогресс"),
              ("Реестр договоров", "Реестр"),
              ("План-график работ", "План-график"),
              ("Прогресс по работам", "Прогресс работ")]


def load_page(path):
    raw = open(path, "rb").read()
    d = json.loads(raw.decode("utf-8"))
    pages = d.get("pagesSettings") or []
    if len(pages) != 1:
        print(f"[!] страниц в файле: {len(pages)} — беру первую")
    return raw, d, pages[0]


def is_byte_exact(raw, d):
    return json.dumps(d, **DUMP).encode("utf-8") == raw


def norm(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def rawbox(o):
    pc = o.get("positionConfig") or {}
    x, y = pc.get("x") or 0, pc.get("y") or 0
    return x, y, x + (pc.get("width") or 0), y + (pc.get("height") or 0)


def static_texts(w):
    out = []
    for v in (w.get("dataSettings", {}).get("variables") or []):
        t = (((v.get("settings") or {}).get("textPropertiesSettings") or {}).get("text") or {})
        if norm(t.get("text")):
            out.append(norm(t.get("text")))
    return out


def template_of(w):
    return norm(((w.get("viewSettings") or {}).get("text") or {}).get("text") or "")


def header_of(w):
    h = (w.get("viewSettings") or {}).get("header") or {}
    return norm(h.get("text")) if h.get("isShow") else ""


def has_bg_image(w):
    b = w.get("backgroundImagesSettings") or {}
    by = (((b.get("backgroundImages") or {}).get("imagesSettings") or {}).get("backgroundImagesBy") or {})
    return bool((by.get("byValue") or {}).get("images") or (by.get("byCondition") or {}).get("images"))


def good_names(items):
    return [norm(i.get("name")) for i in (items or [])
            if norm(i.get("name")) and norm(i.get("name")).lower() not in SERVICE_NAMES]


def literal_head(s: str) -> str:
    """Литеральная часть до первого плейсхолдера: «Sобщ: {{total}} …» -> «Sобщ»."""
    head = s.split("{{")[0]
    return norm(head.strip(" ,.:·-—"))


def is_weak(label: str) -> bool:
    lab = norm(label)
    if len(lab) < 3 or "{{" in lab or "%" in lab:
        return True
    if lab.lower() in WEAK_LABELS or lab.isascii() and len(lab) < 5:
        return True
    return bool(re.fullmatch(r"[\W\d_]+", lab))


def role_of(w):
    t = w.get("visualisationType")
    ds = w.get("dataSettings", {})
    h = (w.get("positionConfig") or {}).get("height") or 0
    if t == "text":
        if has_bg_image(w):
            return "иконка-переход" if ((w.get("events", {}).get("goTo") or {}).get("isActive")) else "иконка"
        if [s for s in static_texts(w) if s.lower() not in PLACEHOLDER_TEXTS]:
            return "меню" if (w.get("positionConfig") or {}).get("y", 0) < 60 else "надпись"
        return "значение" if (ds.get("indicators") or []) else "плашка"
    if t == "table":
        return "таблица" if (ds.get("indicators") or []) else "кнопка"
    if t == "lineAndBar":
        if h and h <= 60:
            return "спарклайн"
        return "барчарт" if ds.get("rotateTo90") else "график"
    return ROLE_BY_TYPE.get(t, t or "?").lower()


def raw_template_of(w):
    return str(((w.get("viewSettings") or {}).get("text") or {}).get("text") or "")


def subject_of(w):
    """Порядок источников: заголовок → шаблон без плейсхолдера → значение переменной → данные.

    Порядок критичен: у меню и карточек значение переменной — общая заглушка
    («НАРОДНЫЕ КВАРТАЛЫ» у десятка виджетов), а настоящая подпись в шаблоне.
    """
    ds = w.get("dataSettings", {})
    pc = w.get("positionConfig") or {}
    if header_of(w):
        return header_of(w), "видимый заголовок"
    first = norm(raw_template_of(w).split("\n")[0])
    if first and "{{" not in first and not is_weak(first):
        return first, "шаблон виджета (без плейсхолдера)"
    strong = [s for s in static_texts(w) if s.lower() not in PLACEHOLDER_TEXTS]
    if strong:
        return strong[0], "значение переменной (заглушку проверить вручную)"
    tpl = literal_head(template_of(w))
    if tpl and not is_weak(tpl):
        return tpl, "литеральная часть шаблона"
    inds, incs = good_names(ds.get("indicators")), good_names(ds.get("incisions"))
    if inds or incs:
        parts = ["/".join(inds[:3])] if inds else []
        if incs:
            parts.append("по " + "/".join(incs[:2]))
        return " ".join(parts), "данные: показатели+разрезы"
    hint = norm((w.get("viewSettings") or {}).get("hint", {}).get("text")) if isinstance((w.get("viewSettings") or {}).get("hint"), dict) else ""
    if hint and hint.lower() not in PLACEHOLDER_TEXTS:
        return hint, "подсказка (hint)"
    if has_bg_image(w):
        return "", "фоновая SVG без данных"
    return f"x{round(pc.get('x') or 0)} y{round(pc.get('y') or 0)}", "только позиция"


def mode_label(w, page_vars):
    ev = (w.get("events") or {}).get("variablesSettings") or {}
    cv = ((ev.get("control") or {}).get("view") or {})
    if cv.get("isActive") and cv.get("variableName"):
        return norm(cv.get("variableName")), "переменная видимости"
    for v in ev.get("variables") or []:
        nm = page_vars.get(v.get("variableId"))
        if nm:
            return norm(nm), "переменная видимости"
    return "", ""


def container_label(w):
    """Имя блока по крупному виджету-якорю: заголовок → литерал шаблона → тип."""
    for src, tgt in BLOCK_TRIM:
        if src in header_of(w) or src in template_of(w):
            return tgt
    if header_of(w) and not is_weak(header_of(w)):
        return norm(header_of(w)).split(",")[0][:16]
    lit = literal_head(template_of(w))
    if lit and not is_weak(lit) and len(lit.split()) <= 3:
        return lit[:16]
    return ROLE_BY_TYPE.get(w.get("visualisationType"), "Таблица")


def propose(pages_path, out_path, blocks_map, max_len):
    raw, d, pg = load_page(pages_path)
    widgets = pg.get("visualizationsV3") or []
    groups = pg.get("groupsVisualizationsV3") or []
    filters = pg.get("filtersV3") or []
    gmap = {g["id"]: g for g in groups}
    page_vars = {v["id"]: v.get("name") for v in (pg.get("page", {}).get("variables") or [])}

    boxes, placeable, warn = {}, {}, {}
    for i, w in enumerate(widgets):
        x0, y0, x1, y1 = rawbox(w)
        gid = ((w.get("viewSettings") or {}).get("group") or {}).get("groupId")
        if gid and gid in gmap:
            gx, gy, _, _ = rawbox(gmap[gid])
            boxes[i], placeable[i] = (gx + x0, gy + y0, gx + x1, gy + y1), True
        else:
            boxes[i] = (x0, y0, x1, y1)
            placeable[i] = not gid
            if gid:
                warn[i] = "группа не в выгрузке — координаты неизвестны"

    anchors = [i for i in range(len(widgets)) if placeable[i] and
               ((boxes[i][2] - boxes[i][0]) >= 600 or (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1]) >= 150_000)]
    weak_anchor = {i: is_weak(container_label(widgets[i])) for i in anchors}

    # кластеры: 1) членство в блоке по переменной, 2) ближайший якорь с сильной подписью
    raw_block, block_basis = {}, {}
    for i, w in enumerate(widgets):
        ml, why = mode_label(w, page_vars)
        if ml and not ml.lower().startswith("триггер"):
            raw_block[i], block_basis[i] = ml, why
        elif ml:
            st = static_texts(w)
            raw_block[i] = ("Секция " + re.sub(r"\D", "", st[0]) if st and "екци" in st[0] else "Секции")
            block_basis[i] = "триггерная секция (шаблон карточки)"
        elif not placeable[i]:
            raw_block[i], block_basis[i] = "Секции", "группа не в выгрузке"
        elif i in anchors and not weak_anchor[i]:
            raw_block[i], block_basis[i] = container_label(w), "подпись якоря"
        else:
            bx = boxes[i]
            cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
            strong = [j for j in anchors if not weak_anchor[j]] or anchors
            near = min(strong, key=lambda j: abs((boxes[j][0] + boxes[j][2]) / 2 - cx) + abs((boxes[j][1] + boxes[j][3]) / 2 - cy)) if strong else None
            raw_block[i] = container_label(widgets[near]) if near is not None else "Блок"
            block_basis[i] = "ближайший якорь"

    # нумеруем блоки порядком по y их верхнего края (id стабильны внутри прогона)
    order, bid = {}, {}
    for i in sorted(raw_block, key=lambda i: (min(boxes[j][1] for j in raw_block if raw_block[j] == raw_block[i]), raw_block[i])):
        nm = raw_block[i]
        if nm not in bid:
            bid[nm] = f"B{len(bid) + 1}"
        order[i] = bid[nm]
    names_from_file = {}
    if blocks_map:
        names_from_file = json.load(open(blocks_map, encoding="utf-8"))
    block_name = {nm_id: names_from_file.get(nm_id, nm) for nm, nm_id in bid.items()}

    rows = []
    for i, w in enumerate(widgets):
        role = role_of(w)
        subj, basis = subject_of(w)
        subj = subj.split("\n")[0][:24].strip(" ,.:·-—")
        nm = f"{block_name[order[i]]} · {role}" + (f" {subj}" if subj else "")
        flags = []
        if not w.get("isVisible", True):
            flags.append("скрыт")
        if i in warn:
            flags.append(warn[i])
        if not subj:
            flags.append("нет данных и подписи — дописать вручную")
        rows.append(dict(kind="widget", id=w["id"], old_name=(w.get("viewSettings") or {}).get("name") or "",
                         type=w.get("visualisationType"), block_id=order[i], block_name=block_name[order[i]],
                         proposed_name=nm[:max_len], basis=basis,
                         size=f"{round(boxes[i][2]-boxes[i][0])}x{round(boxes[i][3]-boxes[i][1])}",
                         pos=f"{round(boxes[i][0])},{round(boxes[i][1])}", flags="; ".join(flags)))
    for g in groups:
        vs = g.get("viewSettings") or {}
        rows.append(dict(kind="group", id=g["id"], old_name=vs.get("name") or "", type="group",
                         block_id="B0", block_name="Группа",
                         proposed_name=f"Группа · {norm(vs.get('name'))[:18]}", basis="имя группы",
                         size="", pos="", flags=f"членов: {len(g.get('widgetIds') or [])}"))
    col_used = {}
    for f in filters:
        col = ((f.get("nameSettings") or {}).get("fieldName") or "").split(".")[-1] or "поле"
        col_used[col] = col_used.get(col, 0) + 1
    for f in filters:
        col = ((f.get("nameSettings") or {}).get("fieldName") or "").split(".")[-1] or "поле"
        zone = ""
        if col_used[col] > 1 and anchors:
            pc = f.get("positionConfig") or {}
            fx, fy = pc.get("x") or 0, pc.get("y") or 0
            near = min(anchors, key=lambda j: abs(boxes[j][0] - fx) + abs(boxes[j][1] - fy))
            zone = block_name[bid.get(raw_block[near], "B1")]
        nm = f"Фильтр · {col}" + (f" ({zone})" if zone else "")
        rows.append(dict(kind="filter", id=f["id"], old_name=f.get("name") or "",
                         type=f"filter:{f.get('type')}", block_id="B99", block_name="Фильтры",
                         proposed_name=nm[:max_len],
                         basis=f"SQL-колонка {(f.get('nameSettings') or {}).get('fieldName')}",
                         size="", pos="", flags="колонка повторяется — зона в скобках" if col_used[col] > 1 else ""))

    all_names = [r["proposed_name"] for r in rows]
    dup = sorted({n for n in all_names if all_names.count(n) > 1})
    over = sorted({(len(n), n) for n in all_names if len(n) > max_len}, reverse=True)
    print(f"объектов: {len(rows)} (виджетов {len(widgets)}, фильтров {len(filters)}, групп {len(groups)})")
    print(f"формат исходника байт-в-байт: {is_byte_exact(raw, d)}")
    print(f"длиннее {max_len}: {over or 'нет'}")
    print(f"дубликаты в черновике (доработать вручную): {dup or 'нет'}")
    print("\nблоки (переименовать в колонке block_name или через --blocks):")
    for nm_id, nm in sorted(block_name.items(), key=lambda kv: int(kv[0][1:])):
        mem = [r for r in rows if r["block_id"] == nm_id]
        ys = [r["pos"].split(",")[1] for r in mem if r["pos"]]
        rng = f"y {min(ys, key=lambda s: float(s))}–{max(ys, key=lambda s: float(s))}" if ys else ""
        print(f"   {nm_id}: {nm:<22} объектов {len(mem):>2}   {rng}")
    cols = ["kind", "id", "old_name", "type", "block_id", "block_name", "proposed_name", "basis", "size", "pos", "flags"]
    with open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)
    print(f"\nкарта: {out_path}")
    for r in rows:
        tail = f"  <{r['flags']}>" if r["flags"] else ""
        print(f"  [{r['kind']:>6}] {r['proposed_name'][:34]:<34} {len(r['proposed_name']):>2}  <- {r['old_name'][:30]}{tail}")
    return 0


def name_paths(pg):
    paths = {}
    for w in pg.get("visualizationsV3") or []:
        paths.setdefault(w["id"], []).append("viewSettings.name")
    for g in pg.get("groupsVisualizationsV3") or []:
        paths.setdefault(g["id"], []).extend(["name", "viewSettings.name"])
    for f in pg.get("filtersV3") or []:
        paths.setdefault(f["id"], []).append("name")
    return paths


def get_obj(pg, kind, oid):
    coll = {"widget": pg.get("visualizationsV3") or [],
            "group": pg.get("groupsVisualizationsV3") or [],
            "filter": pg.get("filtersV3") or []}.get(kind, [])
    return next((o for o in coll if o["id"] == oid), None)


def set_name(obj, path, value):
    head, _, tail = path.partition(".")
    if tail:
        obj.setdefault(head, {})[tail] = value
    else:
        obj[head] = value


def read_map(path):
    if path.lower().endswith(".json"):
        return [dict(id=k, proposed_name=v, kind="", old_name="") for k, v in json.load(open(path, encoding="utf-8")).items()]
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def apply_map(src, map_path, out, force=False):
    raw, d, pg = load_page(src)
    exact = is_byte_exact(raw, d)
    if not exact and not force:
        print("[!] дамп не воспроизводит оригинал байт-в-байт — формат экспортёра не угадан. Правку не делаю.")
        return 2
    paths, rows = name_paths(pg), read_map(map_path)
    changed, missed, bad, seen = [], [], [], set()
    for r in rows:
        oid, new = norm(r.get("id")), norm(r.get("proposed_name"))
        if not oid or not new or oid in seen:
            bad.append(r)
            continue
        seen.add(oid)
        kind = norm(r.get("kind"))
        obj = None
        for k in ([kind] if kind else ["widget", "group", "filter"]):
            obj = get_obj(pg, k, oid)
            if obj is not None:
                break
        if obj is None:
            missed.append(oid)
            continue
        for p in paths.get(oid, []):
            cur, ok = obj, True
            for part in p.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    ok = False
                    break
            before = cur if ok else None
            if before == new:
                continue
            set_name(obj, p, new)
            changed.append((p.split(".")[0], oid, before, new))
    payload = json.dumps(d, **DUMP).encode("utf-8")
    open(out, "wb").write(payload)
    other, d2 = [], json.loads(payload.decode("utf-8"))

    def walk(x, y, path=""):
        if type(x) is not type(y):
            other.append(path); return
        if isinstance(x, dict):
            for k in set(x) | set(y):
                if k not in x or k not in y:
                    other.append(f"{path}/{k}")
                else:
                    walk(x[k], y[k], f"{path}/{k}")
        elif isinstance(x, list):
            if len(x) != len(y):
                other.append(path + "/len"); return
            for i, (x2, y2) in enumerate(zip(x, y)):
                walk(x2, y2, f"{path}[{i}]")
        elif x != y:
            other.append(path)

    walk(pg, d2["pagesSettings"][0])
    print(f"объектов в карте: {len(rows)}; применено изменений: {len(changed)}; "
          f"id не найдено: {len(missed)}; строк без id/имени: {len(bad)}")
    print(f"формат исходника байт-в-байт: {'да' if exact else 'НЕТ (--force)'}")
    print(f"изменено что-то кроме имён: {'да: ' + str(other[:10]) if other else 'нет'}")
    print(f"записано: {out} ({len(payload)} байт)")
    for head, oid, before, after in changed[:8]:
        print(f"   {head}: {before!r} -> {after!r}")
    if len(changed) > 8:
        print(f"   ... и ещё {len(changed) - 8}")
    return 0


def main(argv=None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Имена объектов страницы Fastboard")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("propose")
    p1.add_argument("pages")
    p1.add_argument("-o", "--out", default=None)
    p1.add_argument("--blocks", default=None, help='JSON {"B1": "Шапка", ...} — правка имён блоков')
    p1.add_argument("--max-len", type=int, default=MAX_LEN)
    p2 = sub.add_parser("apply")
    p2.add_argument("pages")
    p2.add_argument("map")
    p2.add_argument("-o", "--out", required=True)
    p2.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "apply":
        return apply_map(a.pages, a.map, a.out, a.force)
    out = a.out or os.path.splitext(a.pages)[0] + "_names.csv"
    return propose(a.pages, out, a.blocks, a.max_len)


if __name__ == "__main__":
    raise SystemExit(main())
