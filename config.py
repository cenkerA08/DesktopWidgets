"""
config.py — Loads, saves, and validates all persisted application data.
No tkinter imports here — pure data.
"""
from __future__ import annotations
import json, os, sys, copy
from theme import Theme, PRESETS

# ── Data file location ─────────────────────────────────────
if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

DATA_DIR  = os.path.join(os.environ.get("APPDATA", _BASE), "DesktopWidget")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "data.json")

# ── URL/launcher app registry (populated at load time) ─────
URL_APPS: dict[str, dict] = {}   # path -> {launch, icon_path}

# ── Default data structure ─────────────────────────────────
def _default() -> dict:
    return {
        "version":  3,
        "next_id":  3,
        "theme":    Theme().to_dict(),
        "groups": [
            {"id": 1, "name": "Programs", "apps": [], "x": 60,  "y": 60,  "cols": 5,
             "collapsed": False, "theme_override": None},
            {"id": 2, "name": "Games",    "apps": [], "x": 60,  "y": 340, "cols": 5,
             "collapsed": False, "theme_override": None},
        ],
        "stats": {
            "enabled":  False,
            "x": 300, "y": 60, "w": 240, "h": 280,
            "collapsed": False,
            "metrics": ["cpu", "ram", "gpu", "disk"],
            "theme_override": None,
        },
        "statsplus": {
            "enabled": False,
            "x": 460, "y": 60, "w": 260, "h": 310,
            "collapsed": False,
            "metrics": ["cpu_pct", "cpu_temp", "ram_pct", "gpu_pct", "gpu_temp"],
            "theme_override": None,
        },
        "notes": {
            "enabled": False,
            "x": 620, "y": 60, "w": 240, "h": 300,
            "collapsed": False,
            "text": "",
            "theme_override": None,
        },
        "docs_widgets": [],   # list of {id, name, files, x, y, cols, collapsed, theme_override}
        "network": {
            "enabled":  False,
            "x": 300, "y": 360, "w": 240, "h": 120,
            "collapsed": False,
            "theme_override": None,
        },
        "media": {
            "enabled":  False,
            "x": 100, "y": 100, "w": 300,
            "collapsed": False,
            "theme_override": None,
        },
        "corner_radius": 0,
        "resize_enabled": True,
    }


def _migrate(d: dict) -> dict:
    """Bring old data format up to current version."""
    # v1 → v2: add collapsed, theme_override to groups
    for g in d.get("groups", []):
        g.setdefault("collapsed", False)
        g.setdefault("theme_override", None)
        g.setdefault("apps", [])
        g["x"] = max(0, g.get("x", 60))
        g["y"] = max(0, g.get("y", 60))
        g.setdefault("cols", 5)

    # Add stats / network blocks if missing
    if "stats" not in d:
        d["stats"] = _default()["stats"]
        # migrate old keys
        if d.get("show_stats"):
            d["stats"]["enabled"] = True
            pos = d.get("stats_pos", {})
            d["stats"].update({"x": pos.get("x", 300), "y": pos.get("y", 60),
                                "w": pos.get("w", 240), "h": pos.get("h", 280)})

    if "network" not in d:
        d["network"] = _default()["network"]
        if d.get("show_network"):
            d["network"]["enabled"] = True
            pos = d.get("net_pos", {})
            d["network"].update({"x": pos.get("x", 300), "y": pos.get("y", 360),
                                  "w": pos.get("w", 240), "h": pos.get("h", 120)})

    for blk in ("stats", "network"):
        d[blk].setdefault("collapsed", False)
        d[blk].setdefault("theme_override", None)
        d[blk].setdefault("metrics", ["cpu", "ram", "gpu", "disk"])

    # v2 → v3: statsplus, notes, docs_widgets
    if "statsplus" not in d:
        d["statsplus"] = _default()["statsplus"]
    if "notes" not in d:
        d["notes"] = _default()["notes"]
    if "docs_widgets" not in d:
        d["docs_widgets"] = []
    for dw in d["docs_widgets"]:
        dw.setdefault("collapsed", False)
        dw.setdefault("theme_override", None)
        dw.setdefault("files", [])
        dw.setdefault("cols", 3)

    d.setdefault("theme", Theme().to_dict())
    d.setdefault("next_id", 3)
    d.setdefault("corner_radius", 0)
    d.setdefault("resize_enabled", True)
    if "media" not in d:
        d["media"] = _default()["media"]
    else:
        d["media"].setdefault("collapsed", False)
        d["media"].setdefault("theme_override", None)
    d["version"] = 3
    return d


def load() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            d = _migrate(d)
            # Populate URL_APPS registry
            for g in d["groups"]:
                for app in g["apps"]:
                    if "launch" in app and app.get("path"):
                        URL_APPS[app["path"]] = {
                            "launch":    app["launch"],
                            "icon_path": app.get("icon_path"),
                        }
            return d
        except Exception as e:
            print(f"[config] load error: {e}")
    return _default()


def save(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[config] save error: {e}")


def get_corner_radius(data: dict) -> int:
    """Return the global corner radius setting (0 = square, up to 16)."""
    return int(data.get("corner_radius", 0))


def get_theme(data: dict, override: dict | None = None) -> Theme:
    """Return the active Theme, optionally merged with a widget-level override.

    override can now be a full preset dict (stored with a '__preset__' key)
    or None to use the global theme.
    """
    from theme import PRESETS
    base = Theme.from_dict(data.get("theme", {}))
    if override:
        preset_name = override.get("__preset__")
        if preset_name and preset_name in PRESETS:
            return PRESETS[preset_name]
        # Legacy: manual key/value overrides (kept for backwards compat)
        merged = base.copy()
        for k, v in override.items():
            if k.startswith("__"): continue
            if v is not None and hasattr(merged, k):
                setattr(merged, k, v)
        return merged
    return base