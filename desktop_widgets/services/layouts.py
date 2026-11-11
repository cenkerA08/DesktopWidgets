"""Saved desktop layouts: where every widget sits, which optional widgets are
on, what is collapsed, each stack's open tab, and the theme.

A layout only stores positions and switches; folders, apps and notes are
never copied, so switching cannot lose anything. Folders created after a
layout was saved simply stay where they are when it is applied.
"""
from __future__ import annotations

import copy
import time

SINGLES = ("statsplus", "notes", "media")


def snapshot(data: dict, name: str) -> dict:
    def place(blk, *extra):
        out = {"x": blk.get("x", 60), "y": blk.get("y", 60), "collapsed": bool(blk.get("collapsed"))}
        for key in extra:
            if key in blk:
                out[key] = blk[key]
        return out
    return {
        "name": name,
        "saved": time.time(),
        "theme_preset": data.get("theme_preset"),
        "theme": copy.deepcopy(data.get("theme")),
        "groups": {str(g["id"]): place(g, "cols") for g in data.get("groups", [])},
        "stacks": {str(s["id"]): place(s, "active", "cols") for s in data.get("stacks", [])},
        "docs": {str(b["id"]): place(b, "cols") for b in data.get("docs_widgets", [])},
        "single": {key: {"enabled": bool(data.get(key, {}).get("enabled")),
                         **place(data.get(key, {}), "w", "h")} for key in SINGLES},
    }


def apply_to_data(data: dict, layout: dict) -> None:
    """Copy a layout's positions and switches into the live data."""
    for blocks, key in ((data.get("groups", []), "groups"), (data.get("stacks", []), "stacks"),
                        (data.get("docs_widgets", []), "docs")):
        saved = layout.get(key, {})
        for blk in blocks:
            if str(blk["id"]) in saved:
                blk.update(saved[str(blk["id"])])
        if key == "stacks":
            for blk in blocks:
                blk["active"] = max(0, min(blk.get("active", 0), len(blk.get("groups", [])) - 1))
    for key, saved in layout.get("single", {}).items():
        if key in SINGLES:
            data.setdefault(key, {}).update(saved)
    if layout.get("theme_preset") and layout.get("theme"):
        data["theme_preset"] = layout["theme_preset"]
        data["theme"] = copy.deepcopy(layout["theme"])


def save(data: dict, name: str) -> dict:
    """Save the current arrangement under `name` (replacing one with that name)."""
    layout = snapshot(data, name)
    layouts = data.setdefault("layouts", [])
    for i, old in enumerate(layouts):
        if old["name"].casefold() == name.casefold():
            layouts[i] = layout
            break
    else:
        layouts.append(layout)
    data["active_layout"] = name
    return layout


def find(data: dict, name: str) -> dict | None:
    return next((l for l in data.get("layouts", []) if l["name"].casefold() == name.casefold()), None)
