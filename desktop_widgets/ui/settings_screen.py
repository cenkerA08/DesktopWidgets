"""
settings_screen.py — Full-screen settings overlay.
Tabs: Appearance | Widgets | System
- Preset-only theming (no custom color picker)
- Per-widget preset override
- No white button flashes (tk.Label for all header/tab controls)
- Custom thin scrollbar, mousewheel scrolling
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from desktop_widgets.theme import Theme, PRESETS, HDR_H, TYPE, R_PANEL
import desktop_widgets.config as config
from desktop_widgets.version import VERSION

if TYPE_CHECKING:
    from desktop_widgets.manager import Manager


def _btn(parent, text, command, t, accent=False, danger=False, **kw):
    """Flash-free flat button."""
    from desktop_widgets.ui.components import RoundedButton
    if danger:
        kw['fg'] = t.danger
    return RoundedButton(parent, text, command, t, accent=accent, **kw)


def _outline_btn(parent, text, command, t, danger=False, **kw):
    """Small rounded secondary button (rename, remove)."""
    from desktop_widgets.ui.components import RoundedButton
    if danger:
        kw['fg'] = t.danger
    kw.setdefault('font', TYPE['label'])
    return RoundedButton(parent, text, command, t, **kw)


def _flat_slider(parent, t, from_val: int, to_val: int, initial: int, command):
    """Canvas-based flat slider that matches the app's dark UI style."""
    H, TRACK_H, THUMB_R = 20, 4, 7
    val = [max(from_val, min(to_val, initial))]

    cv = tk.Canvas(parent, height=H, bg=t.bg, highlightthickness=0, cursor="hand2")

    def _draw(w=None):
        cv.delete("all")
        w = w or cv.winfo_width()
        if w <= 1:
            return
        pad = THUMB_R + 1
        track_w = w - 2 * pad
        y = H // 2
        frac = (val[0] - from_val) / max(1, to_val - from_val)
        tx = pad + frac * track_w
        # Empty track
        cv.create_rectangle(pad, y - TRACK_H // 2, w - pad, y + TRACK_H // 2,
                            fill=t.border, outline="")
        # Filled portion
        cv.create_rectangle(pad, y - TRACK_H // 2, tx, y + TRACK_H // 2,
                            fill=t.accent, outline="")
        # Thumb
        cv.create_oval(tx - THUMB_R, y - THUMB_R, tx + THUMB_R, y + THUMB_R,
                       fill=t.accent, outline="")

    def _set(x):
        w = cv.winfo_width()
        pad = THUMB_R + 1
        frac = max(0.0, min(1.0, (x - pad) / max(1, w - 2 * pad)))
        v = round(from_val + frac * (to_val - from_val))
        v = max(from_val, min(to_val, v))
        if v != val[0]:
            val[0] = v
            command(v)
        _draw()

    cv.bind("<Configure>",  lambda e: _draw(e.width))
    cv.bind("<Button-1>",   lambda e: _set(e.x))
    cv.bind("<B1-Motion>",  lambda e: _set(e.x))
    return cv


