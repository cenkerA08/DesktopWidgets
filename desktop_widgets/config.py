"""
config.py — Loads, saves, and validates all persisted application data.
No tkinter imports here — pure data.
"""
from __future__ import annotations
import json, os, sys, copy
from desktop_widgets.theme import Theme, PRESETS
from desktop_widgets.services.safe_io import atomic_write_json

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
        "stacks": [],         # list of {id, name, groups: [folder ids], active, cols, x, y, collapsed, theme_override}
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
        "corner_radius": 8,
        "theme_preset": "Dark",
        "design_revision": 2,
        "resize_enabled": True,
        "tray_corner": "bottom_right",
    }


def _migrate(d: dict) -> dict:
    """Bring old data format up to current version."""
    if not d.get("design_revision"):
        d["corner_radius"] = 16
        d["design_revision"] = 1
        if d.get("theme_preset", "Dark Blue") == "Dark Blue":
            d["theme"] = Theme().to_dict()
            d["theme_preset"] = "Graphite"
    if d.get("design_revision", 1) < 2:
        # Windows 11 redesign: themes map to the new set, corners and icons
        # follow the new defaults once (they stay adjustable in Settings).
        from desktop_widgets.theme import LEGACY_PRESETS
        def new_name(name):
            if name in PRESETS and name not in LEGACY_PRESETS:
                return name
            return LEGACY_PRESETS.get(name, "Dark")
        d["theme_preset"] = new_name(d.get("theme_preset", "Dark"))
        d["theme"] = PRESETS[d["theme_preset"]].to_dict()
        blocks = list(d.get("groups", [])) + list(d.get("docs_widgets", []))
        blocks += [d[k] for k in ("statsplus", "notes", "media") if isinstance(d.get(k), dict)]
        for blk in blocks:
            override = blk.get("theme_override")
            if override and override.get("__preset__"):
                name = new_name(override["__preset__"])
                blk["theme_override"] = {**PRESETS[name].to_dict(), "__preset__": name}
            elif override:
                blk["theme_override"] = None
        d["corner_radius"] = 8
        if d.get("icon_size") == 52:
            d["icon_size"] = 48
        d["design_revision"] = 2
    # Apps dropped from Explorer were saved with forward slashes, which
    # broke their icons. Normalise them once on load.
    from desktop_widgets.services.apps import normalize_path
    for g in d.get("groups", []):
        for app in g.get("apps", []):
            for key in ("path", "icon_path"):
                if app.get(key):
                    app[key] = normalize_path(app[key])
    for dw in d.get("docs_widgets", []):
        for f in dw.get("files", []):
            if f.get("path"):
                f["path"] = normalize_path(f["path"])

    # v1 → v2: add collapsed, theme_override to groups
    for g in d.get("groups", []):
        g.setdefault("collapsed", False)
        g.setdefault("theme_override", None)
        g.setdefault("apps", [])
        g.setdefault("x", 60)
        g.setdefault("y", 60)
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
    from desktop_widgets.services.screens import CORNERS
    if d.get("tray_corner") not in CORNERS:
        d["tray_corner"] = "bottom_right"
    if "media" not in d:
        d["media"] = _default()["media"]
    else:
        d["media"].setdefault("collapsed", False)
        d["media"].setdefault("theme_override", None)
    # Folder stacks: keep only folders that still exist, each in one stack.
    ids, seen = {g.get("id") for g in d.get("groups", [])}, set()
    stacks = []
    for st in d.get("stacks", []):
        st["groups"] = [gid for gid in st.get("groups", []) if gid in ids and gid not in seen]
        seen.update(st["groups"])
        if st["groups"]:
            for key, value in (("name", "Stack"), ("active", 0), ("cols", 5), ("x", 60), ("y", 60),
                               ("collapsed", False), ("theme_override", None)):
                st.setdefault(key, value)
            stacks.append(st)
    d["stacks"] = stacks
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
            # Starting fresh would save over the user's folders on the next
            # save; keep the unreadable file so it can be recovered.
            try:
                import shutil, time
                shutil.copy2(DATA_FILE, f"{DATA_FILE}.unreadable-{time.strftime('%Y%m%d-%H%M%S')}")
            except OSError:
                pass
    return _default()


def save(data: dict) -> None:
    try:
        atomic_write_json(DATA_FILE, data, indent=2)
    except Exception as e:
        print(f"[config] save error: {e}")


def get_corner_radius(data: dict) -> int:
    """Return the global corner radius setting (0 = square, up to 16)."""
    return max(0, min(24, int(data.get("corner_radius", 8))))


def get_theme(data: dict, override: dict | None = None) -> Theme:
    """Return the active Theme, optionally merged with a widget-level override.

    override can now be a full preset dict (stored with a '__preset__' key)
    or None to use the global theme.
    """
    from desktop_widgets.theme import PRESETS
    base = Theme.from_dict(data.get("theme", {}))
    if override:
        preset_name = override.get("__preset__")
        from desktop_widgets.theme import LEGACY_PRESETS
        if preset_name == "Wallpaper":
            from desktop_widgets.services import wallpaper
            live = wallpaper.theme()
            if live is not None:
                return live
        if preset_name not in PRESETS:
            preset_name = LEGACY_PRESETS.get(preset_name, preset_name)
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
