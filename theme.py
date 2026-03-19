"""
theme.py — Single source of truth for all colors, fonts, and layout sizes.
Everything else imports from here. Change a value here, it changes everywhere.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

# ── Chroma key (tkinter transparency) ─────────────────────
CHROMA = "#010203"

# ── Layout constants ───────────────────────────────────────
SNAP        = 10    # grid snap (pixels) — finer grid for better alignment
MARGIN      = 10    # min gap from screen edge and between widgets
HDR_H       = 36    # header bar height
RSZ         = 14    # resize handle zone (px from edge)
CELL_W      = 88    # app icon cell width
CELL_H      = 90    # app icon cell height
PAD         = 14    # inner padding
MIN_COLS    = 1
MAX_COLS    = 12
ICON_SZ     = 52    # display icon size
ICON_NAT    = 256   # extraction size (native high-res)
COLLAPSE_BTN_W = 28 # collapse arrow button width


# ── Theme dataclass ────────────────────────────────────────
@dataclass
class Theme:
    # Backgrounds
    bg:       str = "#1c1f26"
    hdr:      str = "#14161c"
    border:   str = "#3a3e4a"
    hov:      str = "#2a2e3e"
    btn:      str = "#2e3240"
    btn_h:    str = "#3a3f58"
    # Text
    txt:      str = "#f0f0f0"
    txt2:     str = "#9098aa"
    txt3:     str = "#c8ccd6"
    # Accent / state colors
    accent:   str = "#5b7cf8"
    ok:       str = "#5b7cf8"
    warn:     str = "#e0a050"
    danger:   str = "#e05c5c"
    # Widget-specific
    up_col:   str = "#5bc8f5"
    dn_col:   str = "#58d68d"
    # Fonts
    stat_font: str = "Consolas"   # blocky/tech font for stat numbers

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


# ── Built-in color presets ─────────────────────────────────
PRESETS: dict[str, Theme] = {
    "Dark Blue": Theme(),
    "Midnight": Theme(
        bg="#0d0f14", hdr="#08090d", border="#252830",
        hov="#1a1d26", btn="#1e2130", btn_h="#282c40",
        accent="#7b6cf8",
    ),
    "Dark Green": Theme(
        bg="#131a18", hdr="#0b120f", border="#2a3d34",
        hov="#1a2e24", btn="#1e3028", btn_h="#28403a",
        accent="#3dbf7f", ok="#3dbf7f",
    ),
    "Dark Red": Theme(
        bg="#1a1414", hdr="#100c0c", border="#3d2a2a",
        hov="#2e1a1a", btn="#301e1e", btn_h="#402828",
        accent="#e05c6c", ok="#e05c6c",
    ),
    "Slate": Theme(
        bg="#1e2130", hdr="#161824", border="#32374a",
        hov="#262b3e", btn="#2c3148", btn_h="#363d58",
        accent="#90a0d0",
    ),
    "Mocha": Theme(
        bg="#1e1a17", hdr="#151210", border="#3d3530",
        hov="#2e2820", btn="#302820", btn_h="#403830",
        accent="#c8855a", ok="#c8855a",
        txt="#f0ebe6", txt2="#a09080", txt3="#d0c8bc",
    ),
    "Violet": Theme(
        bg="#1a1526", hdr="#110f1c", border="#352d50",
        hov="#241d3a", btn="#2a2240", btn_h="#362c54",
        accent="#a06cf8", ok="#a06cf8",
    ),
    "Cyan": Theme(
        bg="#111e22", hdr="#0a1518", border="#1e4048",
        hov="#152e36", btn="#183038", btn_h="#204048",
        accent="#2ecfcf", ok="#2ecfcf",
        up_col="#2ecfcf", dn_col="#58d68d",
    ),
    "Rose": Theme(
        bg="#1f1520", hdr="#150f16", border="#3d2540",
        hov="#2e1a30", btn="#32203a", btn_h="#422a4c",
        accent="#e06090", ok="#e06090",
        txt="#f5e8f0", txt2="#b088a8", txt3="#d8b8cc",
    ),
    "Amber": Theme(
        bg="#1c1a10", hdr="#131200", border="#3a3818",
        hov="#2e2c10", btn="#302e14", btn_h="#40401c",
        accent="#d4a820", ok="#d4a820",
        txt="#f5f0d8", txt2="#a09860", txt3="#d8d0a0",
        warn="#e07830", up_col="#d4a820", dn_col="#90c040",
    ),
    "Graphite": Theme(
        bg="#1a1a1a", hdr="#111111", border="#333333",
        hov="#242424", btn="#2a2a2a", btn_h="#383838",
        accent="#888888", ok="#888888",
        txt="#e8e8e8", txt2="#888888", txt3="#bbbbbb",
    ),
    "Nord": Theme(
        bg="#2e3440", hdr="#242932", border="#434c5e",
        hov="#3b4252", btn="#3b4252", btn_h="#434c5e",
        accent="#88c0d0", ok="#a3be8c",
        txt="#eceff4", txt2="#8896a8", txt3="#d8dee9",
        warn="#ebcb8b", danger="#bf616a",
        up_col="#88c0d0", dn_col="#a3be8c",
    ),
    # ── Vivid / high-contrast themes ──────────────────────
    "Neon Blue": Theme(
        bg="#0a0e1a", hdr="#060810", border="#1a2448",
        hov="#111830", btn="#141c38", btn_h="#1e2a50",
        accent="#00aaff", ok="#00aaff",
        txt="#e8f4ff", txt2="#6090c0", txt3="#a8ccee",
        warn="#ffaa00", danger="#ff3355",
        up_col="#00aaff", dn_col="#00ffaa",
    ),
    "Neon Green": Theme(
        bg="#071209", hdr="#040c06", border="#0e2e14",
        hov="#0a2010", btn="#0c2412", btn_h="#133018",
        accent="#00ff88", ok="#00ff88",
        txt="#e0ffe8", txt2="#40a060", txt3="#90dda8",
        warn="#ffdd00", danger="#ff4422",
        up_col="#00ffcc", dn_col="#88ff00",
    ),
    "Neon Pink": Theme(
        bg="#150a18", hdr="#0e060f", border="#38104a",
        hov="#200e28", btn="#261230", btn_h="#341840",
        accent="#ff00cc", ok="#ff00cc",
        txt="#ffe8ff", txt2="#aa50bb", txt3="#dd99ee",
        warn="#ffcc00", danger="#ff3344",
        up_col="#ff00cc", dn_col="#aa00ff",
    ),
    "Cyberpunk": Theme(
        bg="#0d0d12", hdr="#080810", border="#2a1a3a",
        hov="#151020", btn="#1a1428", btn_h="#221c38",
        accent="#f0e000", ok="#f0e000",
        txt="#fff8e0", txt2="#aa9840", txt3="#ddd080",
        warn="#ff6600", danger="#ff0044",
        up_col="#f0e000", dn_col="#00ffee",
    ),
    "Dracula": Theme(
        bg="#282a36", hdr="#1e1f29", border="#44475a",
        hov="#383a4a", btn="#3a3c4e", btn_h="#484a5e",
        accent="#bd93f9", ok="#50fa7b",
        txt="#f8f8f2", txt2="#6272a4", txt3="#cdd6f4",
        warn="#ffb86c", danger="#ff5555",
        up_col="#8be9fd", dn_col="#50fa7b",
    ),
    "Solarized": Theme(
        bg="#002b36", hdr="#00212b", border="#073642",
        hov="#003d4a", btn="#00424f", btn_h="#005060",
        accent="#268bd2", ok="#859900",
        txt="#fdf6e3", txt2="#657b83", txt3="#93a1a1",
        warn="#cb4b16", danger="#dc322f",
        up_col="#2aa198", dn_col="#859900",
    ),
    "Vaporwave": Theme(
        bg="#0d0015", hdr="#080010", border="#2a0040",
        hov="#150020", btn="#1a0030", btn_h="#220040",
        accent="#ff71ce", ok="#05ffa1",
        txt="#ffffe0", txt2="#b967ff", txt3="#ffffa0",
        warn="#fffb96", danger="#ff3c6e",
        up_col="#01cdfe", dn_col="#05ffa1",
    ),
    "Hacker": Theme(
        bg="#000a00", hdr="#000500", border="#003300",
        hov="#001500", btn="#001a00", btn_h="#002200",
        accent="#00ff41", ok="#00ff41",
        txt="#ccffcc", txt2="#007700", txt3="#00cc00",
        warn="#aaff00", danger="#ff0000",
        up_col="#00ff41", dn_col="#00cc44",
        stat_font="Courier New",
    ),
    "Tokyo Night": Theme(
        bg="#1a1b2e", hdr="#13141f", border="#2a2b40",
        hov="#24253a", btn="#252636", btn_h="#303148",
        accent="#7aa2f7", ok="#9ece6a",
        txt="#c0caf5", txt2="#565f89", txt3="#a9b1d6",
        warn="#e0af68", danger="#f7768e",
        up_col="#7dcfff", dn_col="#9ece6a",
    ),
    "Blood Orange": Theme(
        bg="#120800", hdr="#0c0500", border="#3d1a00",
        hov="#1e0c00", btn="#221000", btn_h="#301800",
        accent="#ff6600", ok="#ff6600",
        txt="#fff0e0", txt2="#995522", txt3="#ffbb88",
        warn="#ffcc00", danger="#ff1111",
        up_col="#ff6600", dn_col="#ff9900",
    ),
    "Ice": Theme(
        bg="#e8f4f8", hdr="#d0e8f0", border="#90c8e0",
        hov="#d8eef8", btn="#c8e4f0", btn_h="#b0d8ec",
        accent="#0088cc", ok="#0077bb",
        txt="#001830", txt2="#406080", txt3="#204060",
        warn="#cc6600", danger="#cc0022",
        up_col="#0088cc", dn_col="#00aacc",
        stat_font="Consolas",
    ),

    # Deep black with electric cyan — like a hacker terminal on steroids
    "Neural": Theme(
        bg="#080c10", hdr="#040810", border="#0a3040",
        hov="#0c1820", btn="#0e2030", btn_h="#142840",
        accent="#00e5ff", ok="#00e5ff",
        txt="#e0f8ff", txt2="#2a7a9a", txt3="#80d8f0",
        warn="#ff9500", danger="#ff1744",
        up_col="#00e5ff", dn_col="#00ff88",
        stat_font="Consolas",
    ),

    # Blood red on pitch black — aggressive and vivid
    "Crimson": Theme(
        bg="#0c0508", hdr="#080306", border="#6a1020",
        hov="#180810", btn="#200a12", btn_h="#2c1018",
        accent="#ff1744", ok="#ff1744",
        txt="#fff0f0", txt2="#882233", txt3="#ffaaaa",
        warn="#ff9500", danger="#ff6d00",
        up_col="#ff1744", dn_col="#ff6d00",
        stat_font="Consolas",
    ),

    # Dusk — matches the moody dark sunset wallpaper
    "Dusk": Theme(
        bg="#0e1018", hdr="#090b12", border="#2a2d3a",
        hov="#191d2a", btn="#1e2230", btn_h="#272c3e",
        accent="#e8724a", ok="#e8724a",
        txt="#f0ece8", txt2="#7a7a8a", txt3="#c8b8a8",
        warn="#e8a84a", danger="#e85a4a",
        up_col="#e8724a", dn_col="#4a7ae8",
        stat_font="Consolas",
    ),
}

# Module-level active theme (Manager will set this from saved data)
active: Theme = Theme()