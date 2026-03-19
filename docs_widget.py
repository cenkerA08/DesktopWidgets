"""
docs_widget.py — Documents/Files widget.
Pin any file (PDF, DOCX, XLSX, CSV, etc.) as a tile.
Double-click opens with the system default application.
Drag-and-drop supported if tkinterdnd2 is installed.
"""
from __future__ import annotations
import os
from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import filedialog
from theme import HDR_H, CHROMA
import theme as _th
from base_widget import BaseWidget
from utils import clip, ask_string, ask_confirm
import config

if TYPE_CHECKING:
    from manager import Manager

try:
    from tkinterdnd2 import DND_FILES
    DND_OK = True
except ImportError:
    DND_OK = False

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ── File-type colours & icons ──────────────────────────────
_EXT_COLOR = {
    ".pdf":  "#e05c5c",
    ".docx": "#5b7cf8", ".doc": "#5b7cf8",
    ".xlsx": "#3dbf7f", ".xls": "#3dbf7f", ".csv": "#3dbf7f",
    ".pptx": "#e0a050", ".ppt": "#e0a050",
    ".txt":  "#9098aa", ".md":  "#9098aa",
    ".zip":  "#c8855a", ".rar": "#c8855a", ".7z": "#c8855a",
    ".mp4":  "#a06cf8", ".mkv": "#a06cf8", ".avi": "#a06cf8",
    ".mp3":  "#2ecfcf", ".wav": "#2ecfcf",
    ".png":  "#e06090", ".jpg": "#e06090", ".jpeg": "#e06090",
}
_EXT_LABEL = {
    ".pdf":  "PDF",
    ".docx": "DOC", ".doc": "DOC",
    ".xlsx": "XLS", ".xls": "XLS", ".csv": "CSV",
    ".pptx": "PPT", ".ppt": "PPT",
    ".txt":  "TXT", ".md":  "MD",
    ".zip":  "ZIP", ".rar": "RAR", ".7z":  "7Z",
    ".mp4":  "MP4", ".mkv": "MKV", ".avi": "AVI",
    ".mp3":  "MP3", ".wav": "WAV",
    ".png":  "IMG", ".jpg": "IMG", ".jpeg": "IMG",
}

CELL_W = 88
CELL_H = 90
ICON_SZ = 48
PAD    = 10
MIN_COLS = 1
MAX_COLS = 8

_ICON_CACHE: dict[tuple, object] = {}


