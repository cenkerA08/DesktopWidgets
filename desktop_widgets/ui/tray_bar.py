"""
tray_bar.py — Floating bottom-right bar with + and gear buttons.
Both buttons are canvas-drawn so there are zero white flashes on click.
"""
from __future__ import annotations
import tkinter as tk
import math
from typing import TYPE_CHECKING
from desktop_widgets.utils import push_desktop
from desktop_widgets.widgets.base_widget import _rounded_rect
import desktop_widgets.config as config

if TYPE_CHECKING:
    from desktop_widgets.manager import Manager


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
    W = 112
    H = 48

    def __init__(self, mgr: "Manager") -> None:
        self.mgr = mgr
        t = config.get_theme(mgr.data)

        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.configure(bg='#010203')
        self.win.attributes('-transparentcolor', '#010203')
        self.reposition()
        self.cv = tk.Canvas(self.win, width=self.W, height=self.H,
                            bg='#010203', highlightthickness=0, cursor='hand2')
        self.cv.pack(fill='both', expand=True)
        self._hover = None
        self.cv.bind('<Motion>', self._motion)
        self.cv.bind('<Leave>', lambda e: self._set_hover(None))
        self.cv.bind('<ButtonRelease-1>', self._click)
        self.redraw()

        self._desktop_job = self.win.after(500, lambda: push_desktop(self.win.winfo_id()))

    def reposition(self) -> None:
        from desktop_widgets.services.screens import area_for, corner_position
        area = area_for(self.mgr.root, 0, 0,
                        self.mgr.root.winfo_screenwidth(), self.mgr.root.winfo_screenheight())
        x, y = corner_position(area, self.W, self.H,
                               self.mgr.data.get("tray_corner", "bottom_right"), margin=32)
        self.win.geometry(f"{self.W}x{self.H}+{x}+{y}")

    def _set_hover(self, value):
        if value != self._hover:
            self._hover = value
            self.redraw()

    def _motion(self, event):
        self._set_hover('add' if event.x < self.W // 2 else 'settings')

    def _click(self, event):
        if event.x < self.W // 2:
            self.mgr.show_add_picker()
        else:
            self.mgr.open_settings()

    def redraw(self) -> None:
        t = config.get_theme(self.mgr.data)
        self.cv.delete('all')
        _rounded_rect(self.cv, 1, 1, self.W-1, self.H-1, 20,
                      fill=t.hdr, outline=t.border, width=1)
        if self._hover:
            x1, x2 = (5, self.W//2-2) if self._hover == 'add' else (self.W//2+2, self.W-5)
            _rounded_rect(self.cv, x1, 5, x2, self.H-5, 15, fill=t.btn_h)
        self.cv.create_line(self.W//2, 12, self.W//2, self.H-12, fill=t.border)
        self.cv.create_oval(14, 9, 44, 39, fill=t.accent, outline='')
        accent = t.bg if t.accent != t.bg else t.txt
        _draw_plus(self.cv, 29, 24, 13, 2.5, accent)
        _draw_gear(self.cv, 83, 24, 9, 6.2, 8, t.txt)

    def destroy(self) -> None:
        try: self.win.after_cancel(self._desktop_job)
        except tk.TclError: pass
        try: self.win.destroy()
        except: pass
