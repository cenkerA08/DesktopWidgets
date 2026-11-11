"""Quick launcher: a search box that opens over everything with a shortcut.

Type part of a name, initials ("rdr") or a few letters in order, then press
Enter. Searches the apps in your folders and stacks, files in Files widgets,
every installed app, your saved layouts and a couple of commands. With nothing
typed it shows what you opened most recently.
"""
from __future__ import annotations

import os
import threading
import time
import tkinter as tk

from PIL import ImageTk

from desktop_widgets import config
from desktop_widgets import theme as th
from desktop_widgets.theme import CHROMA, TYPE, mix, on_color
from desktop_widgets.services import search
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.drawing import rounded_rect

W = 640
SEARCH_H = 60
ROW_H = 52
_installed: dict = {"apps": None, "loaded": 0.0, "loading": False}


def _load_installed() -> None:
    """Installed apps are slow to list (COM), so load them once in the background."""
    if _installed["loading"] or (_installed["apps"] is not None and time.time() - _installed["loaded"] < 600):
        return
    _installed["loading"] = True
    def run():
        try:
            from desktop_widgets.services.apps import installed_apps
            _installed["apps"] = installed_apps()
            _installed["loaded"] = time.time()
        except Exception as exc:
            print(f"[launcher] installed apps: {exc}")
            _installed["apps"] = _installed["apps"] or []
        finally:
            _installed["loading"] = False
    threading.Thread(target=run, name="installed-apps", daemon=True).start()


