"""
context_menu.py — Themed context menu that matches the active theme.
Drop-in replacement for tk.Menu — same add_command / add_separator / tk_popup API.
"""
from __future__ import annotations
import tkinter as tk

ITEM_H = 32
SEP_H  = 9
MIN_W  = 200
PAD_X  = 16


class ContextMenu:
    def __init__(self, root: tk.Misc, t) -> None:
        self._root  = root
        self._t     = t
        self._items: list[dict] = []
        self._win:   tk.Toplevel | None = None
        self._hov:   int | None = None

    def add_command(self, label: str = "", command=None, state: str = "normal") -> None:
        self._items.append({"type": "cmd", "label": label,
                            "command": command, "state": state})

    def add_separator(self) -> None:
        self._items.append({"type": "sep"})

    def grab_release(self) -> None:
        if self._win:
            try: self._win.grab_release()
            except: pass

    def tk_popup(self, x: int, y: int, entry: int = 0) -> None:
        self._show(x, y)

    def _show(self, x: int, y: int) -> None:
        t = self._t

        w = MIN_W
        h = 8
        for item in self._items:
            h += SEP_H if item["type"] == "sep" else ITEM_H
        h += 8

        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        if x + w > sw: x = sw - w - 4
        if y + h > sh: y = sh - h - 4

        self._win = tk.Toplevel(self._root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg=t.border)
        self._win.geometry(f"{w}x{h}+{x}+{y}")

        cv = tk.Canvas(self._win, width=w, height=h,
                       bg=t.hdr, highlightthickness=1,
                       highlightbackground=t.border)
        cv.pack(fill="both", expand=True)

        iy = 8
        self._item_rects = []

        for i, item in enumerate(self._items):
            if item["type"] == "sep":
                cy = iy + SEP_H // 2
                cv.create_line(PAD_X, cy, w - PAD_X, cy,
                               fill=t.border, width=1, tags=f"sep_{i}")
                self._item_rects.append(None)
                iy += SEP_H
            else:
                disabled = item.get("state") == "disabled"
                fg = t.txt2 if disabled else t.txt
                self._item_rects.append((iy, iy + ITEM_H, i))
                self._draw_label(cv, item["label"], PAD_X, iy + ITEM_H // 2,
                                 fg, bold=False, tags=f"item_{i}")
                iy += ITEM_H

        def _motion(e):
            new_hov = None
            for rect in self._item_rects:
                if rect is None: continue
                y1, y2, idx = rect
                if y1 <= e.y <= y2:
                    itm = self._items[idx]
                    if itm.get("state") != "disabled" and itm.get("command"):
                        new_hov = idx
                    break
            if new_hov != self._hov:
                self._hov = new_hov
                self._redraw(cv, w)

        def _click(e):
            for rect in self._item_rects:
                if rect is None: continue
                y1, y2, idx = rect
                if y1 <= e.y <= y2:
                    itm = self._items[idx]
                    if itm.get("state") != "disabled" and itm.get("command"):
                        self._close()
                        itm["command"]()
                    return
            self._close()

        def _leave(e):
            self._hov = None
            self._redraw(cv, w)

        cv.bind("<Motion>",   _motion)
        cv.bind("<Button-1>", _click)
        cv.bind("<Leave>",    _leave)
        self._win.bind("<Escape>",   lambda e: self._close())
        self._win.bind("<FocusOut>", lambda e: self._close())
        self._root.bind("<Button-1>", self._on_outside_click, add=True)

        self._cv = cv
        self._w  = w
        self._redraw(cv, w)
        self._win.focus_force()
        self._win.grab_set()

    def _redraw(self, cv: tk.Canvas, w: int) -> None:
        t  = self._t
        iy = 8
        cv.delete("hover")
        for i in range(len(self._items)):
            cv.delete(f"item_{i}")

        for i, item in enumerate(self._items):
            if item["type"] == "sep":
                iy += SEP_H
                continue

            if i == self._hov:
                cv.create_rectangle(2, iy, w - 2, iy + ITEM_H,
                                    fill=t.hov, outline="", tags="hover")
                cv.create_rectangle(2, iy, 5, iy + ITEM_H,
                                    fill=t.accent, outline="", tags="hover")
                self._draw_label(cv, item["label"], PAD_X + 2, iy + ITEM_H // 2,
                                 t.txt, bold=True, tags="hover")
            else:
                disabled = item.get("state") == "disabled"
                fg = t.txt2 if disabled else t.txt
                self._draw_label(cv, item["label"], PAD_X, iy + ITEM_H // 2,
                                 fg, bold=False, tags=f"item_{i}")
            iy += ITEM_H

        cv.tag_raise("hover")
        for i in range(len(self._items)):
            cv.tag_raise(f"item_{i}")

    def _draw_label(self, cv, label: str, x: int, y: int,
                    fg: str, bold: bool, tags: str) -> None:
        """Draw label with emoji always at normal weight, text optionally bold."""
        # Split leading emoji from rest of label
        # Labels look like "⤢  Open focus" or "✎  Rename"
        parts = label.split("  ", 1)
        if len(parts) == 2:
            icon, text = parts[0], parts[1]
            # Draw emoji at normal weight always
            cv.create_text(x, y, text=icon + "  ", anchor="w",
                           font=("Segoe UI", 10), fill=fg, tags=tags)
            # Measure emoji width to offset text
            icon_w = len(icon) * 11 + 14  # approx
            cv.create_text(x + icon_w, y, text=text, anchor="w",
                           font=("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10),
                           fill=fg, tags=tags)
        else:
            cv.create_text(x, y, text=label, anchor="w",
                           font=("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10),
                           fill=fg, tags=tags)

    def _on_outside_click(self, e) -> None:
        if self._win:
            try:
                wx = self._win.winfo_x(); wy = self._win.winfo_y()
                ww = self._win.winfo_width(); wh = self._win.winfo_height()
                if not (wx <= e.x_root <= wx+ww and wy <= e.y_root <= wy+wh):
                    self._close()
            except:
                self._close()

    def _close(self) -> None:
        try: self._root.unbind("<Button-1>")
        except: pass
        try:
            self._win.grab_release()
            self._win.destroy()
            self._win = None
        except: pass