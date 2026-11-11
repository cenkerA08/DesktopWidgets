"""
context_menu.py — Windows 11 style context menu (a rounded flyout).
Drop-in replacement for tk.Menu — same add_command / add_separator / tk_popup API.
Labels may start with an emoji followed by two spaces ("✎  Rename"); the
emoji is shown as the matching Segoe Fluent Icons glyph.
"""
from __future__ import annotations
import tkinter as tk

ITEM_H = 32
SEP_H  = 9
MIN_W  = 220
PAD    = 4      # inset of the item highlight inside the flyout

# Emoji used in menu labels → Fluent icon names.
_ICONS = {
    "⤢": "focus", "✎": "edit", "🗑": "delete", "✕": "close", "⚙": "settings",
    "⏻": "power", "▶": "play", "🖼": "picture", "📂": "open", "➕": "add",
    "🖥": "desktop", "✨": "sparkle", "↗": "open", "📁": "folder", "🔗": "link", "✏": "rename",
    "◈": "picture", "📋": "copy", "\u2713": "check", "\U0001F5A5": "desktop",
}
# Plain labels that still deserve an icon.
_TEXT_ICONS = {"Remove": "delete", "Remove widget": "delete", "Delete widget": "delete",
               "Clear note": "clear", "Rename": "edit"}


class ContextMenu:
    def __init__(self, root: tk.Misc, t) -> None:
        self._root  = root
        self._t     = t
        self._items: list[dict] = []
        self._win:   tk.Toplevel | None = None
        self._hov:   int | None = None

    def add_command(self, label: str = "", command=None, state: str = "normal") -> None:
        icon, text = None, label
        parts = label.split("  ", 1)
        if len(parts) == 2 and len(parts[0]) <= 2:
            icon, text = _ICONS.get(parts[0].strip(), None), parts[1]
        icon = icon or _TEXT_ICONS.get(text)
        self._items.append({"type": "cmd", "label": text, "icon": icon,
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
        from desktop_widgets.theme import CHROMA, TYPE
        from desktop_widgets.ui.drawing import rounded_rect
        import tkinter.font as tkfont
        t = self._t

        measure = tkfont.Font(root=self._root, font=TYPE["body"]).measure
        w = max([MIN_W] + [measure(i["label"]) + 76 for i in self._items if i["type"] == "cmd"])
        h = 2 * PAD + sum(SEP_H if i["type"] == "sep" else ITEM_H for i in self._items)

        from desktop_widgets.services.screens import area_for, clamp
        x, y = clamp(x, y, w, h, area_for(self._root, x, y), margin=4)

        self._win = tk.Toplevel(self._root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg=CHROMA)
        self._win.attributes("-transparentcolor", CHROMA)
        self._win.geometry(f"{w}x{h}+{x}+{y}")

        cv = tk.Canvas(self._win, width=w, height=h, bg=CHROMA, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        rounded_rect(cv, 0, 0, w, h, 8, fill=t.btn, outline=t.border, hard=True)

        self._item_rects = []
        iy = PAD
        for i, item in enumerate(self._items):
            if item["type"] == "sep":
                cy = iy + SEP_H // 2
                cv.create_line(1, cy, w - 1, cy, fill=t.border, width=1)
                self._item_rects.append(None)
                iy += SEP_H
            else:
                self._item_rects.append((iy, iy + ITEM_H, i))
                iy += ITEM_H

        def _motion(e):
            new_hov = None
            for rect in self._item_rects:
                if rect is None: continue
                y1, y2, idx = rect
                if y1 <= e.y < y2:
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
                if y1 <= e.y < y2:
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
        cv.bind("<ButtonRelease-1>", _click)
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
        from desktop_widgets.theme import TYPE, ICON, ICON_FONT, R_CTRL
        from desktop_widgets import theme as th
        from desktop_widgets.ui.drawing import rounded_rect
        t  = self._t
        cv.delete("item")
        for rect in self._item_rects:
            if rect is None:
                continue
            y1, y2, i = rect
            item = self._items[i]
            disabled = item.get("state") == "disabled"
            fg = t.txt2 if disabled else t.txt
            if i == self._hov:
                shape = rounded_rect(cv, PAD, y1 + 1, w - PAD, y2 - 1, R_CTRL, fill=t.btn_h)
                cv.addtag_withtag("item", shape)
            cy = (y1 + y2) // 2
            if item.get("icon"):
                cv.create_text(PAD + 20, cy, text=ICON[item["icon"]], fill=fg,
                               font=(th.ICON_FONT, -14), tags="item")
            cv.create_text(PAD + 44, cy, text=item["label"], anchor="w",
                           font=TYPE["body"], fill=fg, tags="item")

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
