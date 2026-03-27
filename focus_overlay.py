"""
focus_overlay.py — Full-screen app launcher overlay.
Opened by double-clicking a group widget header.
PIL-rendered tiles with rounded corners, hover accent borders, clean layout.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from theme import HDR_H, PAD
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

        # Dark backdrop
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

    # ── Fade ───────────────────────────────────────────────

    def _fade(self, cur: float, target: float = 0.6) -> None:
        cur = round(min(target, cur + 0.06), 3)
        try: self.bg.attributes("-alpha", cur)
        except: return
        if cur < target:
            self.bg.after(12, lambda: self._fade(cur, target))

    def _bg_click(self, e) -> None:
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
        try: self.bg.destroy()
        except: pass
        try: self.win.destroy()
        except: pass
        self.mgr.focus = None