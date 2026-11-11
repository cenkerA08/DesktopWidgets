"""
settings_screen.py — Settings window in the Windows 11 Settings layout.
A navigation pane (Appearance | Widgets | System) and a scrolling page of
grouped cards: a heading above each card, title + description on the left
of a row and its control on the right.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from desktop_widgets.theme import PRESETS, TYPE, R_PANEL, mix
import desktop_widgets.config as config
from desktop_widgets.version import VERSION

if TYPE_CHECKING:
    from desktop_widgets.manager import Manager

NAV_W = 196
PAGE_PAD = 24


def _btn(parent, text, command, t, accent=False, danger=False, **kw):
    """Standard (or accent) Windows 11 button."""
    from desktop_widgets.ui.components import RoundedButton
    if danger:
        kw['fg'] = t.danger
    return RoundedButton(parent, text, command, t, accent=accent, **kw)


def _outline_btn(parent, text, command, t, danger=False, **kw):
    """Compact secondary button (rename, remove)."""
    kw.setdefault('padx', 12)
    kw.setdefault('pady', 5)
    return _btn(parent, text, command, t, danger=danger, **kw)


def _col_stepper(parent, t, get_val, set_val, min_val=1, max_val=12):
    from desktop_widgets.ui.components import stepper
    return stepper(parent, t, get_val, set_val, min_val, max_val)


def _preset_swatch_row(parent, t, current_name, on_select, bg=None):
    from desktop_widgets.ui.components import theme_picker
    theme_picker(parent, t, current_name, on_select, bg)


class SettingsScreen:
    TABS = [
        ("Appearance", "appearance", "palette"),
        ("Widgets",    "widgets",    "apps"),
        ("System",     "system",     "settings"),
    ]

    def __init__(self, mgr: "Manager", initial_tab: str = "appearance",
                 scroll_to: int | None = None) -> None:
        self.mgr = mgr
        self._tab = initial_tab
        self._scroll_to_widget = scroll_to
        self._scroll_pos = 0.0
        t = config.get_theme(mgr.data)
        from desktop_widgets.services.screens import area_for
        left, top, right, bottom = area_for(mgr.root, mgr.root.winfo_pointerx(), mgr.root.winfo_pointery())
        sw, sh = right-left, bottom-top
        margin = min(48, max(16, min(sw, sh) // 12))
        PW, PH = min(940, sw - 2 * margin), min(720, sh - 2 * margin)
        px, py = left+(sw - PW) // 2, top+(sh - PH) // 2

        self.bg = tk.Toplevel(mgr.root)
        self.bg.overrideredirect(True)
        self.bg.attributes("-topmost", True)
        self.bg.attributes("-alpha", 0.0)
        self.bg.configure(bg="#000000")
        self.bg.geometry(f"{sw}x{sh}+{left}+{top}")
        self.bg.bind("<Button-1>", self._bg_click)
        self._fade(0.0)

        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=t.bg)
        self.win.geometry(f"{PW}x{PH}+{px}+{py}")
        self.win.minsize(min(640, PW), min(520, PH))
        self.win.bind("<Escape>", lambda e: self.close())
        self.PW, self.PH = PW, PH

        self.bg.update_idletasks()
        self.win.lift(self.bg)
        self.win.focus_force()
        self.win.grab_set()

        self._build(t)

    def _fade(self, cur=0.0):
        cur = round(min(0.5, cur + 0.05), 3)
        try: self.bg.attributes("-alpha", cur)
        except: return
        if cur < 0.5: self.bg.after(14, lambda: self._fade(cur))

    def _bg_click(self, e):
        try:
            wx = self.win.winfo_x(); wy = self.win.winfo_y()
            ww = self.win.winfo_width(); wh = self.win.winfo_height()
            if not (wx <= e.x_root <= wx+ww and wy <= e.y_root <= wy+wh):
                self.close()
        except:
            self.close()

    def _build(self, t):
        for w in self.win.winfo_children():
            w.destroy()

        from desktop_widgets.theme import CHROMA
        from desktop_widgets.ui.components import paint_shell, NavItem
        self.win.configure(bg=CHROMA)
        self.win.attributes('-transparentcolor', CHROMA)
        shell = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        shell.pack(fill='both', expand=True)
        paint_shell(shell, self.PW, self.PH, t, 'Settings', self.close)
        self._drag_window(shell)
        body = tk.Frame(self.win, bg=t.bg)
        body.place(x=12, y=72, width=self.PW-20, height=self.PH-80)
        sidebar = tk.Frame(body, bg=t.bg, width=NAV_W)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        self._nav = {}
        self._pages = {}
        for label, key, icon in self.TABS:
            item = NavItem(sidebar, label, icon, lambda k=key: self._switch(k), t,
                           selected=key == self._tab, width=NAV_W - 16)
            item.pack(anchor='w', padx=(4, 0), pady=(0, 4))
            self._nav[key] = item

        content = tk.Frame(body, bg=t.bg)
        content.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(content, bg=t.bg, highlightthickness=0)
        self._canvas.pack(side="left", fill="both", expand=True)
        from desktop_widgets.ui.components import thin_scrollbar
        self._sb_canvas, self._sb_update = thin_scrollbar(content, self._canvas, t, bg=t.bg)
        self._sb_canvas.pack(side="right", fill="y", pady=(0, 12))
        self._scroll_inner = tk.Frame(self._canvas, bg=t.bg)
        self._win_id = self._canvas.create_window((0, 0), window=self._scroll_inner, anchor="nw")
        self._scroll_inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>",       self._on_canvas_configure)
        self.win.bind("<MouseWheel>", self._on_mousewheel)
        self._render_tab(t)
        self._pages[self._tab] = (self._scroll_inner, 0.0)

    def _drag_window(self, cv):
        """The window has no title bar; drag it by its title area."""
        def press(e):
            self._drag = ((e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())
                          if e.y < 64 and e.x < self.PW - 60 else None)
        def move(e):
            if getattr(self, '_drag', None):
                dx, dy = self._drag
                self.win.geometry(f'+{e.x_root-dx}+{e.y_root-dy}')
        cv.bind('<ButtonPress-1>', press, add='+')
        cv.bind('<B1-Motion>', move, add='+')

    def _on_inner_configure(self, e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._update_scrollbar()

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win_id, width=e.width)
        self._update_scrollbar()

    def _on_mousewheel(self, e):
        top, bottom = self._canvas.yview()
        if bottom - top < 1.0:
            self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self._update_scrollbar()

    def _update_scrollbar(self):
        try: self._sb_update()
        except Exception: pass

    def _switch(self, key):
        if key == self._tab:
            return
        self._pages[self._tab] = (self._scroll_inner, self._canvas.yview()[0])
        self._tab = key
        t = config.get_theme(self.mgr.data)
        for name, item in self._nav.items():
            item.set_selected(name == key)
        if key in self._pages:
            self._scroll_inner, self._scroll_pos = self._pages[key]
        else:
            self._scroll_inner = tk.Frame(self._canvas, bg=t.bg)
            self._scroll_inner.bind('<Configure>', self._on_inner_configure)
            self._scroll_pos = 0.0
            self._render_tab(t)
            self._pages[key] = (self._scroll_inner, 0.0)
        self._canvas.itemconfigure(self._win_id, window=self._scroll_inner)
        self._canvas.configure(scrollregion=(0, 0, self._canvas.winfo_width(),
                                            self._scroll_inner.winfo_reqheight()))
        self.win.after_idle(self._restore_scroll)

    def _rebuild(self):
        self.win.unbind("<MouseWheel>")
        try:    self._scroll_pos = self._canvas.yview()[0]
        except: self._scroll_pos = 0.0
        self._build(config.get_theme(self.mgr.data))
        self.win.after(30, self._restore_scroll)
        self.win.after(80, self._restore_scroll)

    def _restore_scroll(self):
        try:
            self._canvas.update_idletasks()
            self._canvas.yview_moveto(self._scroll_pos)
            self._update_scrollbar()
        except: pass

    @staticmethod
    def _card_theme(t):
        """Theme for controls that sit on a card: the card is the surface,
        buttons are one step lighter (darker on light themes)."""
        from desktop_widgets.theme import is_light
        tc = t.copy()
        tc.page = t.bg
        tc.bg = t.btn
        step = '#000000' if is_light(t) else '#ffffff'
        tc.btn = mix(t.btn, step, 0.04)
        tc.btn_h = mix(t.btn, step, 0.08)
        tc.hov = mix(t.btn, step, 0.06)
        return tc

    def _render_tab(self, t):
        title = {'appearance': 'Appearance', 'widgets': 'Widgets', 'system': 'System'}[self._tab]
        tk.Label(self._scroll_inner, text=title, font=TYPE['title'], bg=t.bg, fg=t.txt
                 ).pack(anchor='w', padx=(2, 0), pady=(2, 10))
        t = self._card_theme(t)
        if self._tab == "appearance": self._tab_appearance(t)
        elif self._tab == "widgets":  self._tab_widgets(t)
        elif self._tab == "system":   self._tab_system(t)
        # Scroll to a specific widget row after layout is complete
        if getattr(self, "_scroll_to_widget", None):
            self._canvas.after(80, self._do_scroll_to_widget)

    def _do_scroll_to_widget(self):
        target = getattr(self, "_widget_anchors", {}).get(self._scroll_to_widget)
        if not target:
            return
        try:
            self._scroll_inner.update_idletasks()
            y = target.winfo_rooty() - self._scroll_inner.winfo_rooty()
            total_h = self._scroll_inner.winfo_reqheight()
            frac = max(0.0, min(1.0, y / max(1, total_h)))
            self._canvas.yview_moveto(frac)
            self._scroll_pos = frac
        except Exception:
            pass

    # ── Appearance ─────────────────────────────────────────

    def _tab_appearance(self, t):
        page = self._scroll_inner
        from desktop_widgets.services.screens import CORNERS
        from desktop_widgets.ui.components import OptionButton

        p = self._section(page, t, "Theme")
        pf = tk.Frame(p, bg=t.bg)
        pf.pack(fill="x", padx=16, pady=(14, 8))
        current = self.mgr.data.get("theme_preset", "Dark")
        _preset_swatch_row(pf, t, current, self._apply_preset)

        def choices(parent, options, selected, choose, width=150, cols=4, height=56):
            frame = tk.Frame(parent, bg=t.bg)
            frame.pack(fill='x', padx=16, pady=(4, 14))
            for i, (label, detail, value) in enumerate(options):
                OptionButton(frame, label, detail, lambda v=value: choose(v), t,
                             selected=selected == value, width=width, height=height
                             ).grid(row=i // cols, column=i % cols, padx=(0, 8), pady=(0, 8), sticky='w')

        p = self._section(page, t, "Widgets")
        self._caption(p, t, "Corner style")
        def set_corners(value):
            self.mgr.data["corner_radius"] = value
            config.save(self.mgr.data)
            self.mgr.apply_theme()
            self._rebuild()
        choices(p, [("Square", "", 0), ("Subtle", "", 4), ("Default", "", 8), ("Round", "", 14)],
                config.get_corner_radius(self.mgr.data), set_corners, width=136, height=40)
        self._divider(p, t)
        self._caption(p, t, "Icon size")
        choices(p, [("Small", "36 px", 36), ("Medium", "48 px", 48), ("Large", "64 px", 64)],
                self.mgr.data.get("icon_size", 48), self._set_icon_size, width=184, cols=3)
        self._divider(p, t)
        self._caption(p, t, "Spacing between apps")
        choices(p, [("Compact", "", "compact"), ("Normal", "", "normal"), ("Spacious", "", "spacious")],
                self.mgr.data.get("cell_size", "normal"), self._set_cell_size, width=184, cols=3,
                height=40)

        p = self._section(page, t, "Layout")
        def toggle_resize(on):
            self.mgr.data["resize_enabled"] = on
            config.save(self.mgr.data)
            if not on:
                self.mgr.reset_to_natural_size()
            self.mgr.apply_theme()
        self._setting_row(p, t, "Resize widgets", "Drag a widget's edges and corners to resize it",
                          lambda parent: self._switch_control(parent, t,
                              self.mgr.data.get("resize_enabled", True), toggle_resize))
        self._divider(p, t)
        _global_cols = [5]
        def set_global(v):
            _global_cols[0] = v
            for g in self.mgr.data["groups"]:
                g["cols"] = v; self.mgr.set_group_cols(g["id"], v)
            config.save(self.mgr.data)
        self._setting_row(p, t, "Columns in every folder", "Set all app folders to the same width",
                          lambda parent: _col_stepper(parent, t, lambda: _global_cols[0], set_global,
                                                      min_val=1, max_val=12))
        self._divider(p, t)
        self._caption(p, t, "Position of the + and Settings buttons")
        def choose_corner(value):
            self.mgr.data['tray_corner'] = value
            config.save(self.mgr.data)
            self.mgr.tray_bar.reposition()
            self._rebuild()
        details = {'top_left': 'Near the upper edge', 'top_right': 'Near the upper edge',
                   'bottom_left': 'Above the taskbar', 'bottom_right': 'Above the taskbar'}
        choices(p, [(CORNERS[k], details[k], k) for k in ('top_left', 'top_right', 'bottom_left', 'bottom_right')],
                self.mgr.data.get('tray_corner', 'bottom_right'), choose_corner, width=280, cols=2)

        p = self._section(page, t, "Note font")
        font_frame = tk.Frame(p, bg=t.bg)
        font_frame.pack(fill="x", padx=16, pady=(14, 14))
        cur_font = self.mgr.data.get("ui_font", "Segoe UI")
        for i, f in enumerate(["Segoe UI", "Calibri", "Arial", "Verdana", "Tahoma",
                               "Consolas", "Courier New", "Lucida Console"]):
            _btn(font_frame, f, lambda v=f: self._set_ui_font(v), t,
                 accent=cur_font == f, font=(f, 9), width=134, height=32
                 ).grid(row=i//4, column=i%4, padx=(0, 8), pady=(0, 8), sticky='w')

    # ── Widgets ────────────────────────────────────────────

    def _tab_widgets(self, t):
        page = self._scroll_inner
        sw = self.mgr.root.winfo_screenwidth()
        sh = self.mgr.root.winfo_screenheight()
        self._widget_anchors: dict = {}  # group_id → Frame, for scroll-to

        p = self._section(page, t, "Your desktop")
        self._setting_row(p, t, "Add a widget", "App folders, folder stacks, files, notes, stats and media",
                          lambda parent: _btn(parent, 'Add a widget',
                                              lambda: (self.close(), self.mgr.show_add_picker()),
                                              t, accent=True, icon='add'))
        self._divider(p, t)
        def arrange_controls(parent):
            frame = tk.Frame(parent, bg=t.bg)
            if self.mgr.data.get("arrange_undo"):
                _outline_btn(frame, "Undo", lambda: (self.mgr.undo_auto_arrange(), self._rebuild()), t
                             ).pack(side="left", padx=(0, 8))
            _btn(frame, "Auto arrange", lambda: (self.close(), self.mgr.open_arranger()), t,
                 accent=True, icon="sparkle").pack(side="left")
            return frame
        self._setting_row(p, t, "Auto arrange",
                          "Pick a style and see it on your desktop: tidy up your own layout, "
                          "spread over both sides, one neat block, or a dock along the bottom.", arrange_controls)
        self._divider(p, t)
        undo = self.mgr.data.get("organize_undo")
        def organize_controls(parent):
            frame = tk.Frame(parent, bg=t.bg)
            if undo:
                _outline_btn(frame, "Undo last", lambda: (self.mgr.undo_organize(), self._rebuild()), t
                             ).pack(side="left", padx=(0, 8))
            _btn(frame, "Organize", lambda: (self.close(), self.mgr.open_organizer()), t).pack(side="left")
            return frame
        self._setting_row(p, t, "Organize folders",
                          "Suggests a better folder for misplaced apps and finds duplicates, "
                          "broken shortcuts and empty folders. You review everything first.",
                          organize_controls)

        self._layouts_section(page, t)
        self._launcher_section(page, t)

        if self.mgr.data.get("stacks"):
            p = self._section(page, t, "Folder stacks")
            for st in self.mgr.data["stacks"]:
                self._stack_row(p, t, st)

        loose = [g for g in self.mgr.data["groups"] if g["id"] in self.mgr.wins]
        if loose:
            p = self._section(page, t, "App folders")
            for g in loose:
                self._widget_anchors[g["id"]] = self._widget_row(p, t, g, self.mgr.wins[g["id"]], sw, sh)

        if self.mgr.statsplus_win:
            p = self._section(page, t, "System stats")
            self._statsplus_row(p, t, sw, sh)

        if self.mgr.notes_win or self.mgr.media_win:
            p = self._section(page, t, "Notes and media")
            if self.mgr.notes_win:
                self._simple_widget_row(p, t, "Notes",
                                        lambda: (self.close(), self.mgr.remove_notes()),
                                        detail="Saved automatically as you type")
            if self.mgr.media_win:
                self._simple_widget_row(p, t, "Now playing",
                                        lambda: (self.close(), self.mgr.remove_media()),
                                        kind="media", detail="Controls the music or video that is playing")

        if self.mgr.docs_wins:
            p = self._section(page, t, "File folders")
            for blk in self.mgr.data.get("docs_widgets", []):
                if blk["id"] in self.mgr.docs_wins:
                    self._docs_row(p, t, blk, sw, sh)

    def _row(self, parent, t, kind, name, detail, controls, theme=None, extra=None):
        """One widget in the Widgets tab: icon, name + detail, controls on the
        right, and an optional theme gallery that folds open."""
        from PIL import ImageTk
        from desktop_widgets.ui.drawing import widget_icon
        if parent.winfo_children():
            self._divider(parent, t)
        row = tk.Frame(parent, bg=t.bg)
        row.pack(fill="x", padx=16, pady=12)
        icon = ImageTk.PhotoImage(widget_icon(kind, t.txt, 20), master=row)
        self.__dict__.setdefault("_row_icons", []).append(icon)
        tk.Label(row, image=icon, bg=t.bg).pack(side="left", padx=(2, 14))
        text = tk.Frame(row, bg=t.bg)
        text.pack(side="left")
        tk.Label(text, text=name, font=TYPE["body"], bg=t.bg, fg=t.txt).pack(anchor="w")
        tk.Label(text, text=detail, font=TYPE["caption"], bg=t.bg, fg=t.txt2).pack(anchor="w")
        ctrl = tk.Frame(row, bg=t.bg)
        ctrl.pack(side="right")
        controls(ctrl)
        if extra:
            extra(parent)
        if theme:
            key, current, on_preset = theme
            opened = key in self.__dict__.setdefault("_open_themes", set())
            gallery = tk.Frame(parent, bg=t.bg)
            def fill_gallery():
                # Built on first open: a theme card per preset per widget made Settings slow.
                if gallery.winfo_children():
                    return
                if current != "__global__":
                    _outline_btn(gallery, "Use the global theme", lambda: on_preset("__global__"), t
                                 ).pack(anchor="w", pady=(0, 10))
                _preset_swatch_row(gallery, t, current, on_preset, bg=t.bg)
            def toggle():
                if key in self._open_themes:
                    self._open_themes.discard(key)
                    gallery.pack_forget()
                else:
                    self._open_themes.add(key)
                    fill_gallery()
                    gallery.pack(fill="x", padx=52, pady=(0, 12), after=row)
            label = "Theme: " + ("Global" if current == "__global__" else current)
            first = ctrl.winfo_children()[0] if ctrl.winfo_children() else None
            _outline_btn(ctrl, label, toggle, t).pack(
                side="left", padx=(0, 8), **({"before": first} if first else {}))
            if opened:
                fill_gallery()
                gallery.pack(fill="x", padx=52, pady=(0, 12), after=row)
        return row

    def _theme_choice(self, blk, widget):
        """(current preset, setter) for a widget's own theme override."""
        def on_preset(name):
            if name == "__global__":
                blk["theme_override"] = None
            else:
                blk["theme_override"] = {**self._preset_theme(name).to_dict(), "__preset__": name}
            config.save(self.mgr.data)
            if widget:
                widget.redraw()
            self._rebuild()
        current = (blk.get("theme_override") or {}).get("__preset__", "__global__")
        return current, on_preset

    def _widget_row(self, parent, t, g, gw, sw, sh):
        def get_cols(gid=g["id"]):
            grp = next((x for x in self.mgr.data["groups"] if x["id"] == gid), g)
            return grp.get("cols", 5)
        def set_cols(v, gid=g["id"]):
            self.mgr.set_group_cols(gid, v)
            gw.redraw()
        def controls(ctrl):
            _col_stepper(ctrl, t, get_cols, set_cols, min_val=1, max_val=12).pack(side="left", padx=(0, 8))
            _outline_btn(ctrl, "Rename", lambda: self._rename_widget(g), t).pack(side="left", padx=(0, 8))
            _outline_btn(ctrl, "Remove", lambda: (self.close(), self.mgr.delete_group(g["id"])),
                         t, danger=True).pack(side="left")
        n = len(g.get("apps", []))
        current, on_preset = self._theme_choice(g, gw)
        return self._row(parent, t, "folder", g["name"],
                         f"{n} app{'s' if n != 1 else ''} · {get_cols()} columns",
                         controls, theme=(("group", g["id"]), current, on_preset))

    def _layouts_section(self, page, t):
        import time as _time
        p = self._section(page, t, "Layouts")
        self._setting_row(p, t, "Save this arrangement",
                          "Positions, open widgets, collapsed widgets and the theme. "
                          "Switch from the + bar or the quick launcher.",
                          lambda parent: _btn(parent, "Save layout",
                                              lambda: (self.mgr.save_layout_dialog(), self._rebuild()),
                                              t, accent=True, icon="add"))
        active = self.mgr.data.get("active_layout")
        for layout in self.mgr.data.get("layouts", []):
            self._divider(p, t)
            name = layout["name"]
            when = _time.strftime("%d %b %Y", _time.localtime(layout.get("saved", 0)))
            detail = f"Saved {when}" + ("  ·  In use" if name == active else "")
            def controls(parent, n=name):
                frame = tk.Frame(parent, bg=t.bg)
                _outline_btn(frame, "Switch", lambda: (self.mgr.apply_layout(n), self._rebuild()), t
                             ).pack(side="left", padx=(0, 8))
                _outline_btn(frame, "Update", lambda: (self.mgr.save_layout(n), self._rebuild()), t
                             ).pack(side="left", padx=(0, 8))
                _outline_btn(frame, "Rename", lambda: (self.mgr.rename_layout(n), self._rebuild()), t
                             ).pack(side="left", padx=(0, 8))
                _outline_btn(frame, "Delete", lambda: (self.mgr.delete_layout(n), self._rebuild()), t,
                             danger=True).pack(side="left")
                return frame
            self._setting_row(p, t, name, detail, controls)

    def _launcher_section(self, page, t):
        from desktop_widgets.services.hotkey import SHORTCUTS
        p = self._section(page, t, "Quick launcher")
        current = self.mgr.data.get("launcher_hotkey", "Ctrl+Alt+Space")
        hotkey = getattr(self.mgr, "hotkey", None)
        if current == "Off":
            detail = "Turned off. Pick a shortcut to search and open anything from anywhere."
        elif hotkey is not None and not hotkey.ok:
            detail = f"{current} is in use by another app. Pick a different shortcut."
        else:
            detail = f"Press {current} anywhere, type a few letters and press Enter."
        self._setting_row(p, t, "Shortcut", detail, None)
        chips = tk.Frame(p, bg=t.bg)
        chips.pack(fill="x", padx=16, pady=(0, 14))
        def choose(label):
            self.mgr.set_launcher_hotkey(label)
            self._rebuild()
        for label in list(SHORTCUTS) + ["Off"]:
            _btn(chips, label, lambda l=label: choose(l), t, accent=label == current,
                 font=TYPE["label"], padx=12, pady=5, pill=True).pack(side="left", padx=(0, 6))

    def _stack_row(self, parent, t, st):
        def controls(ctrl):
            _col_stepper(ctrl, t, lambda: st.get("cols", 5),
                         lambda v: self.mgr.set_stack_cols(st["id"], v),
                         min_val=1, max_val=12).pack(side="left", padx=(0, 8))
            _outline_btn(ctrl, "Rename", lambda: (self.mgr.rename_stack(st), self._rebuild()),
                         t).pack(side="left", padx=(0, 8))
            _outline_btn(ctrl, "Unstack", lambda: (self.mgr.unstack(st["id"]), self._rebuild()),
                         t).pack(side="left")
        names = [g["name"] for gid in st["groups"] for g in self.mgr.data["groups"] if g["id"] == gid]
        detail = " · ".join(names) if len(" · ".join(names)) < 60 else f"{len(names)} folders"
        current, on_preset = self._theme_choice(st, self.mgr.stack_wins.get(st["id"]))
        for gid in st["groups"]:
            self._widget_anchors[gid] = None
        row = self._row(parent, t, "stack", st["name"], detail, controls,
                        theme=(("stack", st["id"]), current, on_preset))
        for gid in st["groups"]:
            self._widget_anchors[gid] = row
        return row

    def _simple_widget_row(self, parent, t, label, on_remove, kind="notes", detail=""):
        def controls(ctrl):
            _outline_btn(ctrl, "Remove", on_remove, t, danger=True).pack(side="left")
        return self._row(parent, t, kind, label, detail, controls)

    def _statsplus_row(self, parent, t, sw, sh):
        blk = self.mgr.data.setdefault("statsplus", {})
        from desktop_widgets.widgets.statsplus_widget import MIN_COLS, MAX_COLS, DEF_COLS, ALL_METRICS
        def set_sp_cols(v):
            if self.mgr.statsplus_win:
                self.mgr.statsplus_win.set_cols(v)
        def controls(ctrl):
            _col_stepper(ctrl, t, lambda: blk.get("cols", DEF_COLS), set_sp_cols,
                         min_val=MIN_COLS, max_val=MAX_COLS).pack(side="left", padx=(0, 8))
            _outline_btn(ctrl, "Remove", lambda: (self.close(), self.mgr.remove_statsplus()),
                         t, danger=True).pack(side="left")
        active = blk.setdefault("metrics", ["cpu_pct", "cpu_temp", "ram_pct", "gpu_pct", "gpu_temp"])
        def metrics(parent):
            self._divider(parent, t)
            tk.Label(parent, text="Shown metrics — the first one gets the large graph",
                     font=TYPE["caption"], bg=t.bg, fg=t.txt2).pack(anchor="w", padx=52, pady=(10, 8))
            rows = [tk.Frame(parent, bg=t.bg) for _ in range(2)]
            for i, line in enumerate(rows):
                line.pack(fill="x", padx=50, pady=(0, 12 if i else 0))
            for i, (key, label, *_) in enumerate(ALL_METRICS):
                def toggle(k=key):
                    m = self.mgr.data["statsplus"]["metrics"]
                    if k in m:
                        m.remove(k)
                    else:
                        m.append(k)
                    config.save(self.mgr.data)
                    if self.mgr.statsplus_win:
                        self.mgr.statsplus_win.redraw()
                    self._rebuild()
                _btn(rows[i // 6], label, toggle, t, accent=key in active, font=TYPE["label"],
                     padx=12, pady=5, pill=True).pack(side="left", padx=(0, 6), pady=3)
        return self._row(parent, t, "statsplus", "System stats",
                         f"{len(active)} metrics · {blk.get('cols', DEF_COLS)} columns",
                         controls, extra=metrics)

    def _docs_row(self, parent, t, blk, sw, sh):
        def get_dcols(did=blk["id"]):
            b = next((x for x in self.mgr.data.get("docs_widgets", []) if x["id"] == did), blk)
            return b.get("cols", 3)
        def controls(ctrl):
            _col_stepper(ctrl, t, get_dcols, lambda v: self.mgr.set_docs_cols(blk["id"], v),
                         min_val=1, max_val=8).pack(side="left", padx=(0, 8))
            _outline_btn(ctrl, "Rename", lambda: (self.mgr.rename_docs(blk), self._rebuild()),
                         t).pack(side="left", padx=(0, 8))
            _outline_btn(ctrl, "Remove", lambda: (self.close(), self.mgr.delete_docs(blk["id"])),
                         t, danger=True).pack(side="left")
        n = len(blk.get("files", []))
        current, on_preset = self._theme_choice(blk, self.mgr.docs_wins.get(blk["id"]))
        return self._row(parent, t, "docs", blk["name"],
                         f"{n} file{'s' if n != 1 else ''} · {get_dcols()} columns",
                         controls, theme=(("docs", blk["id"]), current, on_preset))

    # ── System ─────────────────────────────────────────────

    def _tab_system(self, t):
        from desktop_widgets.utils import task_exists, create_task, remove_task
        import sys, os
        page = self._scroll_inner

        p = self._section(page, t, "Startup")
        holder = [None]
        status_text = tk.StringVar(value="Checking…")
        def control(parent):
            frame = tk.Frame(parent, bg=t.bg)
            tk.Label(frame, textvariable=status_text, font=TYPE['caption'], bg=t.bg,
                     fg=t.txt2).pack(side='left', padx=(0, 12))
            holder[0] = tk.Frame(frame, bg=t.bg)
            holder[0].pack(side='left')
            return frame
        self._setting_row(p, t, "Start with Windows", "Open your widgets automatically when you sign in",
                          control)
        state = [False]
        from concurrent.futures import ThreadPoolExecutor
        def run_job(job, complete):
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(job)
            pool.shutdown(wait=False)
            def poll():
                if not holder[0].winfo_exists(): return
                if not future.done():
                    self.mgr.root.after(100, poll)
                    return
                try: complete(future.result())
                except Exception:
                    status_text.set('Could not change this. Try again.')
            self.mgr.root.after(100, poll)
        def show_state(enabled):
            state[0] = enabled
            status_text.set('')
            for child in holder[0].winfo_children(): child.destroy()
            self._switch_control(holder[0], t, enabled, lambda on: toggle()).pack()
        def toggle():
            status_text.set('Updating…')
            exe = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))}"'
            def complete(ok):
                show_state(not state[0] if ok else state[0])
                if not ok: status_text.set('Windows could not change this.')
            run_job(remove_task if state[0] else lambda: create_task(exe), complete)
        run_job(task_exists, show_state)

        p = self._section(page, t, "Data")
        self._setting_row(p, t, "Your widgets and settings", config.DATA_FILE,
                          lambda parent: _outline_btn(parent, "Open folder",
                                                      lambda: os.startfile(config.DATA_DIR), t))

        p = self._section(page, t, "About")
        self._setting_row(p, t, f"DesktopWidget {VERSION}",
                          "Updates are checked at startup. You choose when to install them.",
                          None)

    # ── Helpers ────────────────────────────────────────────

    def _section(self, page, t, title):
        """A heading on the page and a rounded card under it.
        Returns the frame the section's rows go into."""
        from desktop_widgets.ui.drawing import rounded_rect
        page_bg = page.cget("bg")
        tk.Label(page, text=title, font=TYPE["strong"], bg=page_bg, fg=t.txt
                 ).pack(anchor="w", padx=(2, 0), pady=(10, 6))
        cv = tk.Canvas(page, bg=page_bg, highlightthickness=0, height=40)
        cv.pack(fill="x", padx=(0, 12), pady=(0, 8))
        inner = tk.Frame(cv, bg=t.bg)
        win = cv.create_window(1, 1, window=inner, anchor="nw")
        size = [0, 0]
        def layout(_=None):
            w, h = cv.winfo_width(), inner.winfo_reqheight() + 2
            if [w, h] == size or w <= 1:
                return
            size[:] = [w, h]
            cv.configure(height=h)
            cv.itemconfigure(win, width=w - 2)
            cv.delete("card")
            item = rounded_rect(cv, 0, 0, w, h, R_PANEL, fill=t.bg, outline=t.border)
            cv.addtag_withtag("card", item)
            cv.tag_lower("card")
        pending = [None]
        def schedule(_=None):
            if pending[0] is None:
                pending[0] = cv.after_idle(lambda: (pending.__setitem__(0, None), layout()))
        cv.bind("<Configure>", schedule)
        inner.bind("<Configure>", schedule)
        return inner

    def _setting_row(self, parent, t, title, detail, control):
        """Title and description on the left, a control on the right."""
        row = tk.Frame(parent, bg=t.bg)
        row.pack(fill="x", padx=16, pady=12)
        text = tk.Frame(row, bg=t.bg)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, font=TYPE["body"], bg=t.bg, fg=t.txt).pack(anchor="w")
        if detail:
            tk.Label(text, text=detail, font=TYPE["caption"], bg=t.bg, fg=t.txt2,
                     wraplength=380, justify="left").pack(anchor="w")
        if control:
            control(row).pack(side="right")
        return row

    def _caption(self, parent, t, text):
        tk.Label(parent, text=text, font=TYPE["body"], bg=t.bg, fg=t.txt
                 ).pack(anchor="w", padx=16, pady=(12, 8))

    def _divider(self, parent, t):
        tk.Frame(parent, bg=getattr(t, 'page', t.border), height=1).pack(fill="x")

    def _switch_control(self, parent, t, on, command):
        from desktop_widgets.ui.components import ToggleSwitch
        return ToggleSwitch(parent, t, on, command)

    def _rename_widget(self, g: dict) -> None:
        self.mgr.rename_group(g); self._rebuild()

    @staticmethod
    def _preset_theme(name):
        if name == "Wallpaper":
            from desktop_widgets.services import wallpaper
            return wallpaper.theme() or PRESETS["Dark"]
        return PRESETS[name]

    def _apply_preset(self, name: str) -> None:
        preset = self._preset_theme(name)
        self.mgr.data["theme"] = preset.to_dict()
        self.mgr.data["theme_preset"] = name
        config.save(self.mgr.data)
        self.mgr.apply_theme(); self._rebuild()

    def _set_icon_size(self, val):
        self.mgr.data["icon_size"] = val
        import desktop_widgets.theme as th, desktop_widgets.utils as utils
        th.apply_sizes(self.mgr.data); utils._CACHE.clear()
        config.save(self.mgr.data)
        for gw in list(self.mgr.wins.values()) + list(self.mgr.stack_wins.values()):
            gw._refresh_size(); gw.redraw()
        self._rebuild()

    def _set_cell_size(self, val):
        self.mgr.data["cell_size"] = val
        import desktop_widgets.theme as th
        th.apply_sizes(self.mgr.data)
        config.save(self.mgr.data)
        for gw in list(self.mgr.wins.values()) + list(self.mgr.stack_wins.values()):
            gw._refresh_size(); gw.redraw()
        self._rebuild()

    def _set_ui_font(self, font_name: str) -> None:
        self.mgr.data["ui_font"] = font_name
        self.mgr.data.setdefault("theme", {})["stat_font"] = font_name
        config.save(self.mgr.data)
        import desktop_widgets.theme as th
        th.active.stat_font = font_name
        self.mgr.apply_theme()
        if self.mgr.notes_win and self.mgr.notes_win._text_widget:
            self.mgr.notes_win._text_widget.configure(font=(th.ui_font(self.mgr.data), 10))
        self._rebuild()

    def close(self):
        try: self.win.unbind("<MouseWheel>")
        except: pass
        try: self.win.grab_release()
        except: pass
        try: self.bg.destroy()
        except: pass
        try: self.win.destroy()
        except: pass
        self.mgr.settings_screen = None
