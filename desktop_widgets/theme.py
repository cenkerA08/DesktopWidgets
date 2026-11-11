"""
theme.py — Single source of truth for all colors, fonts, and layout sizes.
Everything else imports from here. Change a value here, it changes everywhere.

The look follows Windows 11 (Fluent): neutral layered surfaces, hairline
borders, one accent colour, Segoe UI Variable type and Segoe Fluent Icons.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

CHROMA = "#010203"

SNAP        = 10
MARGIN      = 10
HDR_H       = 40
RSZ         = 14
CELL_W      = 88
CELL_H      = 90
PAD         = 14
MIN_COLS    = 1
MAX_COLS    = 12
ICON_SZ     = 48
ICON_NAT    = 256
COLLAPSE_BTN_W = 28

_CELL_SIZES = {"compact": (72, 76, 8), "normal": (88, 90, 14), "spacious": (104, 108, 16)}


def apply_sizes(data: dict) -> None:
    """Apply the saved icon/tile size settings; tiles always fit their icon."""
    global ICON_SZ, CELL_W, CELL_H, PAD
    ICON_SZ = int(data.get("icon_size", 48))
    CELL_W, CELL_H, PAD = _CELL_SIZES.get(data.get("cell_size", "normal"), _CELL_SIZES["normal"])
    CELL_W = max(CELL_W, ICON_SZ + 32)
    CELL_H = max(CELL_H, ICON_SZ + 36)


# ── Type ramp (Windows 11) ─────────────────────────────────
# Families are resolved against what is installed in init_fonts(): Segoe UI
# Variable on Windows 11, plain Segoe UI on Windows 10.
FONT = "Segoe UI"
FONT_SEMI = "Segoe UI Semibold"
FONT_DISPLAY = "Segoe UI Semibold"
ICON_FONT = "Segoe MDL2 Assets"

TYPE = {
    "display": (FONT_DISPLAY, 20),   # screen titles
    "title":   (FONT_SEMI, 13),      # card titles inside screens
    "subtitle": (FONT_SEMI, 11),     # group headings in settings
    "header":  (FONT_SEMI, 10),      # widget header title
    "body":    (FONT, 10),
    "strong":  (FONT_SEMI, 10),
    "label":   (FONT, 9),            # small button text
    "caption": (FONT, 9),
    "meta":    (FONT, 9),            # header status (Live, 7 apps)
}

# PIL font files for images rendered off-screen (stats, media, focus hero).
PIL_FONT = "segoeui.ttf"
PIL_SEMI = "seguisb.ttf"
PIL_ICONS = "segmdl2.ttf"

R_WIN   = 8      # screens, dialogs, menus
R_PANEL = 8      # cards inside a widget or screen
R_TILE  = 6      # app / file tiles
R_CTRL  = 5      # buttons, inputs
INSET   = 10     # gap between widget edge and its inset panel
ACTION_R = 14    # header button half-size

# Segoe Fluent Icons / MDL2 code points (same in both fonts).
ICON = {
    "add": "\uE710", "settings": "\uE713", "close": "\uE8BB", "search": "\uE721",
    "chevron_down": "\uE70D", "chevron_up": "\uE70E", "chevron_right": "\uE76C",
    "chevron_left": "\uE76B", "check": "\uE73E", "play": "\uE768", "pause": "\uE769",
    "prev": "\uE892", "next": "\uE893", "edit": "\uE70F", "delete": "\uE74D",
    "folder": "\uE8B7", "document": "\uE8A5", "note": "\uE70B", "stats": "\uE9D9",
    "music": "\uEC4F", "open": "\uE8A7", "power": "\uE7E8", "clear": "\uE894",
    "desktop": "\uE7F4", "picture": "\uE8B9", "remove": "\uE738", "rename": "\uE8AC",
    "palette": "\uE790", "apps": "\uE71D", "info": "\uE946", "sync": "\uE895",
    "heart": "\uEB51", "emoji": "\uE76E", "game": "\uE7FC", "link": "\uE71B",
    "focus": "\uE740", "grip": "\uE784", "copy": "\uE8C8", "stack": "\uE8F1", "sparkle": "\uE945",
}


def icon_font(size: int) -> tuple:
    return (ICON_FONT, size)


_fonts_ready = False


def init_fonts(root) -> None:
    """Pick the best installed families once a Tk root exists."""
    global FONT, FONT_SEMI, FONT_DISPLAY, ICON_FONT, PIL_ICONS, _fonts_ready
    if _fonts_ready:
        return
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families(root))
    except Exception:
        return
    def pick(*names):
        return next((n for n in names if n in families), names[-1])
    FONT = pick("Segoe UI Variable Text", "Segoe UI")
    FONT_SEMI = pick("Segoe UI Variable Text Semibold", "Segoe UI Semibold")
    FONT_DISPLAY = pick("Segoe UI Variable Display Semib", "Segoe UI Variable Display Semibold",
                        "Segoe UI Semibold")
    ICON_FONT = pick("Segoe Fluent Icons", "Segoe MDL2 Assets")
    import os
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    if os.path.exists(os.path.join(fonts, "SegoeIcons.ttf")):
        PIL_ICONS = "SegoeIcons.ttf"
    TYPE.update({
        "display": (FONT_DISPLAY, 20), "title": (FONT_SEMI, 13), "subtitle": (FONT_SEMI, 11),
        "header": (FONT_SEMI, 10), "body": (FONT, 10), "strong": (FONT_SEMI, 10),
        "label": (FONT, 9), "caption": (FONT, 9), "meta": (FONT, 9),
    })
    _fonts_ready = True


def on_color(color: str) -> str:
    """Readable text colour on a filled accent surface."""
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return "#000000" if (r*299 + g*587 + b*114) / 1000 > 150 else "#ffffff"


def mix(a: str, b: str, amount: float) -> str:
    """Blend two hex colours; amount 0 → a, 1 → b."""
    a, b = a.lstrip("#"), b.lstrip("#")
    out = []
    for i in (0, 2, 4):
        x, y = int(a[i:i+2], 16), int(b[i:i+2], 16)
        out.append(round(x + (y - x) * amount))
    return "#%02x%02x%02x" % tuple(out)


def is_light(t) -> bool:
    c = t.bg.lstrip("#")
    return (int(c[0:2], 16)*299 + int(c[2:4], 16)*587 + int(c[4:6], 16)*114) / 1000 > 128


@dataclass
class Theme:
    # Surfaces: bg is the window/widget (Mica), btn the card/control layer on it.
    bg:       str = "#202020"
    hdr:      str = "#202020"
    border:   str = "#333333"
    hov:      str = "#2d2d2d"
    btn:      str = "#2b2b2b"
    btn_h:    str = "#323232"
    txt:      str = "#ffffff"
    txt2:     str = "#a8a8a8"
    txt3:     str = "#d4d4d4"
    accent:   str = "#60cdff"
    ok:       str = "#6ccb5f"
    warn:     str = "#fce100"
    danger:   str = "#ff99a4"
    up_col:   str = "#60cdff"
    dn_col:   str = "#6ccb5f"
    stat_font: str = "Segoe UI"

    def copy(self) -> "Theme":
        return Theme(**asdict(self))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Theme":
        t = cls()
        for k, v in d.items():
            if hasattr(t, k):
                setattr(t, k, v)
        return t


def _dark(bg, layer, accent, **kw):
    """A dark theme from its two surface colours and accent; the rest follows."""
    base = dict(bg=bg, hdr=bg, btn=layer, border=mix(layer, "#ffffff", 0.07),
                hov=mix(bg, "#ffffff", 0.05), btn_h=mix(layer, "#ffffff", 0.05),
                txt="#ffffff", txt2="#a8a8a8", txt3="#d4d4d4",
                accent=accent, ok="#6ccb5f", warn="#fce100", danger="#ff99a4",
                up_col=accent, dn_col="#6ccb5f")
    base.update(kw)
    return Theme(**base)


def _light(bg, layer, accent, **kw):
    base = dict(bg=bg, hdr=bg, btn=layer, border=mix(bg, "#000000", 0.09),
                hov=mix(bg, "#000000", 0.04), btn_h=mix(layer, "#000000", 0.03),
                txt="#1b1b1b", txt2="#5f5f5f", txt3="#2f2f2f",
                accent=accent, ok="#0f7b0f", warn="#9d5d00", danger="#c42b1c",
                up_col=accent, dn_col="#0f7b0f")
    base.update(kw)
    return Theme(**base)


PRESETS: dict[str, Theme] = {
    # Windows 11 dark: neutral grey and the default blue accent.
    "Dark":     Theme(),
    "Light":    _light("#f3f3f3", "#fbfbfb", "#005fb8"),
    "Black":    _dark("#0f0f0f", "#1c1c1c", "#99ebff", txt2="#9a9a9a"),
    "Slate":    _dark("#1c2028", "#262b35", "#8ab4f8", txt2="#a3abba", txt3="#d3d9e4"),
    "Ocean":    _dark("#16222b", "#1f2e39", "#5fd4e8", txt2="#9fb4c2", txt3="#cfe0ea"),
    "Forest":   _dark("#18201b", "#212b25", "#7fd6a0", txt2="#a2b3a8", txt3="#d1ded5",
                      ok="#7fd6a0", dn_col="#7fd6a0"),
    "Plum":     _dark("#211c26", "#2b2533", "#c8a2ff", txt2="#b0a6bd", txt3="#ddd3e8"),
    "Rose":     _dark("#241c1f", "#2f2529", "#ff9ab8", txt2="#bba5ad", txt3="#e6d2d9"),
    "Mocha":    _dark("#221e1b", "#2d2824", "#f2b880", txt2="#b5aa9f", txt3="#e3d8cd"),
    "Mist":     _light("#eef2f6", "#f9fbfd", "#2167d1", txt2="#5a6472"),
    "Sand":     _light("#f4f0ea", "#fcfaf6", "#a35a14", txt2="#6b6158", ok="#4f7a28",
                       dn_col="#4f7a28"),
}

# Themes from earlier versions, mapped to the closest one in the current set.
LEGACY_PRESETS = {
    "Graphite": "Dark", "Dark Blue": "Dark", "Tokyo Night": "Slate", "Nord": "Slate",
    "Dracula": "Plum", "Void": "Plum", "Vaporwave": "Plum", "Midnight": "Rose",
    "Rose Quartz": "Rose", "Aurora": "Forest", "Forest": "Forest", "Ocean Mist": "Ocean",
    "Ocean": "Ocean", "Abyss": "Ocean", "Neural": "Ocean", "Solarized": "Ocean",
    "Porcelain": "Light", "Silver": "Light", "Ice": "Mist", "Parchment": "Sand",
    "Dusk": "Mocha", "Ember": "Mocha", "Rust": "Mocha", "Cyberpunk": "Black",
    "Mono": "Black", "Launch": "Black", "Crimson": "Black",
}

active: Theme = Theme()


def ui_font(data: dict) -> str:
    """The user's chosen font for note text; Segoe UI means the system font."""
    name = data.get("ui_font") or "Segoe UI"
    return FONT if name == "Segoe UI" else name
