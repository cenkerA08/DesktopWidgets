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


# ── 18 Distinct Themes ─────────────────────────────────────
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

    # 9. Synthwave - purple and yellow (neon 80s vibes)
    "Synthwave": Theme(
        bg="#120b1f", hdr="#0c0717", border="#3f2a5c",
        hov="#1f1435", btn="#251b3a", btn_h="#2f234a",
        accent="#f6d365", ok="#f6d365",
        txt="#f0e6ff", txt2="#b79fd9", txt3="#d8c2ff",
        warn="#ff9f4b", danger="#ff4d6d",
        up_col="#f6d365", dn_col="#b983ff",
        stat_font="Consolas",
    ),

    # 10. Blood & Chrome - black and red
    "Blood & Chrome": Theme(
        bg="#0a0505", hdr="#0f0808", border="#4a1a1a",
        hov="#1f0f0f", btn="#2a1414", btn_h="#351c1c",
        accent="#ff3a3a", ok="#ff3a3a",
        txt="#ffd7d7", txt2="#b36b6b", txt3="#ff9e9e",
        warn="#ff8c42", danger="#ff1a1a",
        up_col="#ff5a5a", dn_col="#ff9090",
        stat_font="Consolas",
    ),

    # 11. Dark Violet - dark purple with pink accents
    "Dark Violet": Theme(
        bg="#130712", hdr="#0e050d", border="#3a1f3a",
        hov="#221022", btn="#2c152c", btn_h="#3a1f3a",
        accent="#ff77ff", ok="#ff77ff",
        txt="#ffe6ff", txt2="#d48fd4", txt3="#ffb8ff",
        warn="#ffb347", danger="#ff5f9e",
        up_col="#ff99ff", dn_col="#cc66ff",
        stat_font="Consolas",
    ),

    # 12. Toxic Waste - black and neon green
    "Toxic": Theme(
        bg="#0a0f0a", hdr="#071007", border="#1f4a1f",
        hov="#122012", btn="#1a2f1a", btn_h="#214021",
        accent="#9eff4f", ok="#9eff4f",
        txt="#e3ffcf", txt2="#7cb852", txt3="#b2ff7a",
        warn="#ffd966", danger="#ff6b6b",
        up_col="#b0ff70", dn_col="#4eff9e",
        stat_font="Consolas",
    ),

    # 13. Electric Blue - deep black with bright electric blue
    "Electric": Theme(
        bg="#0a0d12", hdr="#070a0f", border="#1a3a5a",
        hov="#101a24", btn="#182433", btn_h="#203c5c",
        accent="#3aa8ff", ok="#3aa8ff",
        txt="#d9f0ff", txt2="#6090c0", txt3="#9ac8ff",
        warn="#ffb347", danger="#ff5f6d",
        up_col="#3aa8ff", dn_col="#6cd4ff",
        stat_font="Consolas",
    ),

    # 14. Neon Noir - black with pink and cyan
    "Neon Noir": Theme(
        bg="#0b0b14", hdr="#070710", border="#2a1f40",
        hov="#151528", btn="#1d1d35", btn_h="#252545",
        accent="#ff44aa", ok="#ff44aa",
        txt="#f0e6ff", txt2="#a678b3", txt3="#d9b3ff",
        warn="#ffaa44", danger="#ff4466",
        up_col="#44ccff", dn_col="#ff44aa",
        stat_font="Consolas",
    ),

    # 15. Amber Alert - black and amber/orange
    "Amber Alert": Theme(
        bg="#0f0c06", hdr="#0a0804", border="#4a3a1a",
        hov="#1f1a0d", btn="#2f2616", btn_h="#3f3420",
        accent="#ffb347", ok="#ffb347",
        txt="#ffebc2", txt2="#cc9540", txt3="#ffcc80",
        warn="#ff9500", danger="#ff4d4d",
        up_col="#ffaa33", dn_col="#ffcc66",
        stat_font="Consolas",
    ),

    # 16. Matrix - black and matrix green
    "Matrix": Theme(
        bg="#0c100c", hdr="#070a07", border="#1f4a1f",
        hov="#142014", btn="#1c301c", btn_h="#244024",
        accent="#3aff5a", ok="#3aff5a",
        txt="#b3ffb3", txt2="#4f8a4f", txt3="#80ff80",
        warn="#e6b800", danger="#ff4d4d",
        up_col="#3aff5a", dn_col="#70ff70",
        stat_font="Courier New",
    ),

    # 17. Deep Purple - rich purple with gold accents
    "Deep Purple": Theme(
        bg="#1a1020", hdr="#140c1a", border="#3f2a55",
        hov="#2a1a35", btn="#322040", btn_h="#402a55",
        accent="#ffd966", ok="#ffd966",
        txt="#f0e0ff", txt2="#ad85c2", txt3="#d9b3ff",
        warn="#ff9f4b", danger="#ff6b8b",
        up_col="#bf7fff", dn_col="#ffd966",
        stat_font="Consolas",
    ),

    # 18. Crimson - black and deep red
    "Crimson": Theme(
        bg="#140a0a", hdr="#0f0707", border="#4a1f1f",
        hov="#241212", btn="#2f1a1a", btn_h="#3f2424",
        accent="#ff5e5e", ok="#ff5e5e",
        txt="#ffd6d6", txt2="#b36b6b", txt3="#ffa3a3",
        warn="#ffaa33", danger="#ff2a2a",
        up_col="#ff7a7a", dn_col="#ffaaaa",
        stat_font="Consolas",
    ),
}

# Module-level active theme (Manager will set this from saved data)
active: Theme = Theme()