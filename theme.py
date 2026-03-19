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


# ── 8 Distinct Themes ──────────────────────────────────────
PRESETS: dict[str, Theme] = {
    # 1. Cyberpunk (kept as requested)
    "Cyberpunk": Theme(
        bg="#0d0d12", hdr="#080810", border="#2a1a3a",
        hov="#151020", btn="#1a1428", btn_h="#221c38",
        accent="#f0e000", ok="#f0e000",
        txt="#fff8e0", txt2="#aa9840", txt3="#ddd080",
        warn="#ff6600", danger="#ff0044",
        up_col="#f0e000", dn_col="#00ffee",
    ),

    # 2. Ice (kept as requested)
    "Ice": Theme(
        bg="#e8f4f8", hdr="#d0e8f0", border="#90c8e0",
        hov="#d8eef8", btn="#c8e4f0", btn_h="#b0d8ec",
        accent="#0088cc", ok="#0077bb",
        txt="#001830", txt2="#406080", txt3="#204060",
        warn="#cc6600", danger="#cc0022",
        up_col="#0088cc", dn_col="#00aacc",
    ),

    # 3. Retro Terminal - amber monochrome
    "Retro": Theme(
        bg="#1a0f00", hdr="#0f0a00", border="#4a3a1a",
        hov="#2a1a00", btn="#2a1f0a", btn_h="#3a2f1a",
        accent="#ffb000", ok="#ffb000",
        txt="#ffcc88", txt2="#aa7733", txt3="#ddaa55",
        warn="#ff8800", danger="#ff4444",
        up_col="#ffaa33", dn_col="#88aa33",
        stat_font="Courier New",
    ),

    # 4. Ocean Depths - deep blues
    "Ocean": Theme(
        bg="#0a1a2a", hdr="#05121f", border="#1e405e",
        hov="#102435", btn="#142c40", btn_h="#1c3c55",
        accent="#3fa0e0", ok="#4ac0b0",
        txt="#e0f0ff", txt2="#88a0c0", txt3="#b0d0f0",
        warn="#e0a040", danger="#e06060",
        up_col="#40a0ff", dn_col="#40d0b0",
    ),

    # 5. Forest - earthy greens
    "Forest": Theme(
        bg="#1a2618", hdr="#121e10", border="#3a5230",
        hov="#243820", btn="#2c4428", btn_h="#345830",
        accent="#8bc34a", ok="#8bc34a",
        txt="#e8f0d8", txt2="#88a070", txt3="#c0d0a8",
        warn="#e0a040", danger="#d46b6b",
        up_col="#70c070", dn_col="#a0d070",
    ),

    # 6. Midnight Purple - dark with violet accents
    "Midnight": Theme(
        bg="#1a1428", hdr="#120e20", border="#3a2c50",
        hov="#241c38", btn="#2c2240", btn_h="#382a50",
        accent="#b280f0", ok="#b280f0",
        txt="#f0e8ff", txt2="#a088c0", txt3="#d0b8ff",
        warn="#e0a050", danger="#e07080",
        up_col="#8080ff", dn_col="#a080ff",
    ),

    # 7. Sunset - warm oranges and reds
    "Sunset": Theme(
        bg="#281810", hdr="#1d110a", border="#583a28",
        hov="#382418", btn="#402c20", btn_h="#503c30",
        accent="#ff9966", ok="#ff9966",
        txt="#fff0e0", txt2="#c09870", txt3="#f0c8a8",
        warn="#ffaa33", danger="#ff5555",
        up_col="#ff8866", dn_col="#ffaa66",
    ),

    # 8. Monochrome - grayscale with one accent
    "Monochrome": Theme(
        bg="#1a1a1a", hdr="#121212", border="#404040",
        hov="#282828", btn="#303030", btn_h="#383838",
        accent="#ffffff", ok="#cccccc",
        txt="#ffffff", txt2="#aaaaaa", txt3="#dddddd",
        warn="#cccccc", danger="#aaaaaa",
        up_col="#e0e0e0", dn_col="#c0c0c0",
    ),
}

# Module-level active theme (Manager will set this from saved data)
active: Theme = Theme()