class Launcher:
    def __init__(self, mgr):
        self.mgr = mgr
        self.t = t = config.get_theme(mgr.data)
        self.results: list[dict] = []
        self.selected = 0
        self._icons: dict = {}
        self._closing = False
        _load_installed()
        self.items = search.collect(mgr.data, _installed["apps"])

        x, y = mgr.root.winfo_pointerx(), mgr.root.winfo_pointery()
        left, top, right, bottom = area_for(mgr.root, x, y)
        self.x = left + (right - left - W) // 2
        self.y = top + int((bottom - top) * 0.2)

        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=CHROMA)
        self.win.attributes("-transparentcolor", CHROMA)
        self.cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0, width=W)
        self.cv.pack(fill="both", expand=True)

        self.query = tk.StringVar()
        self.entry = tk.Entry(self.cv, textvariable=self.query, bg=t.bg, fg=t.txt,
                              insertbackground=t.txt, selectbackground=t.accent,
                              selectforeground=on_color(t.accent), relief="flat",
                              highlightthickness=0, borderwidth=0, font=(th.FONT, 15))
        self.placeholder = tk.Label(self.cv, text="Search apps, games, files and layouts",
                                    bg=t.bg, fg=t.txt2, font=(th.FONT, 15), cursor="xterm")
        self.placeholder.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.query.trace_add("write", lambda *_: self.update())
        for key, handler in (("<Escape>", lambda e: self.close()), ("<Return>", lambda e: self.open()),
                             ("<Down>", lambda e: self.move(1)), ("<Up>", lambda e: self.move(-1)),
                             ("<Tab>", lambda e: self.move(1)), ("<Shift-Tab>", lambda e: self.move(-1))):
            self.entry.bind(key, lambda e, h=handler: (h(e), "break")[1])
        self.win.bind("<FocusOut>", self._focus_out)
        self.cv.bind("<Motion>", self._hover)
        self.cv.bind("<ButtonRelease-1>", self._click)
        self.cv.bind("<MouseWheel>", lambda e: (self.move(-1 if e.delta > 0 else 1), "break")[1])

        self.update()
        self._bring_to_front()
        self._refresh_installed()

    # ── Window ─────────────────────────────────────────────

    def _bring_to_front(self) -> None:
        self.win.update_idletasks()
        self.win.lift()
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        self.win.focus_force()
        self.entry.focus_set()

    def _refresh_installed(self) -> None:
        """Add installed apps to the results once they finish loading."""
        if self._closing:
            return
        if _installed["loading"] or _installed["apps"] is None:
            self.win.after(200, self._refresh_installed)
            return
        if not any(i["kind"] == "installed" for i in self.items):
            self.items = search.collect(self.mgr.data, _installed["apps"])
            self.update()

    def _focus_out(self, e) -> None:
        # Focus moves between the window and its entry; only close when it
        # really left the launcher.
        self.win.after(120, lambda: None if self._closing or self.win.focus_get() else self.close())

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        try: self.win.destroy()
        except tk.TclError: pass
        if getattr(self.mgr, "launcher", None) is self:
            self.mgr.launcher = None

    # ── Results ────────────────────────────────────────────

    def update(self) -> None:
        q = self.query.get()
        self.results = search.search(self.items, q, self.mgr.data.get("usage"))
        self.selected = 0
        self.draw()

    def move(self, step: int) -> None:
        if self.results:
            self.selected = (self.selected + step) % len(self.results)
            self.draw()

    def _row_at(self, y: int) -> int | None:
        i = (y - SEARCH_H - 8) // ROW_H
        return i if y > SEARCH_H and 0 <= i < len(self.results) else None

    def _hover(self, e) -> None:
        i = self._row_at(e.y)
        self.cv.config(cursor="hand2" if i is not None else "")
        if i is not None and i != self.selected:
            self.selected = i
            self.draw()

    def _click(self, e) -> None:
        i = self._row_at(e.y)
        if i is not None:
            self.selected = i
            self.open()

    def _icon(self, item):
        key = (item["kind"], item["path"], item.get("command"))
        if key not in self._icons:
            photo = None
            if item["kind"] in ("app", "file", "installed"):
                try:
                    from desktop_widgets.ui.tiles import icon_image
                    image = icon_image(item["app"], 64, self.t.accent).resize((32, 32))
                    photo = ImageTk.PhotoImage(image, master=self.cv)
                except Exception:
                    photo = None
            self._icons[key] = photo
        return self._icons[key]

    def draw(self) -> None:
        t, cv = self.t, self.cv
        cv.delete("all")
        rows = len(self.results)
        empty_hint = not rows
        height = SEARCH_H + (rows * ROW_H + 16 if rows else 44 if empty_hint else 0)
        self.win.geometry(f"{W}x{height}+{self.x}+{self.y}")
        cv.configure(height=height)
        rounded_rect(cv, 0, 0, W, height, 8, fill=t.bg, outline=t.border, hard=True)
        # Search row
        cv.create_text(26, SEARCH_H // 2, text=th.ICON["search"], fill=t.txt2,
                       font=(th.ICON_FONT, -18))
        cv.create_window(52, SEARCH_H // 2, window=self.entry, anchor="w", width=W - 190, height=30)
        if self.query.get():
            cv.delete("placeholder")
        else:
            cv.create_window(52, SEARCH_H // 2, window=self.placeholder, anchor="w", tags="placeholder")
        hotkey = self.mgr.data.get("launcher_hotkey") or ""
        if hotkey and hotkey != "Off":
            cv.create_text(W - 18, SEARCH_H // 2, text=hotkey, anchor="e", fill=t.txt2,
                           font=TYPE["caption"])
        cv.create_line(1, SEARCH_H, W - 1, SEARCH_H, fill=t.border)

        if empty_hint:
            text = ("No matches. Try fewer letters or the first letters of each word."
                    if self.query.get().strip() else
                    "Type to search your folders, files, installed apps and layouts.")
            cv.create_text(W // 2, SEARCH_H + 22, text=text, fill=t.txt2, font=TYPE["caption"])
            return
        for i, item in enumerate(self.results):
            y = SEARCH_H + 8 + i * ROW_H
            if i == self.selected:
                rounded_rect(cv, 6, y + 2, W - 6, y + ROW_H - 2, 5, fill=t.btn_h)
                rounded_rect(cv, 6, y + ROW_H // 2 - 9, 9, y + ROW_H // 2 + 9, 1, fill=t.accent)
            cx, cy = 38, y + ROW_H // 2
            photo = self._icon(item)
            if photo:
                cv.create_image(cx, cy, image=photo)
            else:
                rounded_rect(cv, cx - 16, cy - 16, cx + 16, cy + 16, 6, fill=mix(t.bg, t.accent, 0.16))
                glyph = {"layout": "desktop",
                         "command": {"settings": "settings", "organize": "sparkle"}.get(item.get("command"), "add")
                         }.get(item["kind"], "apps")
                cv.create_text(cx, cy, text=th.ICON[glyph], fill=t.accent, font=(th.ICON_FONT, -16))
            cv.create_text(66, cy - 9, text=item["name"], anchor="w", fill=t.txt, font=TYPE["strong"])
            cv.create_text(66, cy + 10, text=item["sub"], anchor="w", fill=t.txt2, font=TYPE["caption"])
            if i == self.selected:
                action = {"layout": "Switch", "command": "Open", "file": "Open"}.get(item["kind"], "Launch")
                cv.create_text(W - 18, cy, text=f"{action}  ↵", anchor="e", fill=t.txt2,
                               font=TYPE["caption"])

    # ── Opening ────────────────────────────────────────────

    def open(self) -> None:
        if not self.results:
            return
        item = self.results[self.selected]
        self.close()
        mgr = self.mgr
        if item["kind"] == "layout":
            mgr.apply_layout(item["layout"])
        elif item["kind"] == "command":
            if item["command"] == "settings":
                mgr.open_settings()
            elif item["command"] == "organize":
                mgr.open_organizer()
            else:
                mgr.show_add_picker()
        elif item["kind"] == "file":
            search.record_launch(mgr.data, item["path"])
            config.save(mgr.data)
            try:
                os.startfile(item["path"])
            except OSError as exc:
                from tkinter import messagebox
                messagebox.showerror("Could not open file", str(exc))
        else:
            app = item["app"]
            if app.get("launch"):
                config.URL_APPS[app["path"]] = {"launch": app["launch"], "icon_path": app.get("icon_path")}
            mgr.launch(app["path"])
