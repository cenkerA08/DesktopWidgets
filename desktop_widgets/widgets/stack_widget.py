"""
stack_widget.py — Folder stack: several app folders in one widget.

A row of category tabs sits under the header; click a tab, or scroll the
mouse wheel over the tabs, to flip between folders. Everything else (tiles,
reordering, dragging apps out, dropping shortcuts in, the + button) works
exactly like a single folder: the stack is a GroupWidget whose `group` is
whichever folder is showing.

Data: data["stacks"] = [{id, name, groups: [group ids], active, cols, x, y,
collapsed, theme_override}]. The folders themselves stay in data["groups"].
"""
from __future__ import annotations
import tkinter as tk
import tkinter.font as tkfont
from typing import TYPE_CHECKING

import desktop_widgets.config as config
import desktop_widgets.theme as _th
from desktop_widgets.theme import HDR_H
from desktop_widgets.widgets.group_widget import GroupWidget
from desktop_widgets.ui.drawing import rounded_rect

if TYPE_CHECKING:
    from desktop_widgets.manager import Manager

TAB_H = 36          # height of the category tab strip
TAB_PAD = 12        # horizontal padding inside a tab
ARROW_W = 26        # scroll arrows shown when the tabs do not fit


class StackWidget(GroupWidget):
    def __init__(self, mgr: "Manager", stack: dict) -> None:
        self.stack = stack
        self.mgr = mgr
        self._slide = 0
        self._slide_job = None
        self._tab_hov: int | None = None
        super().__init__(mgr, self.group)
        self.cv.bind("<MouseWheel>", self._wheel)
        self._tile_wheel_bound = True       # the stack routes the wheel itself

    # ── The folder that is showing ─────────────────────────

    def _groups(self) -> list[dict]:
        by_id = {g["id"]: g for g in self.mgr.data["groups"]}
        return [by_id[gid] for gid in self.stack.get("groups", []) if gid in by_id]

    @property
    def group(self) -> dict:
        groups = self._groups()
        if not groups:
            return {"id": None, "name": self.stack.get("name", "Stack"), "apps": []}
        index = max(0, min(self.stack.get("active", 0), len(groups) - 1))
        return groups[index]

    @group.setter
    def group(self, value) -> None:
        pass        # GroupWidget assigns it in __init__; the stack decides itself

    @property
    def active_index(self) -> int:
        return max(0, min(self.stack.get("active", 0), len(self._groups()) - 1))

    # ── Sizing: tall enough for the biggest folder, so flipping never resizes ──

    @property
    def cols(self) -> int:
        return self.stack.get("cols", 5)

    @property
    def body_top(self) -> int:
        return HDR_H + TAB_H

    @property
    def _natural_h(self) -> int:
        most = max([len(g["apps"]) for g in self._groups()] + [1])
        rows = max(1, -(-most // self.cols))
        return self.body_top + rows * _th.CELL_H + _th.PAD

    def place(self, x, y, collapsed=False, **_):
        super().place(self.stack.get("x", x), self.stack.get("y", y),
                      collapsed=self.stack.get("collapsed", collapsed))

    def _theme(self):
        return config.get_theme(self.mgr.data, self.stack.get("theme_override"))

    def _home_block(self):
        return self.stack

    # ── Flipping ───────────────────────────────────────────

    def flip_to(self, index: int, animate: bool = True) -> None:
        groups = self._groups()
        if not groups:
            return
        index %= len(groups)
        old = self.active_index
        if index == old:
            return
        self.stack["active"] = index
        self._row_offset = 0
        self._hov = None
        config.save(self.mgr.data)
        if animate:
            self._slide = 18 if index > old else -18
            self._animate()
        else:
            self.redraw()

    def flip(self, step: int) -> None:
        self.flip_to(self.active_index + step)

    def _animate(self) -> None:
        if self._slide_job:
            self.win.after_cancel(self._slide_job)
        def frame():
            self.redraw()
            if self._slide:
                self._slide = int(self._slide * 0.55)
                self._slide_job = self.win.after(16, frame)
            else:
                self._slide_job = None
        frame()

    def _wheel(self, e) -> str | None:
        if self._collapsed or self._mode or not e.delta:
            return None
        if HDR_H <= e.y <= HDR_H + TAB_H or e.state & 1:     # over the tabs, or Shift
            self.flip(-1 if e.delta > 0 else 1)
            return "break"
        return self._scroll_tiles(e)

    # ── Drawing ────────────────────────────────────────────

    def _draw_header(self, t) -> None:
        apps = len(self.group["apps"])
        self.paint_header(self.stack.get("name", "Stack"),
                          meta=f"{apps} app{'s' if apps != 1 else ''}", action=True)
        if not self._collapsed:
            self._draw_tabs(t)

    def _tab_layout(self):
        """[(x1, x2, name)] for every tab in canvas coordinates, after scrolling
        so the active tab is visible; plus whether arrows are needed."""
        font = tkfont.Font(root=self.cv, font=_th.TYPE["body"])
        groups = self._groups()
        widths = [font.measure(g["name"]) + 2 * TAB_PAD for g in groups]
        left, right = _th.PAD - 4, self.W - _th.PAD + 4
        overflow = sum(widths) + 2 * (len(widths) - 1) > right - left
        if overflow:
            left, right = left + ARROW_W, right - ARROW_W
        xs, x = [], 0
        for w in widths:
            xs.append((x, x + w))
            x += w + 2
        offset = 0
        if overflow and xs:
            a1, a2 = xs[self.active_index]
            offset = max(0, min(a1 - (right - left - (a2 - a1)) // 2, x - 2 - (right - left)))
        return [(left + a - offset, left + b - offset, g["name"])
                for (a, b), g in zip(xs, groups)], overflow, (left, right)

    def _draw_tabs(self, t) -> None:
        tabs, overflow, (left, right) = self._tab_layout()
        y1, y2 = HDR_H, HDR_H + TAB_H - 6
        font = _th.TYPE["body"]
        active = self.active_index
        for i, (x1, x2, name) in enumerate(tabs):
            if x2 < left or x1 > right:
                continue
            if i == self._tab_hov and i != active:
                rounded_rect(self.cv, max(x1, left), y1, min(x2, right), y2, 5, fill=t.hov)
            label = name
            if x1 < left or x2 > right:          # partly hidden behind an arrow
                label = ""
            self.cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=label, font=font,
                                fill=t.txt if i == active else t.txt2)
            if i == active:
                cx = (x1 + x2) // 2
                rounded_rect(self.cv, cx - 8, y2 - 3, cx + 8, y2, 1, fill=t.accent)
            self._spots.append({"x1": max(x1, left), "y1": y1, "x2": min(x2, right), "y2": y2,
                                "click": lambda k=i: self.flip_to(k), "tab": i})
        if overflow:
            for side, x, step in (("chevron_left", left - ARROW_W // 2, -1),
                                  ("chevron_right", right + ARROW_W // 2, 1)):
                self.cv.create_text(x, (y1 + y2) // 2, text=_th.ICON[side], fill=t.txt2,
                                    font=(_th.ICON_FONT, -11))
                self._spots.append({"x1": x - ARROW_W // 2, "y1": y1, "x2": x + ARROW_W // 2,
                                    "y2": y2, "click": lambda s=step: self.flip(s)})
        # Hairline under the tabs separates them from the apps.
        self.cv.create_line(_th.INSET, HDR_H + TAB_H - 1, self.W - _th.INSET, HDR_H + TAB_H - 1,
                            fill=t.border)

    # ── Pointer ────────────────────────────────────────────

    def _on_hover_direct(self, e: tk.Event) -> None:
        tab = None
        if not self._mode and HDR_H <= e.y <= HDR_H + TAB_H:
            spot = self._hit(e.x, e.y)
            if spot and "click" in spot:
                self.cv.config(cursor="hand2")
                tab = spot.get("tab")
        if tab != self._tab_hov:
            self._tab_hov = tab
            self.redraw()
        if HDR_H <= e.y <= HDR_H + TAB_H and not self._mode:
            if not (self._hit(e.x, e.y) or {}).get("click"):
                self.cv.config(cursor="arrow")
            return
        super()._on_hover_direct(e)

    def _on_leave(self, e) -> None:
        if self._tab_hov is not None and not self._mode:
            self._tab_hov = None
            self.redraw()
        super()._on_leave(e)

    def _right_click(self, e: tk.Event) -> None:
        spot = self._hit(e.x, e.y)
        if spot and "right" in spot:
            spot["right"]()
        elif spot and "tab" in spot:
            self.mgr.stack_tab_ctx(e, self.stack, self._groups()[spot["tab"]])
        else:
            self.mgr.stack_ctx(e, self.stack)

    def _dbl(self, e: tk.Event) -> None:
        if HDR_H <= e.y <= HDR_H + TAB_H:
            return          # double-clicking a tab only flips to it
        if self.group.get("id") is None:
            return
        super()._dbl(e)

    def _on_drop(self, event) -> None:
        if self.group.get("id") is not None:
            super()._on_drop(event)

    def _on_wmdrop(self, paths: list) -> None:
        if self.group.get("id") is not None:
            super()._on_wmdrop(paths)

    # ── Persist ────────────────────────────────────────────

    def _on_resize_extra(self, nw: int, nh: int) -> None:
        from desktop_widgets.theme import MIN_COLS, MAX_COLS
        cols = max(MIN_COLS, min(MAX_COLS, max(1, round((nw - _th.PAD * 2) / _th.CELL_W))))
        self.stack["cols"] = cols

    def _save_geometry(self) -> None:
        self.stack["x"] = self._win_x()
        self.stack["y"] = self._win_y()
        config.save(self.mgr.data)

    def _notify_collapse_change(self) -> None:
        self.stack["collapsed"] = self._collapsed
        try:
            self._last_collapse_ms = int(self.win.tk.call("clock", "milliseconds"))
        except Exception:
            self._last_collapse_ms = 0
        config.save(self.mgr.data)

    def destroy(self) -> None:
        if self._slide_job:
            try: self.win.after_cancel(self._slide_job)
            except Exception: pass
        super().destroy()
