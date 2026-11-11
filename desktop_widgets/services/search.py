"""Search for the quick launcher: what can be found, how it ranks, and usage.

Items are plain dicts: {kind, name, sub, path, app?, layout?, command?}.
kind is one of: app (in a folder), file (in a Files widget), installed
(any installed app), layout, command.
"""
from __future__ import annotations

import os
import re
import time

MAX_RESULTS = 8
_KIND_BONUS = {"app": 8, "layout": 6, "command": 4, "file": 3, "installed": 0}


def record_launch(data: dict, path: str) -> None:
    """Count launches so frequent apps rank higher and show as Recent."""
    usage = data.setdefault("usage", {})
    entry = usage.setdefault(path, {"count": 0, "last": 0})
    entry["count"] += 1
    entry["last"] = time.time()
    if len(usage) > 300:     # forget the least recently used
        for old in sorted(usage, key=lambda p: usage[p]["last"])[:len(usage) - 300]:
            del usage[old]


def collect(data: dict, installed: list | None = None) -> list[dict]:
    """Everything the launcher can open, folders first, without duplicates."""
    items, seen = [], set()
    def key(path, name):
        return os.path.normcase(path or ""), (name or "").casefold()
    stack_of = {gid: st for st in data.get("stacks", []) for gid in st.get("groups", [])}
    for g in data.get("groups", []):
        st = stack_of.get(g["id"])
        where = f"{st['name']} › {g['name']}" if st else g["name"]
        for app in g.get("apps", []):
            k = key(app.get("path"), app.get("name"))
            if k[0] in seen:
                continue
            seen.update(k)
            items.append({"kind": "app", "name": app.get("name", ""), "sub": where,
                          "path": app["path"], "app": app})
    for blk in data.get("docs_widgets", []):
        for f in blk.get("files", []):
            if os.path.normcase(f.get("path", "")) in seen:
                continue
            seen.add(os.path.normcase(f.get("path", "")))
            items.append({"kind": "file", "name": f.get("name", ""), "sub": f"File · {blk.get('name', 'Files')}",
                          "path": f["path"], "app": f})
    for entry in installed or []:
        p, n = key(entry.get("path"), entry.get("name"))
        if p in seen or n in seen:
            continue
        seen.update((p, n))
        items.append({"kind": "installed", "name": entry.get("name", ""), "sub": "Installed app",
                      "path": entry["path"], "app": entry})
    for layout in data.get("layouts", []):
        items.append({"kind": "layout", "name": layout["name"], "sub": "Switch to this layout",
                      "path": "", "layout": layout["name"]})
    for name, sub, command in (("Settings", "Open Settings", "settings"),
                               ("Add a widget", "Folders, stacks, notes, stats and more", "add_widget"),
                               ("Organize folders", "Sort apps into fitting folders and clean up", "organize")):
        items.append({"kind": "command", "name": name, "sub": sub, "path": "", "command": command})
    return items


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"[\s\-_.:/()&+]+", text.casefold()) if w]


def match_score(name: str, query: str) -> int | None:
    """How well `query` matches `name`; None when it does not match at all."""
    n, q = name.casefold(), query.casefold().strip()
    if not q:
        return 0
    if n == q:
        return 100
    if n.startswith(q):
        return 80
    words = _words(name)
    if any(w.startswith(q) for w in words):
        return 65
    initials = "".join(w[0] for w in words)
    if len(q) >= 2 and initials.startswith(q):
        return 55                                   # "rdr" → Red Dead Redemption
    if q in n:
        return 40
    it = iter(n.replace(" ", ""))
    if len(q) >= 3 and all(c in it for c in q.replace(" ", "")):
        return 15                                   # letters in order: "frza" → Forza
    return None


def search(items: list[dict], query: str, usage: dict | None = None) -> list[dict]:
    usage = usage or {}
    if not query.strip():
        # Nothing typed: the most recently opened things.
        recent = [i for i in items if i["path"] in usage]
        recent.sort(key=lambda i: usage[i["path"]]["last"], reverse=True)
        return recent[:MAX_RESULTS]
    ranked = []
    for order, item in enumerate(items):
        base = match_score(item["name"], query)
        if base is None:
            continue
        used = usage.get(item["path"], {}).get("count", 0) if item["path"] else 0
        score = base + _KIND_BONUS[item["kind"]] + min(15, used * 2)
        ranked.append((-score, order, base, item))
    # Loose "letters in order" matches only help when nothing matches properly.
    if any(base >= 40 for _, _, base, _ in ranked):
        ranked = [r for r in ranked if r[2] >= 40]
    ranked.sort(key=lambda r: (r[0], r[1]))
    return [item for _, _, _, item in ranked[:MAX_RESULTS]]
