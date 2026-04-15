"""
focus_overlay.py — Full-screen app launcher overlay.
Opened by double-clicking a group widget header.
PIL-rendered tiles with rounded corners, hover accent borders, clean layout.
"""
from __future__ import annotations
import math
import tkinter as tk
from typing import TYPE_CHECKING
from theme import HDR_H, PAD, CHROMA
from utils import get_icon, clip, launch_app
import config

if TYPE_CHECKING:
    from manager import Manager

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ── Layout ─────────────────────────────────────────────────
TILE_W   = 110   # tile width
TILE_H   = 130   # tile height — taller for bigger icons
TILE_PAD = 10    # padding inside each tile
TILE_R   = 12    # tile corner radius
ICON_SZ  = 64    # bigger icons — more distinct than the desktop widget
GAP      = 10    # gap between tiles
PANEL_P  = 20    # panel outer padding
MAX_COLS = 8     # single row up to 8, wraps after
HDR_H_OV = 48    # overlay header height

# ── Navigation side panels ──────────────────────────────────
SIDE_GAP       = 8    # gap between arrow and adjacent panel / main panel
SIDE_PEEK_W    = 200  # max visible width of each side panel
SIDE_MIN_AVAIL = 40   # skip side panel if less space available
SIDE_SCALE     = 0.82 # side panel height relative to main panel

# ── Carousel arrow buttons ──────────────────────────────────
ARROW_SZ = 42   # arrow button diameter

# ── Carousel animation ──────────────────────────────────────
CAR_STEPS = 16   # frames
CAR_MS    = 11   # ms per frame — ~176 ms total, smooth-step easing

# ── Side panel fade ──────────────────────────────────────────
FADE_W = 50      # gradient fade width at the outer edge of each side panel


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return (int(c[0:2],16), int(c[2:4],16), int(c[4:6],16))


def _rgba(c: str, a: int = 255) -> tuple:
    r, g, b = _hex(c)
    return (r, g, b, a)


def _draw_tile(size_w: int, size_h: int, bg: str, border: str,
               radius: int, hover: bool, accent: str) -> "Image.Image":
    """Render a single tile background at 2x then downscale."""
    S = 2
    W, H = size_w * S, size_h * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    col  = _rgba(accent, 30) if hover else _rgba(bg)
    brdr = _rgba(accent) if hover else _rgba(border)
    d.rounded_rectangle([0, 0, W-1, H-1], radius=radius*S,
                        fill=col, outline=brdr,
                        width=2 if hover else 1)
    return img.resize((size_w, size_h), Image.LANCZOS)


