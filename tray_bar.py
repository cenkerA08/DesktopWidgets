"""
tray_bar.py — Floating bottom-right bar with + and gear buttons.
Both buttons are canvas-drawn so there are zero white flashes on click.
"""
from __future__ import annotations
import tkinter as tk
import math
from typing import TYPE_CHECKING
from utils import push_desktop
import config

if TYPE_CHECKING:
    from manager import Manager


# ── Icon drawing helpers ────────────────────────────────────

def _draw_gear(canvas: tk.Canvas, cx: float, cy: float,
               r_out: float, r_in: float, teeth: int, color: str) -> None:
    """Draw a crisp polygon gear, with a hollow hub."""
    tooth_half  = math.pi / teeth * 0.42
    valley_half = math.pi / teeth * 0.58
    points = []
    for i in range(teeth):
        base = 2 * math.pi * i / teeth
        for da, r in [(-valley_half, r_in), (-tooth_half, r_out),
                      ( tooth_half, r_out), ( valley_half, r_in)]:
            a = base + da
            points.extend([cx + r * math.cos(a), cy + r * math.sin(a)])
    canvas.create_polygon(points, fill=color, outline="", smooth=False, tags="icon")
    hub = r_in * 0.42
    canvas.create_oval(cx - hub, cy - hub, cx + hub, cy + hub,
                       fill=canvas.cget("bg"), outline="", tags="icon")


def _draw_plus(canvas: tk.Canvas, cx: float, cy: float,
               size: float, thickness: float, color: str) -> None:
    """Draw a clean + cross."""
    h = size / 2
    t = thickness / 2
    # Horizontal bar
    canvas.create_rectangle(cx - h, cy - t, cx + h, cy + t,
                            fill=color, outline="", tags="icon")
    # Vertical bar
    canvas.create_rectangle(cx - t, cy - h, cx + t, cy + h,
                            fill=color, outline="", tags="icon")


# ── Reusable canvas button ──────────────────────────────────

class _CanvasBtn:
    """A canvas that looks and acts like a flat button — no system flash."""

    def __init__(self, parent, w, h, bg_normal, bg_hover, command, cursor="hand2"):
        self.bg_normal = bg_normal
        self.bg_hover  = bg_hover
        self.command   = command
        self.cv = tk.Canvas(parent, width=w, height=h,
                            bg=bg_normal, highlightthickness=0, cursor=cursor)
        self.cv.bind("<Enter>",           self._enter)
        self.cv.bind("<Leave>",           self._leave)
        self.cv.bind("<ButtonRelease-1>", self._click)

    def _enter(self, e=None):
        self.cv.configure(bg=self.bg_hover)
        self._redraw_icon()

    def _leave(self, e=None):
        self.cv.configure(bg=self.bg_normal)
        self._redraw_icon()

    def _click(self, e=None):
        self.command()

    def _redraw_icon(self):
        pass  # override in subclass

    def grid(self, **kw):
        self.cv.grid(**kw)

    def configure(self, **kw):
        if "bg_normal" in kw: self.bg_normal = kw.pop("bg_normal")
        if "bg_hover"  in kw: self.bg_hover  = kw.pop("bg_hover")
        self.cv.configure(**kw)
        self._redraw_icon()


class _PlusBtn(_CanvasBtn):
    def __init__(self, parent, w, h, fg, bg_normal, bg_hover, command):
        self.fg = fg
        super().__init__(parent, w, h, bg_normal, bg_hover, command)
        self._redraw_icon()

    def _redraw_icon(self):
        self.cv.delete("icon")
        cx, cy = int(self.cv["width"]) / 2, int(self.cv["height"]) / 2
        _draw_plus(self.cv, cx, cy, size=13, thickness=2.2, color=self.fg)


class _GearBtn(_CanvasBtn):
    def __init__(self, parent, w, h, fg, bg_normal, bg_hover, command):
        self.fg = fg
        super().__init__(parent, w, h, bg_normal, bg_hover, command)
        self._redraw_icon()

    def _redraw_icon(self):
        self.cv.delete("icon")
        cx, cy = int(self.cv["width"]) / 2, int(self.cv["height"]) / 2
        _draw_gear(self.cv, cx, cy, r_out=8.5, r_in=5.8, teeth=8, color=self.fg)


# ── TrayBar ─────────────────────────────────────────────────

class TrayBar:
    W = 80
    H = 34

    def __init__(self, mgr: "Manager") -> None:
        self.mgr = mgr
        t = config.get_theme(mgr.data)
        sw = mgr.root.winfo_screenwidth()
        sh = mgr.root.winfo_screenheight()
        bx = sw - self.W - 58
        by = sh - self.H - 44

        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.configure(bg=t.border)   # border colour = 1px gap between halves
        self.win.geometry(f"{self.W}x{self.H}+{bx}+{by}")
        self.win.columnconfigure(0, weight=1)
        self.win.columnconfigure(1, weight=1)

        half = self.W // 2

        self._plus = _PlusBtn(
            self.win, w=half - 1, h=self.H,
            fg=t.txt, bg_normal=t.hdr, bg_hover=t.btn_h,
            command=mgr.show_add_picker)
        self._plus.grid(row=0, column=0, sticky="nsew")

        self._gear = _GearBtn(
            self.win, w=half - 1, h=self.H,
            fg=t.txt2, bg_normal=t.hdr, bg_hover=t.btn_h,
            command=mgr.open_settings)
        self._gear.grid(row=0, column=1, sticky="nsew")

        self.win.after(500, lambda: push_desktop(self.win.winfo_id()))

    def redraw(self) -> None:
        t = config.get_theme(self.mgr.data)
        self.win.configure(bg=t.border)
        self._plus.bg_normal = t.hdr;  self._plus.bg_hover = t.btn_h
        self._plus.fg = t.txt
        self._plus.configure(bg=t.hdr)
        self._gear.bg_normal = t.hdr;  self._gear.bg_hover = t.btn_h
        self._gear.fg = t.txt2
        self._gear.configure(bg=t.hdr)

    def destroy(self) -> None:
        try: self.win.destroy()
        except: pass