def _file_tile(path: str, size: int):
    """Render a coloured rounded square with the file extension label."""
    if not PIL_OK:
        return None
    key = (path, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    ext  = os.path.splitext(path)[1].lower()
    col  = _EXT_COLOR.get(ext, "#5b7cf8")
    lbl  = _EXT_LABEL.get(ext, ext.lstrip(".").upper()[:4] or "?")
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    r    = max(6, size // 5)
    d.rounded_rectangle([0, 0, size-1, size-1], radius=r, fill=col)
    d.text((size//2, size//2), lbl, fill="white", anchor="mm")
    photo = ImageTk.PhotoImage(img)
    _ICON_CACHE[key] = photo
    return photo


class DocsWidget(BaseWidget):
    MIN_W = CELL_W + PAD * 2
    MIN_H = HDR_H + CELL_H + PAD * 2
    MAX_W = CELL_W * 8 + PAD * 2
    MAX_H = 700

    def __init__(self, mgr: "Manager", blk: dict) -> None:
        self._blk    = blk       # the data block (one of data["docs_widgets"][i])
        self._spots: list[dict] = []
        self._refs:  list = []
        self._hov:   int | None = None

        super().__init__(mgr)

        if DND_OK:
            try:
                self.win.drop_target_register(DND_FILES)
                self.win.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

        self.place(
            x=blk.get("x", 60),
            y=blk.get("y", 400),
            collapsed=blk.get("collapsed", False),
        )
        self.cv.bind("<Double-Button-1>", self._dbl)
        self.cv.bind("<Button-3>",        self._right_click)
        self.cv.bind("<Leave>",           self._on_leave)
        self.cv.bind("<Motion>",          self._on_hover)

    # ── Sizing ─────────────────────────────────────────────

    @property
    def cols(self) -> int:
        return self._blk.get("cols", 3)

    @property
    def _natural_w(self) -> int:
        return self.cols * CELL_W + PAD * 2

    @property
    def _natural_h(self) -> int:
        n = max(len(self._blk.get("files", [])), 1)
        rows = max(1, -(-n // self.cols))
        return HDR_H + rows * CELL_H + PAD * 2

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

    def _theme(self):
        return config.get_theme(self.mgr.data,
                                self._blk.get("theme_override"))

    # ── Draw ───────────────────────────────────────────────

    def _draw(self) -> None:
        self._spots.clear(); self._refs.clear()
        t = self._theme()
        files = self._blk.get("files", [])
        ww, wh = self.W, self.H

        # Header title + add button
        self.cv.create_text(ww // 2, HDR_H // 2,
            text=self._blk.get("name", "Files"),
            font=("Segoe UI", 11, "bold"), fill=t.txt, anchor="center")

        self.cv.create_rectangle(ww - HDR_H, 0, ww, HDR_H,
            fill="", outline="", tags="add_btn")
        self.cv.create_text(ww - HDR_H // 2, HDR_H // 2, text="+",
            font=("Segoe UI", 14, "bold"), fill=t.txt2, anchor="center",
            tags="add_btn")
        self._spots.append({
            "x1": ww - HDR_H, "y1": 0, "x2": ww, "y2": HDR_H,
            "click": self._add_file,
        })

        if self._collapsed:
            return

        if not files:
            hint = "Drop files here" if DND_OK else "Click + to add files"
            self.cv.create_text(ww // 2, HDR_H + (wh - HDR_H) // 2,
                text=hint, font=("Segoe UI", 9),
                fill=t.txt2, anchor="center", justify="center")
            return

        for i, f in enumerate(files):
            col = i % self.cols; row = i // self.cols
            ax  = PAD + col * CELL_W; ay = HDR_H + PAD + row * CELL_H
            cx  = ax + CELL_W // 2

            if i == self._hov:
                self.cv.create_rectangle(ax+2, ay+2, ax+CELL_W-2, ay+CELL_H-2,
                    fill=t.btn_h, outline=t.accent, width=1)

            photo = _file_tile(f["path"], ICON_SZ)
            if photo:
                self._refs.append(photo)
                self.cv.create_image(cx, ay + ICON_SZ // 2 + 4,
                    image=photo, anchor="center")

            self.cv.create_text(cx, ay + ICON_SZ + 12,
                text=clip(f["name"], 10), font=("Segoe UI", 8),
                fill=t.txt3, anchor="n", width=CELL_W - 4)

            bid = self._blk["id"]
            self._spots.append({
                "x1": ax, "y1": ay, "x2": ax+CELL_W, "y2": ay+CELL_H,
                "idx": i,
                "dbl":   lambda p=f["path"]: self._open(p),
                "right": lambda p=f["path"], n=f["name"]: self._file_ctx(p, n),
            })

    # ── Hit ────────────────────────────────────────────────

    def _hit(self, x, y) -> dict | None:
        for s in self._spots:
            if s["x1"] <= x <= s["x2"] and s["y1"] <= y <= s["y2"]:
                return s
        return None

    # ── Events ─────────────────────────────────────────────

    def _on_hover(self, e) -> None:
        if self._mode != "":
            return
        h = self._hit(e.x, e.y)
        idx = h["idx"] if h and "idx" in h else None
        edge = self._edge(e.x, e.y)
        if edge:
            self.cv.config(cursor=self._CURSORS.get(edge, "arrow"))
        elif e.y <= HDR_H:
            self.cv.config(cursor="hand2" if (e.x <= HDR_H or e.x >= self.W - HDR_H) else "fleur")
        else:
            self.cv.config(cursor="hand2" if (h and "idx" in h) else "arrow")
        if idx != self._hov:
            self._hov = idx
            self.redraw()

    def _on_leave(self, e) -> None:
        if self._hov is not None:
            self._hov = None
            self.redraw()
        self.cv.config(cursor="arrow")

    def _on_press_extra(self, e) -> None:
        if self._mode in ("drag", "collapse_click", "resize"):
            return
        s = self._hit(e.x, e.y)
        if s and "click" in s and "idx" not in s:
            s["click"](); self._mode = ""

    def _dbl(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and "dbl" in h:
            h["dbl"]()

    def _right_click(self, e) -> None:
        h = self._hit(e.x, e.y)
        if h and "right" in h:
            h["right"]()
        else:
            self._widget_ctx(e)

    def _on_resize_extra(self, nw: int, nh: int) -> None:
        cols = max(MIN_COLS, min(MAX_COLS, max(1, round((nw - PAD * 2) / CELL_W))))
        if cols != self.cols:
            self._blk["cols"] = cols

    def _save_geometry(self) -> None:
        self._blk["x"] = self._win_x()
        self._blk["y"] = self._win_y()
        config.save(self.mgr.data)

    def _notify_collapse_change(self) -> None:
        self._blk["collapsed"] = self._collapsed
        config.save(self.mgr.data)

    def rect(self):
        return (self._win_x(), self._win_y(), self.W, self.H)

    # ── File actions ───────────────────────────────────────

    def _open(self, path: str) -> None:
        if not os.path.exists(path):
            tk.messagebox.showerror("Not found", f"File not found:\n{path}")
            return
        try:
            os.startfile(path)
        except Exception as ex:
            tk.messagebox.showerror("Error", str(ex))

    def _add_file(self) -> None:
        FILETYPES = [
            ("All supported", "*.pdf *.docx *.doc *.xlsx *.xls *.csv *.pptx *.ppt "
                              "*.txt *.md *.png *.jpg *.jpeg *.mp4 *.mp3 *.zip *.rar *.7z *.*"),
            ("PDF",           "*.pdf"),
            ("Word",          "*.docx *.doc"),
            ("Excel / CSV",   "*.xlsx *.xls *.csv"),
            ("PowerPoint",    "*.pptx *.ppt"),
            ("Text / Markdown","*.txt *.md"),
            ("Images",        "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("Video",         "*.mp4 *.mkv *.avi *.mov"),
            ("Audio",         "*.mp3 *.wav *.flac *.ogg"),
            ("Archives",      "*.zip *.rar *.7z *.tar *.gz"),
            ("All files",     "*.*"),
        ]
        paths = filedialog.askopenfilenames(
            title="Add files", parent=self.mgr.root,
            filetypes=FILETYPES)
        if not paths:
            return
        existing = {f["path"] for f in self._blk.setdefault("files", [])}
        added = 0
        for path in paths:
            if path in existing:
                continue
            default = os.path.splitext(os.path.basename(path))[0]
            name = ask_string(self.mgr.root, "Add file",
                              f"Label for '{default}':", initial=default,
                              theme=self._theme())
            if name:
                self._blk["files"].append({"name": name.strip(), "path": path})
                added += 1
        if added:
            self._refresh_size()
            config.save(self.mgr.data)
            self.redraw()

    def _file_ctx(self, path: str, name: str) -> None:
        m = self.mgr._menu()
        m.add_command(label=f"📂  Open {name}", command=lambda: self._open(path))
        m.add_command(label="📋  Copy path",
                      command=lambda: (self.mgr.root.clipboard_clear(),
                                       self.mgr.root.clipboard_append(path)))
        m.add_separator()
        m.add_command(label="Remove",
                      command=lambda: self._remove_file(path))
        self.mgr.root.focus_force()
        try: m.tk_popup(self.mgr.root.winfo_pointerx(), self.mgr.root.winfo_pointery())
        finally: m.grab_release()

    def _remove_file(self, path: str) -> None:
        self._blk["files"] = [f for f in self._blk.get("files", [])
                               if f["path"] != path]
        self._refresh_size()
        config.save(self.mgr.data)
        self.redraw()

    def _widget_ctx(self, e) -> None:
        m = self.mgr._menu()
        m.add_command(label="Rename",
                      command=lambda: self.mgr.rename_docs(self._blk))
        m.add_separator()
        m.add_command(label="Delete widget",
                      command=lambda: self.mgr.delete_docs(self._blk["id"]))
        m.add_separator()
        m.add_command(label="⚙  Settings", command=self.mgr.open_settings)
        self.mgr.root.focus_force()
        try: m.tk_popup(e.x_root, e.y_root)
        finally: m.grab_release()

    # ── Drop ───────────────────────────────────────────────

    def _on_drop(self, event) -> None:
        try:
            paths = self.win.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        existing = {f["path"] for f in self._blk.setdefault("files", [])}
        added = 0
        for path in paths:
            path = path.strip("{}").strip()
            if not path or not os.path.isfile(path):
                continue
            if path in existing:
                continue
            default = os.path.splitext(os.path.basename(path))[0]
            name = ask_string(self.mgr.root, "Add file",
                              f"Label for '{default}':", initial=default,
                              theme=self._theme())
            if name:
                self._blk["files"].append({"name": name.strip(), "path": path})
                added += 1
        if added:
            self._refresh_size()
            config.save(self.mgr.data)
            self.redraw()