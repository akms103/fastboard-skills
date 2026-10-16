#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Клиент MCP Fastboard: ходит по PAT без пользовательской сессии.

Эндпоинт: POST {BASE_URL}/api/v3/mcp (streamable HTTP, ответы в SSE).
Авторизация: Authorization: Bearer fbpat_…  — JWT не нужен.

Токен — из env FB_PAT, адрес — из FB_MCP (по умолчанию dev).
Файлы в tools/call кладутся конвертом {contentType, encoding:"base64", data}.

Использование:
    python fb_mcp.py tools
    python fb_mcp.py schema import_project_pages
    python fb_mcp.py call get_project_palettes --project <id>
    python fb_mcp.py call import_project_pages --project <id> --args '{"newPages":"true","importModels":"false"}' --file page.json --content-type application/json
    python fb_mcp.py call save_project_palettes --project <id> --args-file pal-save.json
    python fb_mcp.py call <name> --args-file args.json --save out.json
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

MCP = os.environ.get("FB_MCP", "https://dev.fastboard.online/back/api/v3/mcp")
PAT = os.environ.get("FB_PAT", "")


def rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    if not PAT:
        raise SystemExit("не задан FB_PAT: положите личный токен в переменную окружения")
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    req = urllib.request.Request(
        MCP, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Authorization": f"Bearer {PAT}"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = resp.read().decode("utf-8", "replace")
    for line in body.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return json.loads(body)


def tools() -> list[dict]:
    return rpc("tools/list")["result"]["tools"]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]

    if cmd == "tools":
        for t in tools():
            print(f"  {t['name']:34} {(t.get('description') or '')[:78]}")
        return 0

    if cmd == "schema":
        want = sys.argv[2]
        for t in tools():
            if t["name"] == want:
                print(json.dumps(t.get("inputSchema"), ensure_ascii=False, indent=1))
                return 0
        print(f"инструмента {want} нет", file=sys.stderr)
        return 1

    if cmd == "call":
        name = sys.argv[2]
        rest = sys.argv[3:]
        args: dict = {}
        if "--args" in rest:
            args.update(json.loads(rest[rest.index("--args") + 1]))
        if "--args-file" in rest:
            with open(rest[rest.index("--args-file") + 1], encoding="utf-8") as fh:
                args.update(json.load(fh))
        if "--project" in rest:
            args["projectId"] = rest[rest.index("--project") + 1]
        if "--file" in rest:
            path = Path(rest[rest.index("--file") + 1])
            ct = rest[rest.index("--content-type") + 1] if "--content-type" in rest else \
                "application/zip" if path.suffix == ".zip" else "application/json"
            args["file"] = {"contentType": ct, "encoding": "base64",
                            "data": base64.b64encode(path.read_bytes()).decode("ascii")}
        out = rpc("tools/call", {"name": name, "arguments": args})
        text = json.dumps(out, ensure_ascii=False, indent=1)
        if "--save" in rest:
            p = rest[rest.index("--save") + 1]
            Path(p).write_text(text, encoding="utf-8")
            print(f"ответ сохранён в {p} ({len(text)} символов)")
        print(text[:4000])
        return 1 if out.get("result", {}).get("isError") else 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())