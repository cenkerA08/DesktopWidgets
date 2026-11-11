"""
notes_widget.py — Sticky note widget.
Editable text directly on the desktop. Auto-saves on every keystroke.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import tkinter as tk
from desktop_widgets.theme import HDR_H, INSET, TYPE, on_color
from desktop_widgets.widgets.base_widget import BaseWidget
import desktop_widgets.config as config

if TYPE_CHECKING:
    from desktop_widgets.manager import Manager


class NotesWidget(BaseWidget):
    MIN_W = 160
    MIN_H = HDR_H + 60
    MAX_W = 700
    MAX_H = 800

    def __init__(self, mgr: "Manager") -> None:
        self._text_widget: tk.Text | None = None
        self._scrollbar = None
        super().__init__(mgr)

        blk = self.mgr.data.get("notes", {})
        self.place(
            x=blk.get("x", 620),
            y=blk.get("y", 60),
            w=blk.get("w", 240),
            h=blk.get("h", 300),
            collapsed=blk.get("collapsed", False),
        )
        self.cv.bind("<Button-3>", self._right_click)

    def _home_block(self):
        return self.mgr.data.get("notes")

    def _theme(self):
        return config.get_theme(self.mgr.data,
                                self.mgr.data.get("notes", {}).get("theme_override"))

    def _draw(self) -> None:
        t = self._theme()
        self.paint_header("Notes", meta="Saved")
        if self._collapsed:
            self._remove_text_widget()
            return
        self.paint_panel(INSET, HDR_H, self.W - INSET, self.H - INSET)
        self._ensure_text_widget(t)

    def _ensure_text_widget(self, t) -> None:
        SB_W = 4
        PAD  = INSET + 8             # text sits inside the inset panel
        tx = PAD; ty = HDR_H + 8
        tw = self.W - PAD * 2 - SB_W - 4
        th = self.H - HDR_H - INSET - 16
        SB_X = self.W - INSET - SB_W - 5

        if self._text_widget is None:
            blk = self.mgr.data.get("notes", {})
            from desktop_widgets.theme import ui_font as _uf; ui_font = _uf(self.mgr.data)

            txt = tk.Text(
                self.win,
                font=(ui_font, 10),
                bg=t.btn, fg=t.txt,
                insertbackground=t.txt,
                selectbackground=t.accent, selectforeground=on_color(t.accent),
                relief="flat", bd=0, spacing1=3, spacing3=3,
                wrap="word", undo=True,
                highlightthickness=0,
                padx=2, pady=2,
            )

            # Canvas scrollbar — fully themed, no system widget
            sb_cv = tk.Canvas(self.win, width=SB_W, bg=t.btn,
                              highlightthickness=0)
            sb_cv.place(x=SB_X, y=ty,
                        width=SB_W, height=th)

            def _update_sb(*_):
                try:
                    top, bot = txt.yview()
                except Exception:
                    return
                sb_cv.delete("thumb")
                if bot - top >= 1.0:
                    return
                h = sb_cv.winfo_height()
                if h <= 1: return
                sb_cv.create_line(
                    SB_W // 2, int(top * h) + 3, SB_W // 2, int(bot * h) - 3,
                    width=SB_W, capstyle="round",
                    fill=self._theme().txt2, tags="thumb")

            txt.configure(yscrollcommand=lambda *a: (_update_sb(),))
            txt.bind("<MouseWheel>",
                     lambda e: (txt.yview_scroll(int(-1*(e.delta/120)), "units"),
                                _update_sb()))

            # Scrollbar drag
            self._sb_drag_y = None
            def _sb_press(e): self._sb_drag_y = e.y
            def _sb_drag(e):
                if self._sb_drag_y is None: return
                h = sb_cv.winfo_height()
                if h <= 1: return
                dy = (e.y - self._sb_drag_y) / h
                self._sb_drag_y = e.y
                txt.yview_moveto(txt.yview()[0] + dy)
                _update_sb()
            def _sb_release(e): self._sb_drag_y = None
            sb_cv.bind("<ButtonPress-1>",   _sb_press)
            sb_cv.bind("<B1-Motion>",       _sb_drag)
            sb_cv.bind("<ButtonRelease-1>", _sb_release)

            txt.place(x=tx, y=ty, width=tw, height=th)

            saved = blk.get("text", "")
            if saved:
                txt.insert("1.0", saved)
            txt.bind("<<Modified>>", self._on_text_change)
            # Refresh scrollbar after content loads
            txt.after(50, _update_sb)

            self._text_widget  = txt
            self._scrollbar    = sb_cv
            self._update_sb_fn = _update_sb

        else:
            # Reposition on resize
            self._text_widget.place(x=tx, y=ty, width=tw, height=th)
            if self._scrollbar:
                self._scrollbar.place(x=SB_X, y=ty, width=SB_W, height=th)
                self._scrollbar.configure(bg=t.btn)
            # Restyle text
            from desktop_widgets.theme import ui_font as _uf; ui_font = _uf(self.mgr.data)
            self._text_widget.configure(
                bg=t.btn, fg=t.txt, selectforeground=on_color(t.accent),
                insertbackground=t.txt,
                selectbackground=t.accent,
                font=(ui_font, 10),
            )
            if hasattr(self, "_update_sb_fn"):
                self._update_sb_fn()

    def _remove_text_widget(self) -> None:
        for w in (self._text_widget, self._scrollbar):
            if w:
                try: w.destroy()
                except Exception: pass
        self._text_widget = None
        self._scrollbar   = None

    def _on_text_change(self, e=None) -> None:
        if not self._text_widget or not self._text_widget.edit_modified():
            return
        content = self._text_widget.get("1.0", "end-1c")
        self.mgr.data.setdefault("notes", {})["text"] = content
        config.save(self.mgr.data)
        self._text_widget.edit_modified(False)

    def _on_resize_extra(self, nw: int, nh: int) -> None:
        if self._text_widget and not self._collapsed:
            self._ensure_text_widget(self._theme())

    def _save_geometry(self) -> None:
        blk = self.mgr.data.setdefault("notes", {})
        blk["x"] = self._win_x(); blk["y"] = self._win_y()
        blk["w"] = self.W;             blk["h"] = self._full_h
        config.save(self.mgr.data)

    def _notify_collapse_change(self) -> None:
        self.mgr.data.setdefault("notes", {})["collapsed"] = self._collapsed
        config.save(self.mgr.data)

    def rect(self):
        return (self._win_x(), self._win_y(), self.W, self.H)

    def destroy(self) -> None:
        self._remove_text_widget()
        super().destroy()

    def _right_click(self, e) -> None:
        self.mgr.root.focus_force()
        m = self.mgr._menu()
        m.add_command(label="Clear note",    command=self._clear)
        m.add_separator()
        m.add_command(label="Remove widget", command=self.mgr.remove_notes)
        try: m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()

    def _clear(self) -> None:
        from desktop_widgets.utils import ask_confirm
        if ask_confirm(self.mgr.root, "Clear all note text?", theme=self._theme()):
            if self._text_widget:
                self._text_widget.delete("1.0", "end")
            self.mgr.data.setdefault("notes", {})["text"] = ""
            config.save(self.mgr.data)
