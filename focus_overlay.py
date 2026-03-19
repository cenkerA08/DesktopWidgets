"""
focus_overlay.py — Full-screen app launcher overlay.
Opened by double-clicking a group widget header.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from theme import HDR_H, PAD
from utils import get_icon, clip, launch_app
import config

if TYPE_CHECKING:
    from manager import Manager


class FocusOverlay:
    def __init__(self, mgr: "Manager", group: dict) -> None:
        self.mgr   = mgr
        self.group = group
        self._hov: int | None = None
        self._spots: list[dict] = []
        self._refs:  list = []

        t  = config.get_theme(mgr.data, group.get("theme_override"))
        sw = mgr.root.winfo_screenwidth()
        sh = mgr.root.winfo_screenheight()
        apps = group["apps"]; n = max(len(apps), 1)
        cols = max(3, min(8, n)); rows = max(1, -(-n // cols))
        ww   = cols * 110 + PAD * 2
        wh   = HDR_H + rows * 110 + PAD * 2
        self._wx = (sw - ww) // 2; self._wy = (sh - wh) // 2
        self._ww = ww; self._wh = wh; self._t = t

        # Dark backdrop — created FIRST so it stays BELOW the panel
        self.bg = tk.Toplevel(mgr.root)
        self.bg.overrideredirect(True)
        self.bg.attributes("-topmost", False)
        self.bg.attributes("-alpha", 0.0)
        self.bg.configure(bg="#000000")
        self.bg.geometry(f"{sw}x{sh}+0+0")
        self.bg.bind("<Button-1>", self._bg_click)
        self._fade(0.0, 0.55)

        # Main panel — created AFTER so it's on top of the backdrop
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", False)
        self.win.configure(bg=t.bg)
        self.win.geometry(f"{ww}x{wh}+{self._wx}+{self._wy}")

        self.cv = tk.Canvas(self.win, bg=t.bg, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        # Bind all interactions to the canvas
        self.cv.bind("<Motion>",          self._hover)
        self.cv.bind("<Leave>",           self._leave)
        self.cv.bind("<Button-1>",        self._click)
        self.cv.bind("<Double-Button-1>", self._dbl)
        self.cv.bind("<Button-3>",        self._right)
        self.win.bind("<Escape>",         lambda e: self.close())

        # Raise panel above backdrop and take focus
        self.bg.update_idletasks()
        self.win.lift(self.bg)
        self.win.focus_force()

        self._render()

    def _fade(self, cur: float, target: float = 0.55) -> None:
        cur = round(min(target, cur + 0.05), 3)
        try: self.bg.attributes("-alpha", cur)
        except: return
        if cur < target:
            self.bg.after(14, lambda: self._fade(cur, target))

    def _bg_click(self, e) -> None:
        """Close only when clicking outside the panel."""
        try:
            wx = self.win.winfo_x(); wy = self.win.winfo_y()
            ww = self.win.winfo_width(); wh = self.win.winfo_height()
            if not (wx <= e.x_root <= wx + ww and wy <= e.y_root <= wy + wh):
                self.close()
        except Exception:
            self.close()

    def _render(self, hov: int | None = None) -> None:
        self.cv.delete("all"); self._spots.clear(); self._refs.clear()
        t = self._t; apps = self.group["apps"]
        n = max(len(apps), 1); cols = max(3, min(8, n))
        ww, wh = self._ww, self._wh

        # Header
        self.cv.create_rectangle(0, 0, ww, HDR_H, fill=t.hdr, outline="")
        self.cv.create_line(0, HDR_H, ww, HDR_H, fill=t.border, width=1)
        self.cv.create_rectangle(0, 0, ww, wh, fill="", outline=t.border, width=1)
        self.cv.create_text(ww // 2, HDR_H // 2, text=self.group["name"],
            font=("Segoe UI", 12, "bold"), fill=t.txt, anchor="center")
        # Esc hint
        self.cv.create_text(PAD, HDR_H // 2, text="Esc to close",
            font=("Segoe UI", 8), fill=t.txt2, anchor="w")
        # Close button — large clickable area in top-right
        cbx = ww - 20; cby = HDR_H // 2; cbr = 14
        close_hov = (hov == -1) if hasattr(self, "_hov") and self._hov == -1 else False
        self.cv.create_oval(cbx-cbr, cby-cbr, cbx+cbr, cby+cbr,
            fill="#5a1a1a" if close_hov else "#2e2020", outline="#6a2a2a")
        self.cv.create_text(cbx, cby, text="✕",
            font=("Segoe UI", 11, "bold"),
            fill="#ff5555" if close_hov else "#cc4444", anchor="center",
            tags="close_btn")
        self._spots.append({
            "x1": cbx-cbr-4, "y1": cby-cbr-4,
            "x2": cbx+cbr+4, "y2": cby+cbr+4,
            "close": True,
        })

        if not apps:
            self.cv.create_text(ww // 2, wh // 2,
                text="No apps.\nAdd via the + button.",
                font=("Segoe UI", 11), fill=t.txt2,
                anchor="center", justify="center")
            return

        for i, app in enumerate(apps):
            col = i % cols; row = i // cols
            ax = PAD + col * 110; ay = HDR_H + PAD + row * 110; cx = ax + 55

            # Hover highlight
            if i == hov:
                self.cv.create_rectangle(ax+3, ay+3, ax+107, ay+107,
                    fill=t.hov, outline=t.accent, width=1)

            photo = get_icon(app["path"], 64)
            if photo:
                self._refs.append(photo)
                self.cv.create_image(cx, ay + 40, image=photo, anchor="center")
            else:
                self.cv.create_rectangle(cx-32, ay+8, cx+32, ay+72,
                    fill=t.accent, outline="")
                self.cv.create_text(cx, ay+40,
                    text=app["name"][0].upper() if app["name"] else "?",
                    font=("Segoe UI", 22, "bold"), fill="white")

            self.cv.create_text(cx, ay+80, text=clip(app["name"], 14),
                font=("Segoe UI", 9), fill=t.txt3, anchor="n", width=106)

            p, nm, gid = app["path"], app["name"], self.group["id"]
            self._spots.append({
                "x1": ax, "y1": ay, "x2": ax+110, "y2": ay+110, "idx": i,
                "dbl":   lambda pa=p: (launch_app(pa), self.close()),
                "right": lambda pa=p, na=nm, ga=gid: self.mgr.app_ctx(pa, na, ga),
            })

    def _hit(self, x, y) -> dict | None:
        for s in self._spots:
            if s["x1"] <= x <= s["x2"] and s["y1"] <= y <= s["y2"]: return s
        return None

    def _hover(self, e) -> None:
        h = self._hit(e.x, e.y)
        # -1 = close button, None = nothing, int = app icon
        if h and h.get("close"):
            idx = -1
        elif h and "idx" in h:
            idx = h["idx"]
        else:
            idx = None
        if idx != self._hov:
            self._hov = idx
            self._render(hov=idx)
        self.cv.config(cursor="hand2" if h else "arrow")

    def _leave(self, e) -> None:
        if self._hov is not None:
            self._hov = None
            self._render()

    def _click(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and h.get("close"):
            self.close()

    def _dbl(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and "dbl" in h:
            h["dbl"]()
        elif e.y <= HDR_H:
            self.close()

    def _right(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and "right" in h:
            h["right"]()

    def close(self) -> None:
        try: self.bg.destroy()
        except: pass
        try: self.win.destroy()
        except: pass
        self.mgr.focus = None