"""
base_widget.py — Universal base class for ALL desktop widgets.
Handles: drag, resize (all 8 edges/corners), collapse, snap, screen clamping.
Subclasses only need to implement _draw() and optionally override HDR_H, MIN_W, MIN_H.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from theme import CHROMA, SNAP, MARGIN, RSZ, HDR_H
from utils import snap_to_grid, clamp_to_screen, magnetic_snap, push_desktop
import config as _config_mod   # avoid name clash with local vars

if TYPE_CHECKING:
    from manager import Manager

# keep the name 'config' available inside the class methods that use it
import config


def _rounded_rect(canvas: tk.Canvas,
                  x1: int, y1: int, x2: int, y2: int,
                  r: int,
                  fill: str = "", outline: str = "", width: int = 1,
                  corners: str = "all") -> None:
    """
    Draw a crisp rounded rectangle using arcs + lines.
    This is correct tkinter technique — create_polygon(smooth=True) overshoots
    and looks terrible. Arcs give pixel-perfect corners.
    corners: "all" | "top" | "bottom" | "none"
    """
    if r <= 0 or corners == "none":
        canvas.create_rectangle(x1, y1, x2, y2,
                                 fill=fill, outline=outline, width=width)
        return

    r  = min(r, (x2 - x1) // 2, (y2 - y1) // 2)
    tl = r if corners in ("all", "top")    else 0
    tr = r if corners in ("all", "top")    else 0
    bl = r if corners in ("all", "bottom") else 0
    br = r if corners in ("all", "bottom") else 0

    # Filled body — three rectangles that together cover the interior
    if fill:
        # Centre column full height
        canvas.create_rectangle(x1+max(tl,bl), y1, x2-max(tr,br), y2,
                                 fill=fill, outline="")
        # Left strip (between corner arcs)
        if tl or bl:
            canvas.create_rectangle(x1, y1+tl, x1+max(tl,bl), y2-bl,
                                     fill=fill, outline="")
        # Right strip
        if tr or br:
            canvas.create_rectangle(x2-max(tr,br), y1+tr, x2, y2-br,
                                     fill=fill, outline="")

    # Corner arcs (fill only, outline drawn separately)
    _arc_kw = dict(style="pieslice", outline="" if not fill else fill)
    if tl: canvas.create_arc(x1,    y1,    x1+tl*2, y1+tl*2,
                              start=90,  extent=90, fill=fill, **{k:v for k,v in _arc_kw.items() if k!='fill'}, outline="" if not fill else "")
    if tr: canvas.create_arc(x2-tr*2, y1,    x2,      y1+tr*2,
                              start=0,   extent=90, fill=fill, outline="")
    if br: canvas.create_arc(x2-br*2, y2-br*2, x2,    y2,
                              start=270, extent=90, fill=fill, outline="")
    if bl: canvas.create_arc(x1,    y2-bl*2, x1+bl*2, y2,
                              start=180, extent=90, fill=fill, outline="")

    # Outline path (drawn on top so it's crisp)
    if outline and width > 0:
        ow = width
        # Top edge
        canvas.create_line(x1+tl, y1, x2-tr, y1, fill=outline, width=ow)
        # Right edge
        canvas.create_line(x2, y1+tr, x2, y2-br, fill=outline, width=ow)
        # Bottom edge
        canvas.create_line(x2-br, y2, x1+bl, y2, fill=outline, width=ow)
        # Left edge
        canvas.create_line(x1, y2-bl, x1, y1+tl, fill=outline, width=ow)
        # Corner arcs (outline only)
        if tl: canvas.create_arc(x1,      y1,      x1+tl*2, y1+tl*2,
                                  start=90, extent=90, style="arc",
                                  outline=outline, width=ow)
        if tr: canvas.create_arc(x2-tr*2, y1,      x2,      y1+tr*2,
                                  start=0,  extent=90, style="arc",
                                  outline=outline, width=ow)
        if br: canvas.create_arc(x2-br*2, y2-br*2, x2,      y2,
                                  start=270,extent=90, style="arc",
                                  outline=outline, width=ow)
        if bl: canvas.create_arc(x1,      y2-bl*2, x1+bl*2, y2,
                                  start=180,extent=90, style="arc",
                                  outline=outline, width=ow)


class BaseWidget:
    """
    Base for all floating desktop widgets.

    Subclass contract:
        self.mgr        — Manager instance
        self.data_key   — string key into mgr.data (e.g. "stats")
                          OR None for group widgets (use self.group instead)
        MIN_W, MIN_H    — class-level resize limits
        MAX_W, MAX_H    — class-level resize limits

    Subclass must implement:
        _draw()         — (re)draw widget contents on self.cv
        _get_pos_data() — return dict with x, y, w (optional), h (optional), collapsed
        _save_pos()     — persist position/size back to mgr.data
    """

    MIN_W = 160
    MAX_W = 800
    MIN_H = 60
    MAX_H = 700

    # Resize cursor map
    _CURSORS = {
        "se": "size_nw_se", "sw": "size_ne_sw",
        "ne": "size_ne_sw", "nw": "size_nw_se",
        "e":  "size_we",    "w":  "size_we",
        "s":  "size_ns",    "":   "arrow",
    }

    def __init__(self, mgr: "Manager") -> None:
        self.mgr = mgr
        self._collapsed = False
        self._full_h = self.MIN_H    # height when expanded
        self.W = self.MIN_W
        self.H = self.MIN_H

        # Interaction state
        self._mode = ""          # "drag" | "resize" | ""
        self._rsz_edge = ""
        self._px = self._py = 0
        self._moved = False
        self._rsz_x0 = self._rsz_y0 = 0
        self._rsz_w0 = self._rsz_h0 = 0
        self._prev: tk.Toplevel | None = None   # snap preview window

        # Build the window
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.configure(bg=CHROMA)
        self.win.attributes("-transparentcolor", CHROMA)
        self.win.attributes("-topmost", False)

        self.cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)

        # Bind universal interactions
        self.cv.bind("<ButtonPress-1>",   self._on_press)
        self.cv.bind("<B1-Motion>",       self._on_motion)
        self.cv.bind("<ButtonRelease-1>", self._on_release)
        self.cv.bind("<Motion>",          self._on_cursor)

        self.win.after(400, lambda: push_desktop(self.win.winfo_id()))

    # ── Public API ─────────────────────────────────────────

    def place(self, x: int, y: int, w: int | None = None, h: int | None = None,
              collapsed: bool = False) -> None:
        """Set initial position/size. Call after __init__."""
        self.W = w or self.W
        self._full_h = h or self._full_h
        self._collapsed = collapsed
        self.H = HDR_H if collapsed else self._full_h
        self.win.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.cv.config(width=self.W, height=self.H)
        self.redraw()

    def redraw(self) -> None:
        """Full redraw. Calls subclass _draw()."""
        self.cv.delete("all")
        t  = self._theme()
        r  = config.get_corner_radius(self.mgr.data)

        # Background (rounded or flat)
        _rounded_rect(self.cv, 0, 0, self.W, self.H,
                      r, fill=t.bg, outline=t.border, width=1)

        # Header band — clip to top corners only
        if r > 0:
            _rounded_rect(self.cv, 0, 0, self.W, HDR_H,
                          r, fill=t.hdr, outline="",
                          corners="top")
            # Fill the bottom of the header square (no bottom rounding)
            self.cv.create_rectangle(0, r, self.W, HDR_H,
                                     fill=t.hdr, outline="")
        else:
            self.cv.create_rectangle(0, 0, self.W, HDR_H,
                                     fill=t.hdr, outline="")

        self.cv.create_line(0, HDR_H, self.W, HDR_H, fill=t.border, width=1)

        # Collapse button
        arrow = "▶" if self._collapsed else "▼"
        self.cv.create_rectangle(0, 0, HDR_H, HDR_H,
                                 fill="", outline="", tags="collapse_btn")
        self.cv.create_text(HDR_H // 2, HDR_H // 2, text=arrow,
                            font=("Segoe UI", 9), fill=t.txt2, anchor="center",
                            tags="collapse_btn")

        # Resize grip dots — only shown when resize is enabled
        if not self._collapsed and self.mgr.data.get("resize_enabled", True):
            gc = t.border
            for off in (5, 9, 13):
                self.cv.create_line(self.W-off, self.H-1, self.W-1, self.H-off,
                                    fill=gc, width=1)
        self._draw()

    def destroy(self) -> None:
        self._hide_prev()
        try: self.win.withdraw(); self.win.after(50, self.win.destroy)
        except: pass

    # ── Subclass stubs ─────────────────────────────────────

    def _draw(self) -> None:
        """Override in subclass to draw widget body."""
        pass

    def _theme(self):
        """Override to support per-widget theme overrides."""
        import config
        return config.get_theme(self.mgr.data)

    def _get_rect(self) -> tuple[int, int, int, int]:
        """Return current (x, y, w, h)."""
        return (self._win_x(), self._win_y(), self.W, self.H)

    def _win_x(self) -> int:
        """
        Read window X from the geometry string — avoids DWM shadow offset.
        winfo_x() on Windows with overrideredirect adds ~8px per save/reload cycle.
        """
        try:
            g = self.win.geometry()  # e.g. "300x200+150+80"
            return int(g.split("+")[1])
        except Exception:
            return self.win.winfo_x()

    def _win_y(self) -> int:
        """Read window Y from the geometry string — see _win_x."""
        try:
            g = self.win.geometry()
            return int(g.split("+")[2])
        except Exception:
            return self.win.winfo_y()

    def _save_geometry(self) -> None:
        """Override in subclass to persist position."""
        pass

    def _notify_collapse_change(self) -> None:
        """Called after collapse state changes. Override to persist."""
        pass

    # ── Collapse ───────────────────────────────────────────

    def toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._full_h = self.H
            self.H = HDR_H
        else:
            self.H = self._full_h
            # Clamp so expanding never pushes the bottom off screen
            sh = self.win.winfo_screenheight()
            ny = self._win_y()
            if ny + self.H + MARGIN > sh:
                ny = max(MARGIN, sh - self.H - MARGIN)
                self.win.geometry(f"+{self._win_x()}+{ny}")
        self.win.geometry(f"{self.W}x{self.H}")
        self.cv.config(height=self.H)
        self.redraw()
        self._notify_collapse_change()
        self.mgr.reflow_after_collapse(self)

    # ── Edge detection ─────────────────────────────────────

    def _edge(self, x: int, y: int) -> str:
        """Returns resize edge only when resize_enabled is True in settings."""
        if self._collapsed:
            return ""
        if not self.mgr.data.get("resize_enabled", True):
            return ""
        r = x >= self.W - RSZ;  l = x <= RSZ
        b = y >= self.H - RSZ;  t_zone = HDR_H <= y <= HDR_H + RSZ
        if r and b: return "se"
        if l and b: return "sw"
        if r and t_zone: return "ne"
        if l and t_zone: return "nw"
        if r: return "e"
        if l: return "w"
        if b: return "s"
        return ""

    # ── Input events ───────────────────────────────────────

    def _on_cursor(self, e: tk.Event) -> None:
        edge = self._edge(e.x, e.y)
        if edge:
            self.cv.config(cursor=self._CURSORS.get(edge, "arrow"))
        elif e.y <= HDR_H:
            self.cv.config(cursor="hand2" if e.x <= HDR_H else "fleur")
        else:
            self.cv.config(cursor="arrow")

    def _on_press(self, e: tk.Event) -> None:
        self._px, self._py = e.x, e.y
        self._moved = False
        edge = self._edge(e.x, e.y)
        if edge:
            self._mode = "resize"
            self._rsz_edge = edge
            self._rsz_x0 = self._win_x()
            self._rsz_y0 = self._win_y()
            self._rsz_w0 = self.W
            self._rsz_h0 = self.H
        elif e.y <= HDR_H:
            # Check collapse button — full left square of the header
            if e.x <= HDR_H:
                self._mode = "collapse_click"
            else:
                self._mode = "drag"
        else:
            self._mode = ""
        self._on_press_extra(e)

    def _on_press_extra(self, e: tk.Event) -> None:
        """Hook for subclasses (e.g. GroupWin) to intercept press."""
        pass

    def _on_motion(self, e: tk.Event) -> None:
        dx = e.x - self._px; dy = e.y - self._py
        if abs(dx) < 2 and abs(dy) < 2: return
        self._moved = True

        if self._mode == "drag":
            nx = self._win_x() + dx
            ny = self._win_y() + dy
            self.win.geometry(f"+{nx}+{ny}")
            self._show_prev(nx, ny)

        elif self._mode == "resize":
            self._do_resize(e)

        self._on_motion_extra(e)

    def _on_motion_extra(self, e: tk.Event) -> None:
        pass

    def _do_resize(self, e: tk.Event) -> None:
        """Universal resize — works for all widgets."""
        edge = self._rsz_edge
        mx = e.x_root; my = e.y_root
        x0, y0, w0, h0 = (self._rsz_x0, self._rsz_y0,
                           self._rsz_w0, self._rsz_h0)

        if "e" in edge:
            nw = max(self.MIN_W, min(self.MAX_W, mx - x0))
        elif "w" in edge:
            nw = max(self.MIN_W, min(self.MAX_W, x0 + w0 - mx))
        else:
            nw = self.W

        if "s" in edge:
            nh = max(self.MIN_H, min(self.MAX_H, my - y0))
        else:
            nh = self.H

        self.W = nw
        if not self._collapsed:
            self.H = nh
            self._full_h = nh

        self.win.geometry(f"{nw}x{self.H}")
        self.cv.config(width=nw, height=self.H)

        if "w" in edge:
            self.win.geometry(f"+{x0 + w0 - nw}+{self._win_y()}")

        self._on_resize_extra(nw, nh)
        self.redraw()

    def _on_resize_extra(self, nw: int, nh: int) -> None:
        """Hook for subclasses that need to update their layout on resize."""
        pass

    def _on_release(self, e: tk.Event) -> None:
        self._hide_prev()

        if self._mode == "collapse_click" and not self._moved:
            self.toggle_collapse()

        elif self._mode == "drag" and self._moved:
            nx, ny = self._win_x(), self._win_y()
            sw = self.win.winfo_screenwidth()
            sh = self.win.winfo_screenheight()
            nx, ny = clamp_to_screen(nx, ny, self.W, self.H, sw, sh)
            # Magnetic snap to other widgets
            others = self.mgr.all_rects(exclude=self)
            nx, ny = magnetic_snap(nx, ny, self.W, self.H, others)
            # No overlap
            nx, ny = find_non_overlapping_release(nx, ny, self.W, self.H, others, sw, sh)
            self.win.geometry(f"+{nx}+{ny}")
            self._save_geometry()

        elif self._mode == "resize" and self._moved:
            nx, ny = self._win_x(), self._win_y()
            if "w" in self._rsz_edge:
                # window moved — update stored position
                pass
            self._save_geometry()

        self._on_release_extra(e)
        self._mode = ""
        self._moved = False

    def _on_release_extra(self, e: tk.Event) -> None:
        pass

    # ── Snap preview ───────────────────────────────────────

    def _show_prev(self, nx: int, ny: int) -> None:
        others = self.mgr.all_rects(exclude=self)
        sx, sy = magnetic_snap(nx, ny, self.W, self.H, others)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        sx, sy = clamp_to_screen(sx, sy, self.W, self.H, sw, sh)

        # Ghost preview window
        if self._prev:
            try: self._prev.geometry(f"{self.W}x{self.H}+{sx}+{sy}")
            except: pass
        else:
            p = tk.Toplevel(self.mgr.root)
            p.overrideredirect(True)
            p.attributes("-alpha", 0.18)
            p.configure(bg=self._theme().accent)
            p.geometry(f"{self.W}x{self.H}+{sx}+{sy}")
            self._prev = p

        self._update_guides(sx, sy, others, sw, sh)

    def _update_guides(self, sx: int, sy: int,
                       others: list, sw: int, sh: int) -> None:
        """Draw dashed alignment guide lines when snapped to another widget's edge."""
        t = self._theme()
        THRESH = 6

        guides = []
        for ox, oy, ow, oh in others:
            if abs(sx - ox) <= THRESH:
                guides.append(("v", ox))
            if abs(sx - (ox + ow - self.W)) <= THRESH:
                guides.append(("v", ox + ow))
            if abs(sx - (ox + ow + MARGIN)) <= THRESH:
                guides.append(("v", ox + ow))
            if abs(sx + self.W + MARGIN - ox) <= THRESH:
                guides.append(("v", ox))
            if abs(sy - oy) <= THRESH:
                guides.append(("h", oy))
            if abs(sy - (oy + oh - self.H)) <= THRESH:
                guides.append(("h", oy + oh))
            if abs(sy - (oy + oh + MARGIN)) <= THRESH:
                guides.append(("h", oy + oh))
            if abs(sy + self.H + MARGIN - oy) <= THRESH:
                guides.append(("h", oy))

        if not guides:
            self._hide_guides()
            return

        if not hasattr(self, "_guide_win") or self._guide_win is None:
            from theme import CHROMA
            g = tk.Toplevel(self.mgr.root)
            g.overrideredirect(True)
            g.attributes("-transparentcolor", CHROMA)
            g.attributes("-alpha", 0.85)
            g.configure(bg=CHROMA)
            g.geometry(f"{sw}x{sh}+0+0")
            g.attributes("-topmost", True)
            gcv = tk.Canvas(g, bg=CHROMA, highlightthickness=0,
                            width=sw, height=sh)
            gcv.pack()
            self._guide_win = g
            self._guide_cv  = gcv
        else:
            try:
                self._guide_win.geometry(f"{sw}x{sh}+0+0")
            except Exception:
                self._guide_win = None
                return

        self._guide_cv.delete("all")
        seen = set()
        for kind, pos in guides:
            if (kind, pos) in seen:
                continue
            seen.add((kind, pos))
            if kind == "v":
                self._guide_cv.create_line(pos, 0, pos, sh,
                    fill=t.accent, width=1, dash=(6, 4))
            else:
                self._guide_cv.create_line(0, pos, sw, pos,
                    fill=t.accent, width=1, dash=(6, 4))

    def _hide_guides(self) -> None:
        if hasattr(self, "_guide_win") and self._guide_win:
            try: self._guide_win.destroy()
            except: pass
            self._guide_win = None
            self._guide_cv  = None

    def _hide_prev(self) -> None:
        if self._prev:
            try: self._prev.destroy()
            except: pass
            self._prev = None
        self._hide_guides()


def find_non_overlapping_release(x, y, w, h, others, sw, sh):
    from utils import find_non_overlapping
    return find_non_overlapping(x, y, w, h, others, sw, sh)