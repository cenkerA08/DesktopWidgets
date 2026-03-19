"""
group_widget.py — App folder widget.
Displays a grid of app icons. Supports drag-drop, reorder, collapse.
"""
from __future__ import annotations
import os, tkinter as tk
from tkinter import filedialog
from typing import TYPE_CHECKING

from theme import CHROMA, HDR_H, MIN_COLS, MAX_COLS, RSZ
import theme as _th
from base_widget import BaseWidget
from utils import (get_icon, clear_icon_cache, clip, launch_app, ask_string, ask_confirm,
                   resolve_lnk, resolve_url, allow_dnd_from_explorer, setup_wmdrop)
import config

if TYPE_CHECKING:
    from manager import Manager

try:
    from tkinterdnd2 import DND_FILES
    DND_OK = True
except ImportError:
    DND_OK = False


class GroupWidget(BaseWidget):
    MIN_W = 80
    MIN_H = HDR_H + _th.CELL_H + _th.PAD * 2

    def __init__(self, mgr: "Manager", group: dict) -> None:
        self.group = group
        self._spots: list[dict] = []
        self._refs:  list = []
        self._hov:   int | None = None
        self._drag_idx:   int | None = None
        self._drag_over:  int | None = None
        self._drag_cross: bool = False   # True while dragging outside this widget
        self._last_collapse_ms: int = 0  # timestamp of last collapse toggle

        super().__init__(mgr)

        # Drag-and-drop from Explorer
        if DND_OK:
            try:
                self.win.drop_target_register(DND_FILES)
                self.win.dnd_bind("<<Drop>>", self._on_drop)
            except: pass

        # Position from saved data
        self.place(
            x=group.get("x", 60),
            y=group.get("y", 60),
            collapsed=group.get("collapsed", False),
        )

    # ── Sizing ─────────────────────────────────────────────

    @property
    def cols(self) -> int:
        return self.group.get("cols", 5)

    @property
    def _natural_w(self) -> int:
        return self.cols * _th.CELL_W + _th.PAD * 2

    @property
    def _natural_h(self) -> int:
        n = len(self.group["apps"])
        rows = max(1, -(-n // self.cols))
        return HDR_H + rows * _th.CELL_H + _th.PAD * 2

    def place(self, x, y, collapsed=False, **_):
        self.W = self._natural_w
        self._full_h = self._natural_h
        self._collapsed = collapsed
        self.H = HDR_H if collapsed else self._full_h
        self.win.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.cv.config(width=self.W, height=self.H)
        self.redraw()

    def _refresh_size(self) -> None:
        old_h = self.H
        self.W = self._natural_w
        self._full_h = self._natural_h
        if not self._collapsed:
            self.H = self._full_h
        self.win.geometry(f"{self.W}x{self.H}")
        self.cv.config(width=self.W, height=self.H)
        if self.H != old_h:
            self.mgr.reflow_after_resize(self, old_h, self.H)

    # ── Theme ──────────────────────────────────────────────

    def _theme(self):
        return config.get_theme(self.mgr.data, self.group.get("theme_override"))

    # ── Draw ───────────────────────────────────────────────

    def _draw(self) -> None:
        self._spots.clear(); self._refs.clear()
        t = self._theme()
        ww, wh = self.W, self.H
        apps = self.group["apps"]
        gid = self.group["id"]

        # Header title
        self.cv.create_text(ww // 2, HDR_H // 2,
            text=self.group["name"],
            font=("Segoe UI", 11, "bold"), fill=t.txt, anchor="center")

        # + button
        self.cv.create_rectangle(ww - HDR_H, 0, ww, HDR_H,
            fill="", outline="", tags="add_btn")
        self.cv.create_text(ww - HDR_H // 2, HDR_H // 2, text="+",
            font=("Segoe UI", 14, "bold"), fill=t.txt2, anchor="center",
            tags="add_btn")
        self._spots.append({
            "x1": ww - HDR_H, "y1": 0, "x2": ww, "y2": HDR_H,
            "click": lambda: self.mgr.add_app(gid),
        })

        if self._collapsed:
            return

        # Empty hint
        if not apps:
            hint = "Drop .exe / .lnk here" if DND_OK else "Click + to add apps"
            self.cv.create_text(ww // 2, HDR_H + (wh - HDR_H) // 2,
                text=hint, font=("Segoe UI", 9),
                fill=t.txt2, anchor="center", justify="center")

        # Pass 1: cell backgrounds + drag indicators
        for i, app in enumerate(apps):
            col = i % self.cols; row = i // self.cols
            ax = _th.PAD + col * _th.CELL_W; ay = HDR_H + _th.PAD + row * _th.CELL_H
            if i == self._hov and self._drag_idx is None:
                self.cv.create_rectangle(ax+2, ay+2, ax+_th.CELL_W-2, ay+_th.CELL_H-2,
                    fill=t.btn_h, outline=t.accent, width=2)
            if i == self._drag_idx:
                self.cv.create_rectangle(ax+2, ay+2, ax+_th.CELL_W-2, ay+_th.CELL_H-2,
                    fill=t.hov, outline=t.accent, width=2)
            if (i == self._drag_over and self._drag_idx is not None
                    and i != self._drag_idx):
                self.cv.create_line(ax, ay+2, ax, ay+_th.CELL_H-2,
                    fill=t.accent, width=3)

        # Pass 2: icons + labels
        for i, app in enumerate(apps):
            col = i % self.cols; row = i // self.cols
            ax = _th.PAD + col * _th.CELL_W; ay = HDR_H + _th.PAD + row * _th.CELL_H
            cx = ax + _th.CELL_W // 2
            photo = get_icon(app["path"], _th.ICON_SZ)
            if photo:
                self._refs.append(photo)
                self.cv.create_image(cx, ay + _th.ICON_SZ // 2 + 4,
                    image=photo, anchor="center", tags="icon")
            else:
                self.cv.create_rectangle(cx-_th.ICON_SZ//2, ay+4,
                    cx+_th.ICON_SZ//2, ay+4+_th.ICON_SZ, fill=t.accent, outline="",
                    tags="icon")
                self.cv.create_text(cx, ay+4+_th.ICON_SZ//2,
                    text=app["name"][0].upper() if app["name"] else "?",
                    font=("Segoe UI", 18, "bold"), fill="white", tags="icon")
            self.cv.create_text(cx, ay+_th.ICON_SZ+10,
                text=clip(app["name"], 10), font=("Segoe UI", 8),
                fill=t.txt3, anchor="n", width=_th.CELL_W-6, tags="label")
            p, n = app["path"], app["name"]
            self._spots.append({
                "x1": ax, "y1": ay, "x2": ax+_th.CELL_W, "y2": ay+_th.CELL_H, "idx": i,
                "dbl":   lambda pa=p: launch_app(pa),
                "right": lambda pa=p, na=n, ga=gid: self.mgr.app_ctx(pa, na, ga),
            })

        # Cross-widget drag hint strip at bottom of source widget
        if self._drag_cross and self._drag_idx is not None:
            apps_list = self.group["apps"]
            if self._drag_idx < len(apps_list):
                dname = clip(apps_list[self._drag_idx]["name"], 14)
                self.cv.create_rectangle(0, self.H - 20, self.W, self.H,
                    fill=t.hov, outline="")
                self.cv.create_text(self.W // 2, self.H - 10,
                    text=f"↗  Dragging '{dname}' out …",
                    font=("Segoe UI", 7), fill=t.txt2, anchor="center")

    # ── Hit testing ────────────────────────────────────────

    def _hit(self, x, y) -> dict | None:
        for s in self._spots:
            if s["x1"] <= x <= s["x2"] and s["y1"] <= y <= s["y2"]:
                return s
        return None

    # ── Mouse overrides ────────────────────────────────────

    def _on_press_extra(self, e: tk.Event) -> None:
        s = self._hit(e.x, e.y)
        # Header buttons (+ add) fire immediately on press, before mode is set
        if s and "click" in s and "idx" not in s:
            s["click"](); self._mode = ""; return
        if self._mode in ("drag", "collapse_click", "resize"):
            return
        if s and "idx" in s:
            self._mode = "reorder"
            self._drag_idx = None; self._drag_over = None
            self._drag_cross = False
        self._press_s = s

    def _on_motion_extra(self, e: tk.Event) -> None:
        if self._mode == "reorder":
            if self._drag_idx is None and hasattr(self, "_press_s") and self._press_s:
                self._drag_idx  = self._press_s.get("idx")
                self._drag_over = self._drag_idx

            # In-widget: update drop-target slot
            h = self._hit(e.x, e.y)
            nov = h["idx"] if h and "idx" in h else self._drag_over
            if nov != self._drag_over:
                self._drag_over = nov
                self.redraw()

            # Cross-widget / desktop detection (only once drag is confirmed moved)
            if self._moved and self._drag_idx is not None:
                inside = (0 <= e.x <= self.W and 0 <= e.y <= self.H)
                if inside:
                    if self._drag_cross:
                        self._drag_cross = False
                        self.cv.config(cursor="fleur")
                        self.redraw()
                else:
                    # Compute screen coords for the hit test
                    sx = self._win_x() + e.x
                    sy = self._win_y() + e.y
                    target = self.mgr.find_group_widget_at(
                        sx, sy, exclude_gid=self.group["id"])
                    was_cross = self._drag_cross
                    self._drag_cross = True
                    # Use a distinct cursor so the user knows what will happen:
                    # fleur = will move to another widget, arrow = will go to desktop
                    self.cv.config(cursor="fleur" if target else "arrow")
                    if not was_cross:
                        self.redraw()

    def _on_release_extra(self, e: tk.Event) -> None:
        if self._mode == "reorder" and self._moved:
            inside = (0 <= e.x <= self.W and 0 <= e.y <= self.H)

            if not inside and self._drag_idx is not None:
                # ── Cross-widget or desktop drop ──────────────
                apps = self.group["apps"]
                if self._drag_idx < len(apps):
                    app = apps[self._drag_idx]
                    sx = self._win_x() + e.x
                    sy = self._win_y() + e.y
                    target_gw = self.mgr.find_group_widget_at(
                        sx, sy, exclude_gid=self.group["id"])
                    if target_gw is not None:
                        self.mgr.move_app_to_group(app, self.group["id"], target_gw)
                    else:
                        self.mgr.send_app_to_desktop(app, self.group["id"])
            else:
                # ── Normal in-widget reorder ──────────────────
                src, dst = self._drag_idx, self._drag_over
                apps = self.group["apps"]
                if (src is not None and dst is not None and src != dst
                        and 0 <= src < len(apps) and 0 <= dst < len(apps)):
                    item = apps.pop(src); apps.insert(dst, item)
                    config.save(self.mgr.data)

        elif self._mode == "reorder" and not self._moved:
            pass   # single click does nothing — double-click launches

        self._drag_idx = None; self._drag_over = None
        self._drag_cross = False; self._hov = None
        self._mode = ""
        self.cv.config(cursor="arrow")
        self.cv.bind("<Double-Button-1>", self._dbl)
        self.cv.bind("<Button-3>", self._right_click)
        self.redraw()

    def _on_resize_extra(self, nw: int, nh: int) -> None:
        cols = max(MIN_COLS, min(MAX_COLS,
                   max(1, round((nw - _th.PAD * 2) / _th.CELL_W))))
        if cols != self.cols:
            self.group["cols"] = cols

    # ── Double-click ───────────────────────────────────────

    def _dbl(self, e: tk.Event) -> None:
        try:
            now = int(self.win.tk.call("clock", "milliseconds"))
            if now - self._last_collapse_ms < 400:
                return
        except Exception:
            pass
        h = self._hit(e.x, e.y)
        if h and "dbl" in h: h["dbl"]()
        elif e.y <= HDR_H: self.mgr.open_focus(self.group)

    # ── Right-click ────────────────────────────────────────

    def _right_click(self, e: tk.Event) -> None:
        h = self._hit(e.x, e.y)
        if h and "right" in h: h["right"]()
        else: self.mgr.group_ctx(e, self.group)

    # ── Persist ────────────────────────────────────────────

    def _save_geometry(self) -> None:
        self.group["x"] = self._win_x()
        self.group["y"] = self._win_y()
        config.save(self.mgr.data)

    def _notify_collapse_change(self) -> None:
        self.group["collapsed"] = self._collapsed
        try:
            self._last_collapse_ms = int(self.win.tk.call("clock", "milliseconds"))
        except Exception:
            self._last_collapse_ms = 0
        config.save(self.mgr.data)

    # ── Drop from Explorer ─────────────────────────────────

    def _on_drop(self, event) -> None:
        try: paths = self.win.tk.splitlist(event.data)
        except: paths = [event.data]
        resolved = []
        for p in paths:
            p = p.strip("{}").strip()
            if not p: continue
            ext = os.path.splitext(p)[1].lower()
            if ext == ".lnk":
                r = resolve_lnk(p)
                if r: p = r
                else: continue
            elif ext == ".url":
                r = resolve_url(p)
                if r: p = r
                else: continue
            if p in config.URL_APPS: resolved.append(p)
            elif p.lower().endswith(".exe") and os.path.exists(p): resolved.append(p)
        if not resolved: return
        existing = {a["path"] for a in self.group["apps"]}
        added = 0
        for path in resolved:
            if path in existing: continue
            default = os.path.splitext(os.path.basename(path))[0]
            name = ask_string(self.mgr.root, "Add app",
                              f"Name for '{default}':", initial=default,
                              theme=self._theme())
            if name:
                entry = {"name": name.strip(), "path": path}
                if path in config.URL_APPS:
                    entry["launch"] = config.URL_APPS[path]["launch"]
                    entry["icon_path"] = config.URL_APPS[path].get("icon_path")
                self.group["apps"].append(entry)
                clear_icon_cache(path)
                added += 1
        if added:
            self._refresh_size()
            config.save(self.mgr.data)
            self.redraw()

    # ── Bind events (called by manager after __init__) ─────

    def bind_events(self) -> None:
        self.cv.bind("<Double-Button-1>", self._dbl)
        self.cv.bind("<Button-3>",        self._right_click)
        self.cv.bind("<Leave>",           self._on_leave)
        self.cv.bind("<Motion>",          self._on_hover_direct)
        # Apply UIPI fix at 200ms, 600ms, and 1500ms.
        # tkinterdnd2 registers its OLE drop target asynchronously so one shot
        # isn't always enough — the later retries guarantee it sticks.
        for delay in (200, 600, 1500):
            self.win.after(delay, self._apply_uipi_fix)

    def _apply_uipi_fix(self) -> None:
        """
        Whitelist WM_DROPFILES through UIPI and install a native WM_DROPFILES
        subclass handler so drops work even when running as Administrator.
        The native handler bypasses OLE (which fails cross-integrity) entirely.
        """
        try:
            hwnd = self.win.winfo_id()
            allow_dnd_from_explorer(hwnd)
            setup_wmdrop(hwnd, self.mgr.root, self._on_wmdrop)
        except Exception:
            pass

    def _on_wmdrop(self, paths: list) -> None:
        """
        Called by the native WM_DROPFILES handler (admin-mode DnD fallback).
        Mirrors the logic of _on_drop but receives a plain list of path strings.
        """
        resolved = []
        for p in paths:
            p = p.strip()
            if not p:
                continue
            ext = os.path.splitext(p)[1].lower()
            if ext == ".lnk":
                r = resolve_lnk(p)
                if r: p = r
                else: continue
            elif ext == ".url":
                r = resolve_url(p)
                if r: p = r
                else: continue
            if p in config.URL_APPS:
                resolved.append(p)
            elif p.lower().endswith(".exe") and os.path.exists(p):
                resolved.append(p)
        if not resolved:
            return
        existing = {a["path"] for a in self.group["apps"]}
        added = 0
        for path in resolved:
            if path in existing:
                continue
            default = os.path.splitext(os.path.basename(path))[0]
            name = ask_string(self.mgr.root, "Add app",
                              f"Name for '{default}':", initial=default,
                              theme=self._theme())
            if name:
                entry = {"name": name.strip(), "path": path}
                if path in config.URL_APPS:
                    entry["launch"] = config.URL_APPS[path]["launch"]
                    entry["icon_path"] = config.URL_APPS[path].get("icon_path")
                self.group["apps"].append(entry)
                clear_icon_cache(path)
                added += 1
        if added:
            self._refresh_size()
            config.save(self.mgr.data)
            self.redraw()

    def _on_leave(self, e) -> None:
        # KEY FIX: never reset cursor/hover while any interaction is active.
        # Previously this fired during drags and forced the "blocked" no-drop cursor.
        if self._mode in ("reorder", "drag", "resize", "collapse_click"):
            return
        if self._hov is not None:
            self._hov = None
            self.redraw()
        self.cv.config(cursor="arrow")

    def _on_hover_direct(self, e: tk.Event) -> None:
        """Owns ALL cursor logic and hover highlights when idle."""
        if self._mode not in ("", "reorder"):
            return
        if self._mode == "reorder":
            return

        edge = self._edge(e.x, e.y)
        if edge:
            self.cv.config(cursor=self._CURSORS.get(edge, "arrow"))
        elif e.y <= HDR_H:
            if e.x <= HDR_H or e.x >= self.W - HDR_H:
                self.cv.config(cursor="hand2")
            else:
                self.cv.config(cursor="fleur")
        else:
            h = self._hit(e.x, e.y)
            self.cv.config(cursor="hand2" if (h and "idx" in h) else "arrow")

        h = self._hit(e.x, e.y)
        idx = h.get("idx") if h and "idx" in h else None
        if idx != self._hov:
            self._hov = idx
            self.redraw()

    # ── Rect for snapping ──────────────────────────────────

    def rect(self) -> tuple[int, int, int, int]:
        return (self._win_x(), self._win_y(), self.W, self.H)