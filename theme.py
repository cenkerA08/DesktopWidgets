"""
theme.py — Single source of truth for all colors, fonts, and layout sizes.
Everything else imports from here. Change a value here, it changes everywhere.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

CHROMA = "#010203"

SNAP        = 10
MARGIN      = 10
HDR_H       = 36
RSZ         = 14
CELL_W      = 88
CELL_H      = 90
PAD         = 14
MIN_COLS    = 1
MAX_COLS    = 12
ICON_SZ     = 52
ICON_NAT    = 256
COLLAPSE_BTN_W = 28


@dataclass
class Theme:
    bg:       str = "#1c1f26"
    hdr:      str = "#14161c"
    border:   str = "#3a3e4a"
    hov:      str = "#2a2e3e"
    btn:      str = "#2e3240"
    btn_h:    str = "#3a3f58"
    txt:      str = "#f0f0f0"
    txt2:     str = "#9098aa"
    txt3:     str = "#c8ccd6"
    accent:   str = "#5b7cf8"
    ok:       str = "#5b7cf8"
    warn:     str = "#e0a050"
    danger:   str = "#e05c5c"
    up_col:   str = "#5bc8f5"
    dn_col:   str = "#58d68d"
    stat_font: str = "Consolas"

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


PRESETS: dict[str, Theme] = {

    # ── Neutral dark — the defaults ────────────────────────

    # Neutral dark blue-grey — the default
    "Dark Blue": Theme(),

    # Cool blue-grey bg — feels like a code editor
    "Tokyo Night": Theme(
        bg="#1a1b2e", hdr="#13141f", border="#2a2b40",
        hov="#24253a", btn="#252636", btn_h="#303148",
        accent="#7aa2f7", ok="#9ece6a",
        txt="#c0caf5", txt2="#565f89", txt3="#a9b1d6",
        warn="#e0af68", danger="#f7768e",
        up_col="#7dcfff", dn_col="#9ece6a",
    ),

    # Muted blue-grey — Scandinavian, calm
    "Nord": Theme(
        bg="#2e3440", hdr="#242932", border="#434c5e",
        hov="#3b4252", btn="#3b4252", btn_h="#434c5e",
        accent="#88c0d0", ok="#a3be8c",
        txt="#eceff4", txt2="#8896a8", txt3="#d8dee9",
        warn="#ebcb8b", danger="#bf616a",
        up_col="#88c0d0", dn_col="#a3be8c",
    ),

    # Purple-grey bg — feels rich and moody
    "Dracula": Theme(
        bg="#282a36", hdr="#1e1f29", border="#44475a",
        hov="#383a4a", btn="#3a3c4e", btn_h="#484a5e",
        accent="#bd93f9", ok="#50fa7b",
        txt="#f8f8f2", txt2="#6272a4", txt3="#cdd6f4",
        warn="#ffb86c", danger="#ff5555",
        up_col="#8be9fd", dn_col="#50fa7b",
    ),

    # ── Light themes ───────────────────────────────────────

    # Bright icy blue-white — the only real light theme
    "Ice": Theme(
        bg="#e8f4f8", hdr="#d0e8f0", border="#90c8e0",
        hov="#d8eef8", btn="#c8e4f0", btn_h="#b0d8ec",
        accent="#0088cc", ok="#0077bb",
        txt="#001830", txt2="#406080", txt3="#204060",
        warn="#cc6600", danger="#cc0022",
        up_col="#0088cc", dn_col="#00aacc",
        stat_font="Consolas",
    ),

    # Warm cream/paper bg — easy on the eyes all day
    "Parchment": Theme(
        bg="#f5f0e8", hdr="#ede5d8", border="#c8b89a",
        hov="#ede5d8", btn="#e5ddd0", btn_h="#d8cfc0",
        accent="#8b4513", ok="#5a7a3a",
        txt="#2a1a0a", txt2="#7a6050", txt3="#5a4030",
        warn="#c87020", danger="#b83030",
        up_col="#8b4513", dn_col="#5a7a3a",
        stat_font="Georgia",
    ),

    # Soft grey-white — clean minimal
    "Silver": Theme(
        bg="#f0f0f2", hdr="#e0e0e4", border="#b0b0bc",
        hov="#e4e4e8", btn="#d8d8de", btn_h="#c8c8d0",
        accent="#4466cc", ok="#336633",
        txt="#181820", txt2="#505060", txt3="#303040",
        warn="#aa6600", danger="#aa2222",
        up_col="#4466cc", dn_col="#336633",
    ),

    # ── Warm-tinted backgrounds ────────────────────────────

    # Deep teal bg — feels like deep water
    "Abyss": Theme(
        bg="#0a1a1c", hdr="#061214", border="#0e3038",
        hov="#102428", btn="#122830", btn_h="#183440",
        accent="#00e5ff", ok="#00e5ff",
        txt="#d8f8ff", txt2="#2a7888", txt3="#70c8d8",
        warn="#ffaa00", danger="#ff3344",
        up_col="#00e5ff", dn_col="#00ff88",
        stat_font="Consolas",
    ),

    # Dark teal-black + electric cyan
    "Neural": Theme(
        bg="#080c10", hdr="#040810", border="#0a3040",
        hov="#0c1820", btn="#0e2030", btn_h="#142840",
        accent="#00e5ff", ok="#00e5ff",
        txt="#e0f8ff", txt2="#2a7a9a", txt3="#80d8f0",
        warn="#ff9500", danger="#ff1744",
        up_col="#00e5ff", dn_col="#00ff88",
        stat_font="Consolas",
    ),

    # Dark warm amber-brown bg + yellow accent
    "Cyberpunk": Theme(
        bg="#0d0d12", hdr="#080810", border="#2a1a3a",
        hov="#151020", btn="#1a1428", btn_h="#221c38",
        accent="#f0e000", ok="#f0e000",
        txt="#fff8e0", txt2="#aa9840", txt3="#ddd080",
        warn="#ff6600", danger="#ff0044",
        up_col="#f0e000", dn_col="#00ffee",
    ),

    # Dark blue-black + warm sunset orange
    "Dusk": Theme(
        bg="#0e1018", hdr="#090b12", border="#2a2d3a",
        hov="#191d2a", btn="#1e2230", btn_h="#272c3e",
        accent="#e8724a", ok="#e8724a",
        txt="#f0ece8", txt2="#7a7a8a", txt3="#c8b8a8",
        warn="#e8a84a", danger="#e85a4a",
        up_col="#e8724a", dn_col="#4a7ae8",
        stat_font="Consolas",
    ),

    # Rich warm brown bg + amber
    "Ember": Theme(
        bg="#1a1000", hdr="#120b00", border="#3a2200",
        hov="#261800", btn="#2c1c00", btn_h="#382400",
        accent="#ffaa00", ok="#ffaa00",
        txt="#fff8e0", txt2="#8a6020", txt3="#ffd080",
        warn="#ff6600", danger="#ff2222",
        up_col="#ffaa00", dn_col="#ff6600",
        stat_font="Consolas",
    ),

    # Dark burgundy-brown bg + warm orange
    "Rust": Theme(
        bg="#1a0e08", hdr="#120908", border="#3a1808",
        hov="#261408", btn="#2c1808", btn_h="#382008",
        accent="#fb923c", ok="#fb923c",
        txt="#fff4e8", txt2="#8a5030", txt3="#d09060",
        warn="#fbbf24", danger="#ef4444",
        up_col="#fb923c", dn_col="#facc15",
        stat_font="Consolas",
    ),

    # ── Cool-tinted backgrounds ────────────────────────────

    # Deep ocean navy bg + sky blue
    "Ocean": Theme(
        bg="#071428", hdr="#050e1c", border="#0e2848",
        hov="#0c2040", btn="#102448", btn_h="#142c58",
        accent="#38bdf8", ok="#38bdf8",
        txt="#e0f4ff", txt2="#3a70a0", txt3="#80c8f0",
        warn="#fbbf24", danger="#f87171",
        up_col="#38bdf8", dn_col="#34d399",
        stat_font="Consolas",
    ),

    # Deep purple bg + lavender — rich and vivid
    "Void": Theme(
        bg="#120820", hdr="#0c0618", border="#2a1050",
        hov="#1c1038", btn="#201440", btn_h="#281848",
        accent="#c084fc", ok="#c084fc",
        txt="#f5e8ff", txt2="#7040a0", txt3="#d0a0f0",
        warn="#ffcc00", danger="#ff4466",
        up_col="#c084fc", dn_col="#60a0ff",
        stat_font="Consolas",
    ),

    # Deep pink-purple bg + hot pink
    "Midnight": Theme(
        bg="#180820", hdr="#100618", border="#381048",
        hov="#220c30", btn="#281040", btn_h="#301448",
        accent="#ff4080", ok="#ff4080",
        txt="#fff0f8", txt2="#904070", txt3="#ffaad0",
        warn="#ffcc00", danger="#ff1744",
        up_col="#ff4080", dn_col="#c084fc",
        stat_font="Consolas",
    ),

    # Deep green bg + neon green
    "Forest": Theme(
        bg="#061408", hdr="#040e06", border="#0a2c10",
        hov="#0c2010", btn="#0e2412", btn_h="#122c18",
        accent="#39ff14", ok="#39ff14",
        txt="#e0ffe0", txt2="#2a7a20", txt3="#90e080",
        warn="#ffdd00", danger="#ff4422",
        up_col="#39ff14", dn_col="#00ffcc",
        stat_font="Consolas",
    ),

    # ── Unique / special ───────────────────────────────────

    # Deep ocean teal + solar green — solarized classic
    "Solarized": Theme(
        bg="#002b36", hdr="#00212b", border="#073642",
        hov="#003d4a", btn="#00424f", btn_h="#005060",
        accent="#268bd2", ok="#859900",
        txt="#fdf6e3", txt2="#657b83", txt3="#93a1a1",
        warn="#cb4b16", danger="#dc322f",
        up_col="#2aa198", dn_col="#859900",
    ),

    # Deep purple bg + neon pink/cyan — retro aesthetic
    "Vaporwave": Theme(
        bg="#1a0828", hdr="#120520", border="#3a1050",
        hov="#241040", btn="#2a1448", btn_h="#341858",
        accent="#ff71ce", ok="#05ffa1",
        txt="#ffffe0", txt2="#b967ff", txt3="#ffffa0",
        warn="#fffb96", danger="#ff3c6e",
        up_col="#01cdfe", dn_col="#05ffa1",
    ),

    # Pure black bg + white — maximum contrast
    "Mono": Theme(
        bg="#0a0a0a", hdr="#050505", border="#282828",
        hov="#141414", btn="#181818", btn_h="#202020",
        accent="#ffffff", ok="#ffffff",
        txt="#ffffff", txt2="#606060", txt3="#c0c0c0",
        warn="#ffcc00", danger="#ff4444",
        up_col="#ffffff", dn_col="#aaaaaa",
        stat_font="Consolas",
    ),

}

active: Theme = Theme()