class FocusOverlay:
    def __init__(self, mgr: "Manager", group: dict) -> None:
        self.mgr    = mgr
        self.group  = group
        self._hov: int | None = None
        self._spots: list[dict] = []
        self._refs:  list = []
        self._tile_cache: dict = {}

        # Navigation between groups
        all_groups = mgr.data.get("groups", [])
        self._groups    = all_groups
        self._group_idx = next(
            (i for i, g in enumerate(all_groups) if g["id"] == group["id"]), 0
        )
        self._left_panel:      tk.Toplevel | None = None
        self._right_panel:     tk.Toplevel | None = None
        self._left_arrow_win:  tk.Toplevel | None = None
        self._right_arrow_win: tk.Toplevel | None = None
        self._side_refs:       list = []
        self._animating:       bool = False

        t    = config.get_theme(mgr.data, group.get("theme_override"))
        self._t = t
        sw   = mgr.root.winfo_screenwidth()
        sh   = mgr.root.winfo_screenheight()

        apps = group["apps"]
        n    = len(apps)

        # Single row — all apps in one line, wrap only if too wide for screen
        max_fit = max(1, (sw - PANEL_P*2) // (TILE_W + GAP))
        cols    = min(n, max_fit) if n > 0 else 1
        rows    = max(1, -(-n // cols)) if n > 0 else 1

        ww = PANEL_P*2 + cols*(TILE_W+GAP) - GAP
        wh = HDR_H_OV + PANEL_P*2 + rows*(TILE_H+GAP) - GAP + 28  # 28 for footer hint

        self._wx = (sw - ww) // 2
        self._wy = (sh - wh) // 2
        self._ww = ww
        self._wh = wh
        self._cols = cols

        # Dark backdrop — reuse handoff from carousel if available (no flash)
        _handoff = getattr(mgr, "_bg_handoff", None)
        mgr._bg_handoff    = None
        _carousel_open     = getattr(mgr, "_focus_carousel", False)
        mgr._focus_carousel = False
        if _handoff and _carousel_open:
            try:
                _handoff.bind("<Button-1>", self._bg_click)
                self.bg = _handoff
            except Exception:
                _handoff = None
        if not _handoff:
            self.bg = tk.Toplevel(mgr.root)
            self.bg.overrideredirect(True)
            self.bg.attributes("-topmost", True)
            self.bg.attributes("-alpha", 0.0)
            self.bg.configure(bg="#000000")
            self.bg.geometry(f"{sw}x{sh}+0+0")
            self.bg.bind("<Button-1>", self._bg_click)
            self._fade(0.0, 0.6)

        # Main panel
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=t.bg)
        self.win.geometry(f"{ww}x{wh}+{self._wx}+{self._wy}")

        self.cv = tk.Canvas(self.win, bg=t.bg, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        self.cv.bind("<Motion>",          self._hover)
        self.cv.bind("<Leave>",           self._leave)
        self.cv.bind("<Button-1>",        self._click)
        self.cv.bind("<Double-Button-1>", self._dbl)
        self.cv.bind("<Button-3>",        self._right)
        self.win.bind("<Escape>",         lambda e: self.close())

        self.bg.update_idletasks()
        self.win.lift(self.bg)
        self.win.focus_force()

        self._render()
        self._build_navigation()

        self.win.bind("<Left>",  lambda e: self._nav_dir("left"))
        self.win.bind("<Right>", lambda e: self._nav_dir("right"))

    # ── Fade ───────────────────────────────────────────────

    def _fade(self, cur: float, target: float = 0.6) -> None:
        cur = round(min(target, cur + 0.06), 3)
        try: self.bg.attributes("-alpha", cur)
        except: return
        if cur < target:
            self.bg.after(12, lambda: self._fade(cur, target))

    def _bg_click(self, e) -> None:
        if self._animating:
            return
        try:
            wx, wy = self.win.winfo_x(), self.win.winfo_y()
            ww, wh = self.win.winfo_width(), self.win.winfo_height()
            if not (wx <= e.x_root <= wx+ww and wy <= e.y_root <= wy+wh):
                self.close()
        except Exception:
            self.close()

    # ── Render ─────────────────────────────────────────────

    def _render(self, hov: int | None = None) -> None:
        self.cv.delete("all")
        self._spots.clear()
        self._refs.clear()
        t    = self._t
        apps = self.group["apps"]
        cols = self._cols
        ww, wh = self._ww, self._wh

        # ── Header ────────────────────────────────────────
        self.cv.create_rectangle(0, 0, ww, HDR_H_OV, fill=t.hdr, outline="")
        self.cv.create_line(0, HDR_H_OV, ww, HDR_H_OV, fill=t.border, width=1)

        # Group name centred
        self.cv.create_text(ww//2, HDR_H_OV//2,
            text=self.group["name"],
            font=("Segoe UI", 13, "bold"), fill=t.txt, anchor="center")

        # Esc hint left
        self.cv.create_text(PANEL_P, HDR_H_OV//2,
            text="Esc to close", font=("Segoe UI", 9), fill=t.txt2, anchor="w")

        # Close button — full header height box like settings screen (padx=14, pady fills height)
        cbw = 44   # padx=14 each side + icon width
        cbx = ww - cbw//2
        cby = HDR_H_OV // 2
        close_hov = (hov == -1)
        if close_hov:
            self.cv.create_rectangle(
                ww - cbw, 0, ww, HDR_H_OV,
                fill="#2a1515", outline="", tags="close_box")
        self.cv.create_text(cbx, cby, text="✕",
            font=("Segoe UI", 12),
            fill="#ff5555" if close_hov else t.txt2,
            anchor="center", tags="close_x")
        self._spots.append({
            "x1": ww - cbw, "y1": 0,
            "x2": ww,       "y2": HDR_H_OV,
            "close": True,
        })

        # ── Empty state ───────────────────────────────────
        if not apps:
            self.cv.create_text(ww//2, HDR_H_OV + (wh-HDR_H_OV)//2,
                text="No apps — use the + button to add some.",
                font=("Segoe UI", 11), fill=t.txt2,
                anchor="center", justify="center")
            return

        # ── App tiles ─────────────────────────────────────
        for i, app in enumerate(apps):
            col = i % cols
            row = i // cols
            tx  = PANEL_P + col * (TILE_W + GAP)
            ty  = HDR_H_OV + PANEL_P + row * (TILE_H + GAP)
            cx  = tx + TILE_W // 2
            is_hov = (i == hov)

            # Tile background (PIL rendered for antialiased corners)
            if PIL_OK:
                key = ("tile", is_hov)
                if key not in self._tile_cache:
                    img   = _draw_tile(TILE_W, TILE_H, t.hov if is_hov else t.btn,
                                       t.border, TILE_R, is_hov, t.accent)
                    photo = ImageTk.PhotoImage(img)
                    self._tile_cache[key] = photo
                self._refs.append(self._tile_cache[key])
                self.cv.create_image(tx, ty, image=self._tile_cache[key], anchor="nw")
            else:
                fill = t.hov if is_hov else t.btn
                outl = t.accent if is_hov else t.border
                self.cv.create_rectangle(tx, ty, tx+TILE_W, ty+TILE_H,
                                         fill=fill, outline=outl)

            # App icon
            icon_y = ty + TILE_PAD + ICON_SZ // 2 + 4
            photo  = get_icon(app["path"], ICON_SZ)
            if photo:
                self._refs.append(photo)
                self.cv.create_image(cx, icon_y, image=photo, anchor="center")
            else:
                # Fallback letter tile
                self.cv.create_rectangle(cx-24, icon_y-24, cx+24, icon_y+24,
                                         fill=t.accent, outline="")
                self.cv.create_text(cx, icon_y,
                    text=(app["name"][0].upper() if app["name"] else "?"),
                    font=("Segoe UI", 18, "bold"), fill="white", anchor="center")

            # App name
            name_y = ty + TILE_H - 18
            self.cv.create_text(cx, name_y,
                text=clip(app["name"], 12),
                font=("Segoe UI", 9), fill=t.txt if is_hov else t.txt2,
                anchor="center", width=TILE_W - 8)

            p, nm, gid = app["path"], app["name"], self.group["id"]
            self._spots.append({
                "x1": tx, "y1": ty, "x2": tx+TILE_W, "y2": ty+TILE_H,
                "idx": i,
                "dbl":   lambda pa=p: (launch_app(pa), self.close()),
                "right": lambda pa=p, na=nm, ga=gid: self.mgr.app_ctx(pa, na, ga),
            })

    # ── Hit test ───────────────────────────────────────────

    def _hit(self, x, y) -> dict | None:
        for s in self._spots:
            if s["x1"] <= x <= s["x2"] and s["y1"] <= y <= s["y2"]:
                return s
        return None

    # ── Events ─────────────────────────────────────────────

    def _hover(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and h.get("close"):     idx = -1
        elif h and "idx" in h:       idx = h["idx"]
        else:                        idx = None
        if idx != self._hov:
            self._hov = idx
            self._tile_cache.clear()   # invalidate so new hover color renders
            self._render(hov=idx)
        self.cv.config(cursor="hand2" if h else "arrow")

    def _leave(self, e) -> None:
        if self._hov is not None:
            self._hov = None
            self._tile_cache.clear()
            self._render()

    def _click(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and h.get("close"):
            self.close()

    def _dbl(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and "dbl" in h:
            h["dbl"]()
        elif e.y <= HDR_H_OV:
            self.close()

    def _right(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and "right" in h:
            h["right"]()

    # ── Navigation ─────────────────────────────────────────

    def _build_navigation(self) -> None:
        """
        Layout:  [left_panel] [SIDE_GAP] [left_arrow] [SIDE_GAP] [MAIN] [SIDE_GAP] [right_arrow] [SIDE_GAP] [right_panel]
        Side panels are SIDE_SCALE × main height, vertically centred on the main panel.
        Arrow buttons sit between each side panel and the main panel.
        """
        self._side_refs.clear()
        n = len(self._groups)
        if n <= 1:
            return

        sw       = self.mgr.root.winfo_screenwidth()
        side_h   = int(self._wh * SIDE_SCALE)
        side_y   = self._wy + (self._wh - side_h) // 2
        ay       = self._wy + (self._wh - ARROW_SZ) // 2

        prev_idx = (self._group_idx - 1) % n
        next_idx = (self._group_idx + 1) % n

        # ── Left side ─────────────────────────────────────
        left_ax = self._wx - SIDE_GAP - ARROW_SZ   # left arrow's x
        if left_ax >= 4:
            self._left_arrow_win = self._make_arrow_btn(
                "left", self._groups[prev_idx], left_ax, ay)
            panel_right = left_ax - SIDE_GAP
            vis_w = min(SIDE_PEEK_W, panel_right - 4)
            if vis_w >= SIDE_MIN_AVAIL:
                self._left_panel = self._make_side_panel(
                    self._groups[prev_idx], "left",
                    panel_right - vis_w, side_y, vis_w, side_h)

        # ── Right side ────────────────────────────────────
        right_ax = self._wx + self._ww + SIDE_GAP  # right arrow's x
        if right_ax + ARROW_SZ <= sw - 4:
            self._right_arrow_win = self._make_arrow_btn(
                "right", self._groups[next_idx], right_ax, ay)
            panel_x = right_ax + ARROW_SZ + SIDE_GAP
            vis_w = min(SIDE_PEEK_W, sw - panel_x - 4)
            if vis_w >= SIDE_MIN_AVAIL:
                self._right_panel = self._make_side_panel(
                    self._groups[next_idx], "right",
                    panel_x, side_y, vis_w, side_h)

    def _make_side_panel(self, group: dict, side: str,
                         px: int, py: int, vis_w: int, wh: int) -> tk.Toplevel:
        """Smaller dim preview for an adjacent group. No outline."""
        t   = self._t
        sw  = self.mgr.root.winfo_screenwidth()

        win = tk.Toplevel(self.mgr.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.72)
        win.configure(bg=t.hdr)
        win.geometry(f"{vis_w}x{wh}+{px}+{py}")

        cv = tk.Canvas(win, bg=t.hdr, highlightthickness=0, width=vis_w, height=wh)
        cv.pack(fill="both", expand=True)

        # Body — no outline
        cv.create_rectangle(0, 0, vis_w, wh, fill=t.hdr, outline="")

        # Header strip
        cv.create_rectangle(0, 0, vis_w, HDR_H_OV, fill=t.bg, outline="")
        cv.create_line(0, HDR_H_OV, vis_w, HDR_H_OV, fill=t.border, width=1)
        cv.create_text(vis_w // 2, HDR_H_OV // 2,
                       text=group["name"],
                       font=("Segoe UI", 10, "bold"), fill=t.txt,
                       anchor="center", width=vis_w - 12)

        # Tiles — standard grid, canvas clips naturally at vis_w
        apps    = group.get("apps", [])
        n_apps  = len(apps)
        max_fit = max(1, (sw - PANEL_P * 2) // (TILE_W + GAP))
        cols    = min(n_apps, max_fit) if n_apps > 0 else 1
        for i, app in enumerate(apps):
            col = i % cols
            row = i // cols
            tx  = PANEL_P + col * (TILE_W + GAP)
            ty  = HDR_H_OV + PANEL_P + row * (TILE_H + GAP)
            if tx >= vis_w:
                break
            cx     = tx + TILE_W // 2
            icon_y = ty + TILE_PAD + ICON_SZ // 2 + 4
            cv.create_rectangle(tx, ty, tx + TILE_W, ty + TILE_H,
                                 fill=t.btn, outline=t.border)
            photo = get_icon(app["path"], ICON_SZ)
            if photo:
                self._side_refs.append(photo)
                cv.create_image(cx, icon_y, image=photo, anchor="center")
            else:
                cv.create_rectangle(cx - 24, icon_y - 24, cx + 24, icon_y + 24,
                                     fill=t.accent, outline="")
                cv.create_text(cx, icon_y,
                               text=(app["name"][0].upper() if app["name"] else "?"),
                               font=("Segoe UI", 18, "bold"), fill="white", anchor="center")
            cv.create_text(cx, ty + TILE_H - 18,
                           text=clip(app["name"], 12),
                           font=("Segoe UI", 9), fill=t.txt2,
                           anchor="center", width=TILE_W - 8)

        # Gradient fade at the outer edge — blends panel colour → black so
        # the panel dissolves naturally into the dark backdrop instead of hard-cutting.
        rh, gh, bh = _hex(t.hdr)
        fade = min(FADE_W, vis_w // 2)
        for i in range(fade):
            frac = i / fade          # 0 = outer edge (black), 1 = inner (full colour)
            x0   = i if side == "left" else vis_w - fade + i
            r    = int(frac * rh)
            g_   = int(frac * gh)
            b_   = int(frac * bh)
            cv.create_rectangle(x0, 0, x0 + 1, wh,
                                fill=f"#{r:02x}{g_:02x}{b_:02x}", outline="")

        cv.bind("<Button-1>", lambda e, g=group, d=side: self._navigate_to(g, d))
        cv.bind("<Enter>",    lambda e: cv.config(cursor="hand2"))
        cv.bind("<Leave>",    lambda e: cv.config(cursor="arrow"))
        win.lift(self.bg)
        return win

    def _make_arrow_btn(self, side: str, group: dict,
                        bx: int, by: int) -> tk.Toplevel:
        t   = self._t
        win = tk.Toplevel(self.mgr.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=CHROMA)
        win.attributes("-transparentcolor", CHROMA)
        win.geometry(f"{ARROW_SZ}x{ARROW_SZ}+{bx}+{by}")
        cv = tk.Canvas(win, bg=CHROMA, highlightthickness=0,
                       width=ARROW_SZ, height=ARROW_SZ)
        cv.pack()
        r  = ARROW_SZ // 2 - 2
        c  = ARROW_SZ // 2
        cv.create_oval(c - r, c - r, c + r, c + r, fill=t.accent, outline="")
        cv.create_text(c, c, text="◀" if side == "left" else "▶",
                       font=("Segoe UI", 15, "bold"), fill="white", anchor="center")
        cv.bind("<Button-1>", lambda e, g=group, d=side: self._navigate_to(g, d))
        cv.bind("<Enter>",    lambda e: cv.config(cursor="hand2"))
        cv.bind("<Leave>",    lambda e: cv.config(cursor="arrow"))
        win.lift(self.bg)
        return win

    # ── Carousel navigation ─────────────────────────────────

    def _navigate_to(self, group: dict, direction: str = "right") -> None:
        if self._animating:
            return
        self._animating = True

        # Hand off the backdrop so it stays visible across the transition
        self.mgr._bg_handoff    = self.bg
        self.mgr._focus_carousel = True
        self.bg = None   # prevents close() from destroying it

        # Hide side panels and arrow buttons immediately
        for p in [self._left_panel, self._right_panel,
                  self._left_arrow_win, self._right_arrow_win]:
            if p:
                try: p.withdraw()
                except Exception: pass

        # Compute the new group's natural panel geometry
        sw   = self.mgr.root.winfo_screenwidth()
        sh   = self.mgr.root.winfo_screenheight()
        apps = group.get("apps", [])
        n    = len(apps)
        mf   = max(1, (sw - PANEL_P * 2) // (TILE_W + GAP))
        cols = min(n, mf) if n > 0 else 1
        rows = max(1, -(-n // cols)) if n > 0 else 1
        nww  = PANEL_P * 2 + cols * (TILE_W + GAP) - GAP
        nwh  = HDR_H_OV + PANEL_P * 2 + rows * (TILE_H + GAP) - GAP + 28
        nwx  = (sw - nww) // 2
        nwy  = (sh - nwh) // 2

        # Build the transition window (static copy of new group content)
        trans = tk.Toplevel(self.mgr.root)
        trans.overrideredirect(True)
        trans.attributes("-topmost", True)
        trans.configure(bg=self._t.bg)
        tcv = tk.Canvas(trans, bg=self._t.bg, highlightthickness=0,
                         width=nww, height=nwh)
        tcv.pack(fill="both", expand=True)
        self._render_group_to(tcv, group, nww, nwh, sw)

        # Travel distance = width of the larger panel + a small gap.
        # This gives a tight "card swap" feel rather than a full-screen fly-across.
        travel = max(self._ww, nww) + 80

        # New panel starts just off the edge in the direction of travel
        t_start_x = nwx + travel if direction == "right" else nwx - travel
        trans.geometry(f"{nww}x{nwh}+{t_start_x}+{nwy}")
        try: trans.lift(self.mgr._bg_handoff)
        except Exception: pass

        self._do_carousel(group, direction, trans, nwx, nwy, t_start_x, travel)

    def _render_group_to(self, cv: tk.Canvas,
                          group: dict, ww: int, wh: int, sw: int) -> None:
        """Draw focus-overlay content for *group* onto an arbitrary canvas."""
        t    = self._t
        apps = group.get("apps", [])
        n    = len(apps)
        mf   = max(1, (sw - PANEL_P * 2) // (TILE_W + GAP))
        cols = min(n, mf) if n > 0 else 1
        refs: list = []

        cv.create_rectangle(0, 0, ww, wh, fill=t.bg, outline=t.border)
        cv.create_rectangle(0, 0, ww, HDR_H_OV, fill=t.hdr, outline="")
        cv.create_line(0, HDR_H_OV, ww, HDR_H_OV, fill=t.border, width=1)
        cv.create_text(ww // 2, HDR_H_OV // 2,
                       text=group["name"],
                       font=("Segoe UI", 13, "bold"), fill=t.txt, anchor="center")

        for i, app in enumerate(apps):
            col    = i % cols
            row    = i // cols
            tx     = PANEL_P + col * (TILE_W + GAP)
            ty     = HDR_H_OV + PANEL_P + row * (TILE_H + GAP)
            cx_t   = tx + TILE_W // 2
            icon_y = ty + TILE_PAD + ICON_SZ // 2 + 4
            cv.create_rectangle(tx, ty, tx + TILE_W, ty + TILE_H,
                                 fill=t.btn, outline=t.border)
            photo = get_icon(app["path"], ICON_SZ)
            if photo:
                refs.append(photo)
                cv.create_image(cx_t, icon_y, image=photo, anchor="center")
            else:
                cv.create_rectangle(cx_t - 24, icon_y - 24,
                                     cx_t + 24, icon_y + 24,
                                     fill=t.accent, outline="")
                cv.create_text(cx_t, icon_y,
                               text=(app["name"][0].upper() if app["name"] else "?"),
                               font=("Segoe UI", 18, "bold"),
                               fill="white", anchor="center")
            cv.create_text(cx_t, ty + TILE_H - 18,
                           text=clip(app["name"], 12),
                           font=("Segoe UI", 9), fill=t.txt2,
                           anchor="center", width=TILE_W - 8)

        cv._img_refs = refs   # prevent GC

    def _do_carousel(self, target: dict, direction: str,
                     trans: tk.Toplevel, nwx: int, nwy: int,
                     t_start_x: int, travel: int, step: int = 0) -> None:
        """
        Swap two panels: old one slides out, new one slides in.
        Both travel `travel` pixels (≈ panel width) — tight card-swap feel.
        """
        if step >= CAR_STEPS:
            # Snap old panel to its exit position, new to its final position
            old_end = self._wx - travel if direction == "right" else self._wx + travel
            try: self.win.geometry(f"+{old_end}+{self._wy}")
            except Exception: pass
            try: trans.geometry(f"+{nwx}+{nwy}")
            except Exception: pass

            # Clean up the old overlay (bg already handed off, won't be destroyed)
            old_win   = self.win
            old_parts = [self._left_panel, self._right_panel,
                         self._left_arrow_win, self._right_arrow_win]
            self._left_panel = self._right_panel = None
            self._left_arrow_win = self._right_arrow_win = None

            # Open new proper overlay (backdrop reused via handoff)
            self.mgr.focus = None
            self.mgr.open_focus(target)

            # Ensure new overlay is on top, then destroy transition window
            try: self.mgr.focus.win.lift()
            except Exception: pass
            try: trans.destroy()
            except Exception: pass

            # Destroy old windows
            try: old_win.destroy()
            except Exception: pass
            for p in old_parts:
                if p:
                    try: p.destroy()
                    except Exception: pass
            return

        t_    = step / CAR_STEPS
        ease  = t_ * t_ * (3 - 2 * t_)   # smooth-step: ease-in-out

        # Old panel exits: right-nav → slides left, left-nav → slides right
        old_x = int(self._wx + ease * (-travel if direction == "right" else travel))
        # New panel enters from the opposite side
        new_x = int(t_start_x + ease * (nwx - t_start_x))

        try:
            self.win.geometry(f"+{old_x}+{self._wy}")
        except Exception:
            try: trans.destroy()
            except Exception: pass
            self.mgr.open_focus(target)
            return

        try: trans.geometry(f"+{new_x}+{nwy}")
        except Exception: pass

        self.win.after(CAR_MS, lambda: self._do_carousel(
            target, direction, trans, nwx, nwy, t_start_x, travel, step + 1))

    def _nav_dir(self, side: str) -> None:
        n = len(self._groups)
        if n <= 1:
            return
        if side == "left":
            new_idx = (self._group_idx - 1) % n
        else:
            new_idx = (self._group_idx + 1) % n
        self._navigate_to(self._groups[new_idx], side)

    def _apply_theme(self) -> None:
        """Update colours in place — called by the animated theme loop."""
        self._t = config.get_theme(self.mgr.data, self.group.get("theme_override"))
        # Tile cache holds PIL images coloured with the old theme — must clear
        # so tiles re-render with new bg/border/accent colours (including hover).
        self._tile_cache.clear()
        try:
            self.win.configure(bg=self._t.bg)
            self.cv.configure(bg=self._t.bg)
            self._render(self._hov)
        except Exception:
            pass

    def close(self) -> None:
        for panel in [self._left_panel, self._right_panel,
                      self._left_arrow_win, self._right_arrow_win]:
            if panel:
                try: panel.destroy()
                except: pass
        self._left_panel      = None
        self._right_panel     = None
        self._left_arrow_win  = None
        self._right_arrow_win = None
        try: self.bg.destroy()
        except: pass
        try: self.win.destroy()
        except: pass
        self.mgr.focus = None