def _col_stepper(parent, t, get_val, set_val, min_val=1, max_val=12):
    """Rounded < n > pill; click either half to step."""
    from desktop_widgets.ui.drawing import rounded_rect
    W, H = 92, 32
    cv = tk.Canvas(parent, width=W, height=H, bg=parent.cget("bg"),
                   highlightthickness=0, cursor="hand2")
    def draw(hover=None):
        cv.delete("all")
        rounded_rect(cv, 0, 0, W, H, H // 2, fill=t.btn,
                     outline=t.accent if hover else t.border)
        for x, glyph, side in ((16, "\u2039", "left"), (W - 16, "\u203a", "right")):
            cv.create_text(x, H // 2 - 1, text=glyph, font=("Segoe UI", 12),
                           fill=t.txt if hover == side else t.txt2)
        cv.create_text(W // 2, H // 2, text=str(get_val()), font=TYPE["header"], fill=t.txt)
    def click(e):
        v = max(min_val, min(max_val, get_val() + (-1 if e.x < W // 2 else 1)))
        if v != get_val():
            set_val(v)
        draw("left" if e.x < W // 2 else "right")
    # Redraws come from <Motion>/<Button>, never <Enter>, so no hover loop.
    cv.bind("<Motion>", lambda e: draw("left" if e.x < W // 2 else "right"))
    cv.bind("<Leave>", lambda e: draw())
    cv.bind("<Button-1>", click)
    draw()
    return cv


def _preset_swatch_row(parent, t, current_name, on_select, bg=None):
    from desktop_widgets.ui.components import theme_picker
    theme_picker(parent, t, current_name, on_select, bg)


class SettingsScreen:
    TABS = [
        ("🎨  Appearance", "appearance"),
        ("🗂  Widgets",    "widgets"),
        ("⚙  System",     "system"),
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
        PW, PH = min(900, sw - 2 * margin), min(720, sh - 2 * margin)
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
        cur = round(min(0.6, cur + 0.05), 3)
        try: self.bg.attributes("-alpha", cur)
        except: return
        if cur < 0.6: self.bg.after(14, lambda: self._fade(cur))

    def _bg_click(self, e):
        try:
            wx = self.win.winfo_x(); wy = self.win.winfo_y()
            ww = self.win.winfo_width(); wh = self.win.winfo_height()
            if not (wx <= e.x_root <= wx+ww and wy <= e.y_root <= wy+wh):
                self.close()
        except:
            self.close()

    def _build(self, t):
        import desktop_widgets.theme as _th
        for w in self.win.winfo_children():
            w.destroy()

        from desktop_widgets.theme import CHROMA
        from desktop_widgets.ui.components import paint_shell, RoundedButton
        self.win.configure(bg=CHROMA)
        self.win.attributes('-transparentcolor', CHROMA)
        shell = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        shell.pack(fill='both', expand=True)
        paint_shell(shell, self.PW, self.PH, t, 'Make it yours', self.close, 'SETTINGS',
                    glows=[(t.accent, 0.15), (t.up_col, 0.9)])
        body = tk.Frame(self.win, bg=t.bg)
        body.place(x=30, y=110, width=self.PW-60, height=self.PH-134)
        sidebar = tk.Frame(body, bg=t.bg, width=132)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        self._nav = {}
        self._pages = {}
        for label, key in [('Appearance', 'appearance'), ('Widgets', 'widgets'), ('System', 'system')]:
            button = RoundedButton(sidebar, label, lambda k=key: self._switch(k), t,
                                   accent=key == self._tab, width=120, height=44)
            button.pack(anchor='w', pady=(0, 8))
            self._nav[key] = button

        content = tk.Frame(body, bg=t.bg)
        content.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(content, bg=t.bg, highlightthickness=0)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._sb_canvas = tk.Canvas(content, width=6, bg=t.hdr, highlightthickness=0)
        self._sb_canvas.pack(side="right", fill="y")
        self._scroll_inner = tk.Frame(self._canvas, bg=t.bg)
        self._win_id = self._canvas.create_window((0, 0), window=self._scroll_inner, anchor="nw")
        self._scroll_inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>",       self._on_canvas_configure)
        self.win.bind("<MouseWheel>", self._on_mousewheel)
        self._sb_canvas.bind("<ButtonPress-1>",  self._sb_press)
        self._sb_canvas.bind("<B1-Motion>",       self._sb_drag)
        self._sb_canvas.bind("<ButtonRelease-1>", self._sb_release)
        self._sb_drag_y = None
        self._render_tab(t)
        self._pages[self._tab] = (self._scroll_inner, 0.0)

    def _on_inner_configure(self, e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._update_scrollbar()

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win_id, width=e.width)
        self._update_scrollbar()

    def _on_mousewheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self._update_scrollbar()

    def _update_scrollbar(self):
        try: top, bot = self._canvas.yview()
        except: return
        h = self._sb_canvas.winfo_height()
        if h <= 1: return
        self._sb_canvas.delete("thumb")
        if bot - top >= 1.0: return
        t = config.get_theme(self.mgr.data)
        self._sb_canvas.create_rectangle(1, int(top*h), 5, int(bot*h),
                                          fill=t.border, outline="", tags="thumb")

    def _sb_press(self, e):   self._sb_drag_y = e.y
    def _sb_release(self, e): self._sb_drag_y = None
    def _sb_drag(self, e):
        if self._sb_drag_y is None: return
        h = self._sb_canvas.winfo_height()
        if h <= 1: return
        dy = (e.y - self._sb_drag_y) / h
        self._sb_drag_y = e.y
        self._canvas.yview_moveto(self._canvas.yview()[0] + dy)
        self._update_scrollbar()

    def _switch(self, key):
        if key == self._tab:
            return
        self._pages[self._tab] = (self._scroll_inner, self._canvas.yview()[0])
        self._tab = key
        t = config.get_theme(self.mgr.data)
        for name, button in self._nav.items():
            button.set_selected(name == key)
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
        from desktop_widgets.ui.tiles import _mix
        tc = t.copy()
        tc.bg = t.btn
        tc.btn = '#%02x%02x%02x' % _mix(t.btn, t.txt, 0.07)
        tc.btn_h = '#%02x%02x%02x' % _mix(t.btn_h, t.txt, 0.07)
        tc.hov = '#%02x%02x%02x' % _mix(t.hov, t.txt, 0.07)
        return tc

    def _render_tab(self, t):
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
        p = self._section(page, t, '+ and settings position')
        corners = tk.Frame(p, bg=t.bg)
        corners.pack(fill='x', padx=20, pady=(4, 12))
        for i, key in enumerate(('top_left', 'top_right', 'bottom_left', 'bottom_right')):
            def choose(value=key):
                self.mgr.data['tray_corner'] = value
                config.save(self.mgr.data)
                self.mgr.tray_bar.reposition()
                self._rebuild()
            detail = {'top_left': 'Near the upper edge', 'top_right': 'Near the upper edge',
                      'bottom_left': 'Above the taskbar', 'bottom_right': 'Above the taskbar'}[key]
            OptionButton(corners, CORNERS[key], detail, choose, t,
                         selected=self.mgr.data.get('tray_corner', 'bottom_right') == key
                         ).grid(row=i//2, column=i%2, padx=4, pady=4, sticky='w')
        PAD = 20

        p = self._section(page, t, "Workspace themes")
        pf = tk.Frame(p, bg=t.bg)
        pf.pack(fill="x", padx=PAD, pady=(4, 12))
        current = self.mgr.data.get("theme_preset", "Graphite")
        _preset_swatch_row(pf, t, current, self._apply_preset)

        p = self._section(page, t, "Card corners")
        corner_row = tk.Frame(p, bg=t.bg)
        corner_row.pack(fill="x", padx=PAD, pady=(6, 16))
        def set_corners(value):
            self.mgr.data["corner_radius"] = value
            config.save(self.mgr.data)
            self.mgr.apply_theme()
            self._rebuild()
        for label, value in (("Square", 0), ("Soft", 10), ("Rounded", 16), ("Extra round", 24)):
            OptionButton(corner_row, label, 'Corner style', lambda v=value: set_corners(v), t,
                         selected=config.get_corner_radius(self.mgr.data) == value,
                         width=142).pack(side="left", padx=(0, 6))

        p = self._section(page, t, "Icon Size")
        icon_frame = tk.Frame(p, bg=t.bg)
        icon_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        cur_icon = self.mgr.data.get("icon_size", 52)
        for label, val in [("Small", 36), ("Medium", 52), ("Large", 68)]:
            is_sel = cur_icon == val
            OptionButton(icon_frame, label, f'{val} px icons',
                         lambda v=val: self._set_icon_size(v), t,
                         selected=is_sel, width=164).pack(side="left", padx=4)

        p = self._section(page, t, "Cell Size")
        cell_frame = tk.Frame(p, bg=t.bg)
        cell_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        cur_cell = self.mgr.data.get("cell_size", "normal")
        for label, val in [("Compact", "compact"), ("Normal", "normal"), ("Spacious", "spacious")]:
            is_sel = cur_cell == val
            OptionButton(cell_frame, label, 'App tile spacing',
                         lambda v=val: self._set_cell_size(v), t,
                         selected=is_sel, width=164).pack(side="left", padx=4)

        p = self._section(page, t, "UI Font")
        font_frame = tk.Frame(p, bg=t.bg)
        font_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        cur_font = self.mgr.data.get("ui_font", "Segoe UI")
        for i, f in enumerate(["Segoe UI", "Calibri", "Arial", "Verdana", "Tahoma",
                               "Consolas", "Courier New", "Lucida Console"]):
            is_sel = cur_font == f
            _btn(font_frame, f, lambda v=f: self._set_ui_font(v), t,
                 accent=is_sel, font=(f, 9), width=140, height=38
                 ).grid(row=i//4, column=i%4, padx=4, pady=4, sticky='w')

        p = self._section(page, t, "Widget Resize")
        resize_frame = tk.Frame(p, bg=t.bg)
        resize_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        resize_on = self.mgr.data.get("resize_enabled", True)
        tk.Label(resize_frame,
                 text="Drag edges/corners to resize widgets" if resize_on
                      else "Widgets are fixed size — drag header to move",
                 font=("Segoe UI", 8), bg=t.bg, fg=t.txt2).pack(side="left", padx=(0, 12))
        def _toggle_resize():
            new_val = not self.mgr.data.get("resize_enabled", True)
            self.mgr.data["resize_enabled"] = new_val
            config.save(self.mgr.data)
            if not new_val: self.mgr.reset_to_natural_size()
            self._rebuild()
        _btn(resize_frame, "Disable Resize" if resize_on else "Enable Resize",
             _toggle_resize, t, accent=resize_on, padx=14, pady=6).pack(side="left")

        p = self._section(page, t, "Default Columns (All Folders)")
        gcol_frame = tk.Frame(p, bg=t.bg)
        gcol_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        gf_row = tk.Frame(gcol_frame, bg=t.bg)
        gf_row.pack(anchor="w")
        tk.Label(gf_row, text="Apply to all folders at once:",
                 font=("Segoe UI", 8), bg=t.bg, fg=t.txt2).pack(side="left", padx=(0,10))
        _global_cols = [5]
        def get_global(): return _global_cols[0]
        def set_global(v):
            _global_cols[0] = v
            for g in self.mgr.data["groups"]:
                g["cols"] = v; self.mgr.set_group_cols(g["id"], v)
            config.save(self.mgr.data)
        _col_stepper(gf_row, t, get_global, set_global, min_val=1, max_val=12).pack(side="left")

    # ── Widgets ────────────────────────────────────────────

    def _tab_widgets(self, t):
        import desktop_widgets.theme as _th
        page = self._scroll_inner
        PAD = 20
        sw = self.mgr.root.winfo_screenwidth()
        sh = self.mgr.root.winfo_screenheight()
        self._widget_anchors: dict = {}  # group_id → Frame, for scroll-to

        p = self._section(page, t, "Your desktop")
        _btn(p, '+  Add a widget', lambda: (self.close(), self.mgr.show_add_picker()),
             t, accent=True, padx=18, pady=10).pack(anchor='w', padx=PAD, pady=(8, 20))

        p = self._section(page, t, "App folders")
        for g in self.mgr.data["groups"]:
            gw = self.mgr.wins.get(g["id"])
            if not gw: continue
            self._widget_anchors[g["id"]] = self._widget_row(p, t, g, gw, sw, sh)

        # Stats+
        if self.mgr.statsplus_win:
            p = self._section(page, t, "System stats")
            self._statsplus_row(p, t, sw, sh)

        # Notes
        if self.mgr.notes_win:
            p = self._section(page, t, "Notes")
            self._simple_widget_row(p, t, "Notes",
                                    lambda: (self.close(), self.mgr.remove_notes()),
                                    detail="Saved automatically")

        # Docs widgets
        if self.mgr.docs_wins:
            p = self._section(page, t, "File folders")
            for blk in self.mgr.data.get("docs_widgets", []):
                if blk["id"] in self.mgr.docs_wins:
                    self._docs_row(p, t, blk, sw, sh)

    def _row(self, parent, t, kind, name, detail, controls, theme=None, extra=None):
        """One widget in the Widgets tab: icon, name + detail, rounded controls,
        and an optional theme gallery that folds open."""
        from PIL import ImageTk
        from desktop_widgets.ui.drawing import widget_icon
        if len(parent.winfo_children()) > 1:      # first child is the card label
            tk.Frame(parent, bg=t.border, height=1).pack(fill="x", padx=10, pady=(2, 8))
        row = tk.Frame(parent, bg=t.bg)
        row.pack(fill="x", padx=10, pady=(4, 6))
        icon = ImageTk.PhotoImage(widget_icon(kind, t.accent, 26), master=row)
        self.__dict__.setdefault("_row_icons", []).append(icon)
        tk.Label(row, image=icon, bg=t.bg).pack(side="left", padx=(0, 12))
        text = tk.Frame(row, bg=t.bg)
        text.pack(side="left")
        tk.Label(text, text=name, font=TYPE["header"], bg=t.bg, fg=t.txt).pack(anchor="w")
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
                # Built on first open: 20 theme cards per widget made Settings slow.
                if gallery.winfo_children():
                    return
                if current != "__global__":
                    _btn(gallery, "Use the global theme", lambda: on_preset("__global__"), t,
                         font=TYPE["label"], padx=12, pady=6).pack(anchor="w", pady=(0, 8))
                _preset_swatch_row(gallery, t, current, on_preset, bg=t.bg)
            def toggle():
                if key in self._open_themes:
                    self._open_themes.discard(key)
                    gallery.pack_forget()
                else:
                    self._open_themes.add(key)
                    fill_gallery()
                    gallery.pack(fill="x", padx=10, pady=(4, 8), after=row)
            label = "Theme: " + ("Global" if current == "__global__" else current)
            first = ctrl.winfo_children()[0] if ctrl.winfo_children() else None
            _btn(ctrl, label, toggle, t, font=TYPE["label"], padx=12, pady=6).pack(
                side="left", padx=(0, 6), **({"before": first} if first else {}))
            if opened:
                fill_gallery()
                gallery.pack(fill="x", padx=10, pady=(4, 8), after=row)
        return row

    def _theme_choice(self, blk, widget):
        """(current preset, setter) for a widget's own theme override."""
        def on_preset(name):
            if name == "__global__":
                blk["theme_override"] = None
            else:
                blk["theme_override"] = {**PRESETS[name].to_dict(), "__preset__": name}
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
            _col_stepper(ctrl, t, get_cols, set_cols, min_val=1, max_val=12).pack(side="left", padx=(0, 6))
            _outline_btn(ctrl, "Rename", lambda: self._rename_widget(g), t,
                         padx=12, pady=6).pack(side="left", padx=(0, 6))
            _outline_btn(ctrl, "Remove", lambda: (self.close(), self.mgr.delete_group(g["id"])),
                         t, danger=True, padx=12, pady=6).pack(side="left")
        n = len(g.get("apps", []))
        current, on_preset = self._theme_choice(g, gw)
        return self._row(parent, t, "folder", g["name"],
                         f"{n} app{'s' if n != 1 else ''} · {get_cols()} columns",
                         controls, theme=(("group", g["id"]), current, on_preset))

    def _simple_widget_row(self, parent, t, label, on_remove, kind="notes", detail=""):
        def controls(ctrl):
            _outline_btn(ctrl, "Remove", on_remove, t, danger=True, padx=12, pady=6).pack(side="left")
        return self._row(parent, t, kind, label, detail, controls)

    def _statsplus_row(self, parent, t, sw, sh):
        blk = self.mgr.data.setdefault("statsplus", {})
        from desktop_widgets.widgets.statsplus_widget import MIN_COLS, MAX_COLS, DEF_COLS, ALL_METRICS
        def set_sp_cols(v):
            if self.mgr.statsplus_win:
                self.mgr.statsplus_win.set_cols(v)
        def controls(ctrl):
            _col_stepper(ctrl, t, lambda: blk.get("cols", DEF_COLS), set_sp_cols,
                         min_val=MIN_COLS, max_val=MAX_COLS).pack(side="left", padx=(0, 6))
            _outline_btn(ctrl, "Remove", lambda: (self.close(), self.mgr.remove_statsplus()),
                         t, danger=True, padx=12, pady=6).pack(side="left")
        active = blk.setdefault("metrics", ["cpu_pct", "cpu_temp", "ram_pct", "gpu_pct", "gpu_temp"])
        def metrics(parent):
            tk.Label(parent, text="Shown metrics (the first one gets the big graph)",
                     font=TYPE["caption"], bg=t.bg, fg=t.txt2).pack(anchor="w", padx=48, pady=(2, 4))
            rows = [tk.Frame(parent, bg=t.bg) for _ in range(2)]
            for i, line in enumerate(rows):
                line.pack(fill="x", padx=44, pady=(0, 8 if i else 0))
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
                     padx=10, pady=5).pack(side="left", padx=3, pady=3)
        return self._row(parent, t, "statsplus", "System stats",
                         f"{len(active)} metrics · {blk.get('cols', DEF_COLS)} columns",
                         controls, extra=metrics)

    def _docs_row(self, parent, t, blk, sw, sh):
        def get_dcols(did=blk["id"]):
            b = next((x for x in self.mgr.data.get("docs_widgets", []) if x["id"] == did), blk)
            return b.get("cols", 3)
        def controls(ctrl):
            _col_stepper(ctrl, t, get_dcols, lambda v: self.mgr.set_docs_cols(blk["id"], v),
                         min_val=1, max_val=8).pack(side="left", padx=(0, 6))
            _outline_btn(ctrl, "Rename", lambda: (self.mgr.rename_docs(blk), self._rebuild()),
                         t, padx=12, pady=6).pack(side="left", padx=(0, 6))
            _outline_btn(ctrl, "Remove", lambda: (self.close(), self.mgr.delete_docs(blk["id"])),
                         t, danger=True, padx=12, pady=6).pack(side="left")
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
        PAD = 20
        p = self._section(page, t, "Auto-start with Windows")
        status = tk.Label(p, text='Checking auto-start…', font=('Segoe UI', 9), bg=t.bg, fg=t.txt2)
        status.pack(anchor='w', padx=PAD, pady=(4, 8))
        controls = tk.Frame(p, bg=t.bg)
        controls.pack(anchor='w', padx=PAD)
        state = [False]
        from concurrent.futures import ThreadPoolExecutor
        def run_job(job, complete):
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(job)
            pool.shutdown(wait=False)
            def poll():
                if not status.winfo_exists(): return
                if not future.done():
                    self.mgr.root.after(100, poll)
                    return
                try: complete(future.result())
                except Exception:
                    status.configure(text='Could not change auto-start. Try again.')
            self.mgr.root.after(100, poll)
        def show_state(enabled):
            state[0] = enabled
            status.configure(text='Enabled' if enabled else 'Disabled', fg=t.ok if enabled else t.txt2)
            for child in controls.winfo_children(): child.destroy()
            _btn(controls, 'Disable' if enabled else 'Enable auto-start', toggle, t,
                 accent=not enabled).pack()
        def toggle():
            for child in controls.winfo_children(): child.destroy()
            status.configure(text='Updating auto-start…')
            exe = sys.executable if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))}"'
            def complete(ok):
                show_state(not state[0] if ok else state[0])
                if not ok: status.configure(text='Windows could not change auto-start. Try again.')
            run_job(remove_task if state[0] else lambda: create_task(exe), complete)
        run_job(task_exists, show_state)
        p = self._section(page, t, "Data")
        tk.Label(p, text=f"Saved to:  {config.DATA_FILE}",
                 font=("Segoe UI", 8), bg=t.bg, fg=t.txt2).pack(
                 anchor="w", padx=PAD, pady=(4,0))
        p = self._section(page, t, "Updates")
        tk.Label(p, text="Updates are checked at startup. You choose whether to download, install, and restart.",
                 font=("Segoe UI", 8), bg=t.bg, fg=t.txt2,
                 wraplength=460, justify="left").pack(anchor="w", padx=PAD, pady=(4,0))
        p = self._section(page, t, "About")
        tk.Label(p, text=f"DesktopWidget {VERSION}\nPython + tkinter",
                 font=("Segoe UI", 9), bg=t.bg, fg=t.txt2,
                 justify="left").pack(anchor="w", padx=PAD, pady=(4,0))

    # ── Helpers ────────────────────────────────────────────

    def _section(self, page, t, title):
        """A rounded card with a dot + capitalised label, like the widget cards.
        Returns the frame the section's controls go into."""
        from desktop_widgets.ui.drawing import rounded_rect
        page_bg = page.cget("bg")
        cv = tk.Canvas(page, bg=page_bg, highlightthickness=0, height=60)
        cv.pack(fill="x", padx=(0, 12), pady=(0, 12))
        inner = tk.Frame(cv, bg=t.bg)
        win = cv.create_window(10, 12, window=inner, anchor="nw")
        head = tk.Frame(inner, bg=t.bg)
        head.pack(fill="x", padx=10, pady=(4, 2))
        dot = tk.Canvas(head, width=8, height=8, bg=t.bg, highlightthickness=0)
        dot.create_oval(1, 1, 7, 7, fill=t.accent, outline="")
        dot.pack(side="left", padx=(0, 8))
        tk.Label(head, text=title.upper(), font=TYPE["meta"], bg=t.bg, fg=t.txt2).pack(side="left")
        size = [0, 0]
        def layout(_=None):
            w, h = cv.winfo_width(), inner.winfo_reqheight() + 26
            if [w, h] == size or w <= 1:
                return
            size[:] = [w, h]
            cv.configure(height=h)
            cv.itemconfigure(win, width=w - 20)
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

    def _rename_widget(self, g: dict) -> None:
        self.mgr.rename_group(g); self._rebuild()

    def _apply_preset(self, name: str) -> None:
        preset = PRESETS[name]
        self.mgr.data["theme"] = preset.to_dict()
        self.mgr.data["theme_preset"] = name
        config.save(self.mgr.data)
        self.mgr.apply_theme(); self._rebuild()

    def _set_icon_size(self, val):
        self.mgr.data["icon_size"] = val
        import desktop_widgets.theme as th, desktop_widgets.utils as utils
        th.apply_sizes(self.mgr.data); utils._CACHE.clear()
        config.save(self.mgr.data)
        for gw in self.mgr.wins.values():
            gw._refresh_size(); gw.redraw()
        self._rebuild()

    def _set_cell_size(self, val):
        self.mgr.data["cell_size"] = val
        import desktop_widgets.theme as th
        th.apply_sizes(self.mgr.data)
        config.save(self.mgr.data)
        for gw in self.mgr.wins.values():
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
            self.mgr.notes_win._text_widget.configure(font=(font_name, 10))
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
