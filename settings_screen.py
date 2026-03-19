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
from theme import Theme, PRESETS, HDR_H
import config

if TYPE_CHECKING:
    from manager import Manager


def _btn(parent, text, command, t, accent=False, danger=False, **kw):
    """Flash-free flat button."""
    if danger:
        bg = "#3a2020"; fg = "#ff6b6b"; abg = "#4a2828"
    elif accent:
        bg = t.accent; abg = t.accent
        # Pick text color based on accent luminance so it's always readable
        try:
            c = t.accent.lstrip("#")
            r, g, b = int(c[0:2],16), int(c[2:4],16), int(c[4:6],16)
            fg = "#000000" if (r*299 + g*587 + b*114) / 1000 > 160 else "#ffffff"
        except Exception:
            fg = "white"
    else:
        bg = kw.pop("bg", t.btn); fg = kw.pop("fg", t.txt)
        abg = t.btn_h
    return tk.Button(parent, text=text, command=command,
                     bg=bg, fg=fg, activebackground=abg, activeforeground=fg,
                     relief="flat", bd=0, cursor="hand2", **kw)


def _preset_swatch_row(parent, t, current_name, on_select, bg=None):
    """Render compact rows of preset swatches. All slots fixed width."""
    _bg     = bg or t.bg
    names   = list(PRESETS.keys())
    PER_ROW = 6
    SW_W, SW_H = 40, 26
    COL_W   = 52   # fixed column width — label never pushes swatch around

    for row_start in range(0, len(names), PER_ROW):
        row_frame = tk.Frame(parent, bg=_bg)
        row_frame.pack(anchor="w", pady=(0, 2))
        for name in names[row_start:row_start + PER_ROW]:
            preset = PRESETS[name]
            is_sel = name == current_name

            # Fixed-width column so every slot is the same size
            col = tk.Frame(row_frame, bg=_bg, width=COL_W)
            col.pack_propagate(False)
            col.pack(side="left")

            swatch = tk.Frame(col, bg=preset.bg, width=SW_W, height=SW_H,
                              highlightbackground=t.accent if is_sel else t.border,
                              highlightthickness=2 if is_sel else 1,
                              cursor="hand2")
            swatch.place(relx=0.5, rely=0.0, anchor="n", y=2)

            dot = tk.Frame(swatch, bg=preset.accent, width=8, height=3)
            dot.place(relx=0.5, rely=0.82, anchor="center")

            short = name if len(name) <= 9 else name[:8] + "…"
            tk.Label(col, text=short, font=("Segoe UI", 6),
                     bg=_bg, fg=t.txt if is_sel else t.txt2,
                     anchor="center").place(relx=0.5, rely=1.0, anchor="s", y=-1)

            col.config(height=SW_H + 16)
            swatch.bind("<Button-1>", lambda e, n=name: on_select(n))
            dot.bind("<Button-1>",    lambda e, n=name: on_select(n))



class SettingsScreen:
    TABS = [
        ("🎨  Appearance", "appearance"),
        ("🗂  Widgets",    "widgets"),
        ("⚙  System",     "system"),
    ]

    def __init__(self, mgr: "Manager") -> None:
        self.mgr = mgr
        self._tab = "appearance"
        self._scroll_pos = 0.0
        t = config.get_theme(mgr.data)
        sw = mgr.root.winfo_screenwidth()
        sh = mgr.root.winfo_screenheight()
        PW, PH = 620, 560
        px, py = (sw - PW) // 2, (sh - PH) // 2

        # Backdrop
        self.bg = tk.Toplevel(mgr.root)
        self.bg.overrideredirect(True)
        self.bg.attributes("-topmost", False)
        self.bg.attributes("-alpha", 0.0)
        self.bg.configure(bg="#000000")
        self.bg.geometry(f"{sw}x{sh}+0+0")
        self.bg.bind("<Button-1>", self._bg_click)
        self._fade(0.0)

        # Panel
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", False)
        self.win.configure(bg=t.bg)
        self.win.geometry(f"{PW}x{PH}+{px}+{py}")
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
        for w in self.win.winfo_children():
            w.destroy()

        # ── Header ──────────────────────────────────────────
        hdr = tk.Frame(self.win, bg=t.hdr, height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="Settings", font=("Segoe UI", 13, "bold"),
                 bg=t.hdr, fg=t.txt).pack(side="left", padx=20, pady=12)

        # Close — tk.Label, zero system flash
        close_lbl = tk.Label(hdr, text="✕", font=("Segoe UI", 12),
                             bg=t.hdr, fg=t.txt2, cursor="hand2", padx=14, pady=10)
        close_lbl.pack(side="right")
        close_lbl.bind("<Enter>",          lambda e: close_lbl.config(bg="#2a1515", fg="#ff5555"))
        close_lbl.bind("<Leave>",          lambda e: close_lbl.config(bg=t.hdr,    fg=t.txt2))
        close_lbl.bind("<ButtonRelease-1>", lambda e: self.close())

        tk.Frame(self.win, bg=t.border, height=1).pack(fill="x")

        # ── Tab bar — tk.Label per tab, zero system flash ───
        tab_bar = tk.Frame(self.win, bg=t.hdr)
        tab_bar.pack(fill="x")
        for label, key in self.TABS:
            is_active = key == self._tab
            fg  = t.txt  if is_active else t.txt2
            bg  = t.bg   if is_active else t.hdr
            hbg = t.btn_h                           # hover bg for inactive
            lbl = tk.Label(tab_bar, text=label,
                           font=("Segoe UI", 9, "bold" if is_active else "normal"),
                           bg=bg, fg=fg, cursor="hand2", padx=20, pady=10)
            lbl.pack(side="left")
            if not is_active:
                lbl.bind("<Enter>", lambda e, l=lbl: l.config(bg=hbg, fg=t.txt))
                lbl.bind("<Leave>", lambda e, l=lbl, b=bg, f=fg: l.config(bg=b, fg=f))
            lbl.bind("<ButtonRelease-1>", lambda e, k=key: self._switch(k))

        tk.Frame(self.win, bg=t.border, height=1).pack(fill="x")

        # ── Scrollable area with custom thin scrollbar ──────
        outer = tk.Frame(self.win, bg=t.bg)
        outer.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(outer, bg=t.bg, highlightthickness=0)
        self._canvas.pack(side="left", fill="both", expand=True)

        # Custom scrollbar: just a canvas on the right
        SB_W = 6
        self._sb_canvas = tk.Canvas(outer, width=SB_W, bg=t.hdr,
                                    highlightthickness=0)
        self._sb_canvas.pack(side="right", fill="y")
        self._sb_thumb = None

        self._scroll_inner = tk.Frame(self._canvas, bg=t.bg)
        self._win_id = self._canvas.create_window(
            (0, 0), window=self._scroll_inner, anchor="nw")

        self._scroll_inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>",       self._on_canvas_configure)

        # Mousewheel on every widget in the panel
        self.win.bind_all("<MouseWheel>", self._on_mousewheel)

        # Scrollbar drag
        self._sb_canvas.bind("<ButtonPress-1>",   self._sb_press)
        self._sb_canvas.bind("<B1-Motion>",        self._sb_drag)
        self._sb_canvas.bind("<ButtonRelease-1>",  self._sb_release)
        self._sb_drag_y = None

        self._render_tab(t)

    def _on_inner_configure(self, e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._canvas.itemconfig(self._win_id,
                                width=self._canvas.winfo_width())
        self._update_scrollbar()

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win_id, width=e.width)
        self._update_scrollbar()

    def _on_mousewheel(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self._update_scrollbar()

    def _update_scrollbar(self):
        try:
            top, bot = self._canvas.yview()
        except Exception:
            return
        h = self._sb_canvas.winfo_height()
        if h <= 1: return
        self._sb_canvas.delete("thumb")
        if bot - top >= 1.0:
            return  # content fits, hide thumb
        ty  = int(top * h)
        by  = int(bot * h)
        t   = config.get_theme(self.mgr.data)
        self._sb_canvas.create_rectangle(
            1, ty, 5, by, fill=t.border, outline="", tags="thumb")

    # ── Scrollbar drag ──────────────────────────────────────

    def _sb_press(self, e):
        self._sb_drag_y = e.y

    def _sb_drag(self, e):
        if self._sb_drag_y is None: return
        h = self._sb_canvas.winfo_height()
        if h <= 1: return
        dy = (e.y - self._sb_drag_y) / h
        self._sb_drag_y = e.y
        self._canvas.yview_moveto(self._canvas.yview()[0] + dy)
        self._update_scrollbar()

    def _sb_release(self, e):
        self._sb_drag_y = None

    def _switch(self, key):
        self.win.unbind_all("<MouseWheel>")
        self._tab = key
        self._scroll_pos = 0.0          # tab switch → always go to top
        self._build(config.get_theme(self.mgr.data))

    def _rebuild(self):
        self.win.unbind_all("<MouseWheel>")
        try:
            self._scroll_pos = self._canvas.yview()[0]
        except Exception:
            self._scroll_pos = 0.0
        self._build(config.get_theme(self.mgr.data))
        # Two-step restore: first pass lets tkinter lay out the inner frame,
        # second pass actually moves the view once scrollregion is correct.
        self.win.after(30,  self._restore_scroll)
        self.win.after(80,  self._restore_scroll)

    def _restore_scroll(self):
        try:
            self._canvas.update_idletasks()
            self._canvas.yview_moveto(self._scroll_pos)
            self._update_scrollbar()
        except Exception:
            pass

    def _render_tab(self, t):
        if self._tab == "appearance": self._tab_appearance(t)
        elif self._tab == "widgets":  self._tab_widgets(t)
        elif self._tab == "system":   self._tab_system(t)

    # ── Appearance ─────────────────────────────────────────

    def _tab_appearance(self, t):
        p = self._scroll_inner
        PAD = 20

        self._section(p, t, "Color Preset")
        pf = tk.Frame(p, bg=t.bg)
        pf.pack(fill="x", padx=PAD, pady=(4, 12))
        current = self.mgr.data.get("theme_preset", "Dark Blue")
        _preset_swatch_row(pf, t, current, self._apply_preset)

        self._section(p, t, "Icon Size")
        icon_frame = tk.Frame(p, bg=t.bg)
        icon_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        cur_icon = self.mgr.data.get("icon_size", 52)
        for label, val in [("Small", 36), ("Medium", 52), ("Large", 68)]:
            is_sel = cur_icon == val
            _btn(icon_frame, label, lambda v=val: self._set_icon_size(v), t,
                 accent=is_sel, padx=16, pady=6).pack(side="left", padx=4)

        self._section(p, t, "Cell Size")
        cell_frame = tk.Frame(p, bg=t.bg)
        cell_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        cur_cell = self.mgr.data.get("cell_size", "normal")
        for label, val in [("Compact", "compact"), ("Normal", "normal"), ("Spacious", "spacious")]:
            is_sel = cur_cell == val
            _btn(cell_frame, label, lambda v=val: self._set_cell_size(v), t,
                 accent=is_sel, padx=16, pady=6).pack(side="left", padx=4)

        self._section(p, t, "UI Font")
        font_frame = tk.Frame(p, bg=t.bg)
        font_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        cur_font = self.mgr.data.get("ui_font", "Segoe UI")
        for f in ["Segoe UI", "Calibri", "Arial", "Verdana", "Tahoma",
                  "Consolas", "Courier New", "Lucida Console"]:
            is_sel = cur_font == f
            _btn(font_frame, f, lambda v=f: self._set_ui_font(v), t,
                 accent=is_sel, font=(f, 9), padx=12, pady=5
                 ).pack(side="left", padx=4, pady=2)

        self._section(p, t, "Widget Resize")
        resize_frame = tk.Frame(p, bg=t.bg)
        resize_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        resize_on = self.mgr.data.get("resize_enabled", True)
        tk.Label(resize_frame,
                 text="Drag edges/corners to resize widgets" if resize_on
                      else "Widgets are fixed size — drag header to move",
                 font=("Segoe UI", 8), bg=t.bg, fg=t.txt2).pack(side="left", padx=(0,12))
        def _toggle_resize():
            new_val = not self.mgr.data.get("resize_enabled", True)
            self.mgr.data["resize_enabled"] = new_val
            config.save(self.mgr.data)
            if not new_val:
                self.mgr.reset_to_natural_size()
            self._rebuild()
        _btn(resize_frame,
             "Disable Resize" if resize_on else "Enable Resize",
             _toggle_resize, t,
             accent=resize_on, padx=14, pady=6).pack(side="left")

    # ── Widgets ────────────────────────────────────────────

    def _tab_widgets(self, t):
        p = self._scroll_inner
        PAD = 20
        sw = self.mgr.root.winfo_screenwidth()
        sh = self.mgr.root.winfo_screenheight()

        self._section(p, t, "Add Widget")
        add_frame = tk.Frame(p, bg=t.bg)
        add_frame.pack(fill="x", padx=PAD, pady=(4, 12))
        for label, cmd in [
            ("+ App folder",   lambda: (self.close(), self.mgr.new_group_dialog())),
            ("+ Stats+",       lambda: (self.close(), self.mgr.toggle_statsplus())),
            ("+ Notes",        lambda: (self.close(), self.mgr.toggle_notes())),
            ("+ Files widget", lambda: (self.close(), self.mgr.new_docs_dialog())),
        ]:
            _btn(add_frame, label, cmd, t, padx=10, pady=6).pack(
                side="left", padx=3, pady=2)

        self._section(p, t, "App Folders")
        for g in self.mgr.data["groups"]:
            gw = self.mgr.wins.get(g["id"])
            if not gw: continue
            self._widget_row(p, t, g, gw, sw, sh)

        # Stats+
        if self.mgr.statsplus_win:
            self._section(p, t, "Stats+")
            self._statsplus_row(p, t, sw, sh)

        # Notes
        if self.mgr.notes_win:
            self._section(p, t, "Notes")
            self._simple_widget_row(p, t, "📝 Notes",
                                    lambda: (self.close(), self.mgr.remove_notes()))

        # Docs widgets
        if self.mgr.docs_wins:
            self._section(p, t, "Files Widgets")
            for blk in self.mgr.data.get("docs_widgets", []):
                if blk["id"] in self.mgr.docs_wins:
                    self._docs_row(p, t, blk, sw, sh)

        # Media / Now Playing
        if self.mgr.media_win:
            self._section(p, t, "Media")
            self._simple_widget_row(p, t, "🎵 Media",
                                    lambda: (self.close(), self.mgr.remove_media()))

    def _widget_row(self, parent, t, g, gw, sw, sh):
        frame = tk.Frame(parent, bg=t.btn, pady=2)
        frame.pack(fill="x", padx=20, pady=3)
        tk.Label(frame, text=f"📁  {g['name']}",
                 font=("Segoe UI", 10, "bold"),
                 bg=t.btn, fg=t.txt).pack(side="left", padx=12, pady=6)
        bf = tk.Frame(frame, bg=t.btn)
        bf.pack(side="right", padx=8)

        def center(w=gw):
            cx = (sw - w.W) // 2; cy = (sh - w.H) // 2
            w.win.geometry(f"+{cx}+{cy}")
            w.group["x"] = cx; w.group["y"] = cy
            config.save(self.mgr.data)

        _btn(bf, "✎ Rename", lambda g=g: self._rename_widget(g), t,
             padx=8, pady=4).pack(side="left", padx=2)
        _btn(bf, "⊕ Center", center, t,
             padx=8, pady=4).pack(side="left", padx=2)
        _btn(bf, "✕", lambda gid=g["id"]: (self.close(), self.mgr.delete_group(gid)),
             t, danger=True, padx=8, pady=4).pack(side="left", padx=2)

        # ── Column picker ───────────────────────────────────
        cf = tk.Frame(parent, bg=t.hdr)
        cf.pack(fill="x", padx=20, pady=(0, 2))
        col_row = tk.Frame(cf, bg=t.hdr)
        col_row.pack(fill="x", padx=8, pady=(6, 4))
        tk.Label(col_row, text="Columns:", font=("Segoe UI", 8),
                 bg=t.hdr, fg=t.txt2).pack(side="left", padx=(0, 6))
        cur_cols = g.get("cols", 5)
        for n in range(1, 13):
            is_sel = cur_cols == n
            def _set_cols(c=n, gid=g["id"]):
                self.mgr.set_group_cols(gid, c)
                self._rebuild()
            _btn(col_row, str(n), _set_cols, t,
                 accent=is_sel, padx=8, pady=3).pack(side="left", padx=1)

        # ── Per-widget preset override ──────────────────────
        tf = tk.Frame(parent, bg=t.hdr)
        tf.pack(fill="x", padx=20, pady=(0, 6))

        def on_preset(name, gid=g["id"]):
            g2 = next((x for x in self.mgr.data["groups"] if x["id"] == gid), None)
            if g2 is None: return
            if name == "__global__":
                g2["theme_override"] = None
            else:
                g2["theme_override"] = PRESETS[name].to_dict()
                g2["theme_override"]["__preset__"] = name
            config.save(self.mgr.data)
            w = self.mgr.wins.get(gid)
            if w: w.redraw()
            self._rebuild()

        ov = g.get("theme_override") or {}
        cur_ov = ov.get("__preset__", "__global__")

        hdr_row = tk.Frame(tf, bg=t.hdr)
        hdr_row.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(hdr_row, text="Widget theme:", font=("Segoe UI", 8),
                 bg=t.hdr, fg=t.txt2).pack(side="left")
        if cur_ov != "__global__":
            _btn(hdr_row, "Reset to global",
                 lambda gid=g["id"]: on_preset("__global__", gid),
                 t, font=("Segoe UI", 8), padx=6, pady=2).pack(side="right")

        # "Global" swatch
        global_row = tk.Frame(tf, bg=t.hdr)
        global_row.pack(fill="x", padx=8, pady=(0, 2))
        is_global = cur_ov == "__global__"
        gb = tk.Frame(global_row, bg=t.hdr)
        gb.pack(side="left", padx=3)
        gswatch = tk.Frame(gb,
                           bg=t.bg, width=46, height=30,
                           highlightbackground=t.accent if is_global else t.border,
                           highlightthickness=2 if is_global else 1,
                           cursor="hand2")
        gswatch.pack()
        gdot = tk.Frame(gswatch, bg=t.accent, width=10, height=3)
        gdot.place(relx=0.5, rely=0.85, anchor="center")
        tk.Label(gb, text="Global", font=("Segoe UI", 7),
                 bg=t.hdr, fg=t.txt if is_global else t.txt2).pack(pady=1)
        gswatch.bind("<Button-1>", lambda e, gid=g["id"]: on_preset("__global__", gid))

        # All presets
        pf = tk.Frame(tf, bg=t.hdr)
        pf.pack(fill="x", padx=8, pady=(0, 6))
        _preset_swatch_row(pf, t, cur_ov,
                           lambda name, gid=g["id"]: on_preset(name, gid),
                           bg=t.hdr)

    def _simple_widget_row(self, parent, t, label, on_remove):
        frame = tk.Frame(parent, bg=t.btn, pady=2)
        frame.pack(fill="x", padx=20, pady=3)
        tk.Label(frame, text=label, font=("Segoe UI", 10, "bold"),
                 bg=t.btn, fg=t.txt).pack(side="left", padx=12, pady=6)
        _btn(frame, "✕ Remove", on_remove, t, danger=True, padx=8, pady=4
             ).pack(side="right", padx=8)

    def _statsplus_row(self, parent, t, sw, sh):
        frame = tk.Frame(parent, bg=t.btn, pady=2)
        frame.pack(fill="x", padx=20, pady=3)
        tk.Label(frame, text="📊 Stats+", font=("Segoe UI", 10, "bold"),
                 bg=t.btn, fg=t.txt).pack(side="left", padx=12, pady=6)
        _btn(frame, "✕ Remove",
             lambda: (self.close(), self.mgr.remove_statsplus()),
             t, danger=True, padx=8, pady=4).pack(side="right", padx=8)

        cf = tk.Frame(parent, bg=t.hdr)
        cf.pack(fill="x", padx=20, pady=(0, 6))

        # ── Columns (width) control ──────────────────────────
        tk.Label(cf, text="Columns:", font=("Segoe UI", 8),
                 bg=t.hdr, fg=t.txt2).pack(anchor="w", padx=8, pady=(6, 2))
        col_f = tk.Frame(cf, bg=t.hdr)
        col_f.pack(fill="x", padx=8, pady=(0, 4))
        blk = self.mgr.data.setdefault("statsplus", {})
        from statsplus_widget import MIN_COLS, MAX_COLS, DEF_COLS
        cur_cols = blk.get("cols", DEF_COLS)
        for n in range(MIN_COLS, MAX_COLS + 1):
            is_sel = cur_cols == n
            def set_cols(c=n):
                if self.mgr.statsplus_win:
                    self.mgr.statsplus_win.set_cols(c)
                self._rebuild()
            _btn(col_f, str(n), set_cols, t, accent=is_sel,
                 padx=14, pady=4).pack(side="left", padx=2)

        # ── Metric toggles ───────────────────────────────────
        tk.Label(cf, text="Visible metrics:", font=("Segoe UI", 8),
                 bg=t.hdr, fg=t.txt2).pack(anchor="w", padx=8, pady=(4, 2))
        mf = tk.Frame(cf, bg=t.hdr)
        mf.pack(fill="x", padx=8, pady=(0, 6))

        active = blk.setdefault("metrics", ["cpu_pct", "cpu_temp", "ram_pct",
                                            "gpu_pct", "gpu_temp"])
        from statsplus_widget import ALL_METRICS
        for key, label, *_ in ALL_METRICS:
            is_on = key in active
            def toggle(k=key):
                m = self.mgr.data["statsplus"]["metrics"]
                if k in m: m.remove(k)
                else: m.append(k)
                config.save(self.mgr.data)
                if self.mgr.statsplus_win:
                    self.mgr.statsplus_win.redraw()
                self._rebuild()
            _btn(mf, label, toggle, t, accent=is_on, padx=8, pady=4
                 ).pack(side="left", padx=2, pady=2)

    def _docs_row(self, parent, t, blk, sw, sh):
        frame = tk.Frame(parent, bg=t.btn, pady=2)
        frame.pack(fill="x", padx=20, pady=3)
        tk.Label(frame, text=f"📁  {blk['name']}",
                 font=("Segoe UI", 10, "bold"),
                 bg=t.btn, fg=t.txt).pack(side="left", padx=12, pady=6)
        bf = tk.Frame(frame, bg=t.btn)
        bf.pack(side="right", padx=8)
        _btn(bf, "✎ Rename",
             lambda b=blk: (self.mgr.rename_docs(b), self._rebuild()),
             t, padx=8, pady=4).pack(side="left", padx=2)
        _btn(bf, "✕",
             lambda did=blk["id"]: (self.close(), self.mgr.delete_docs(did)),
             t, danger=True, padx=8, pady=4).pack(side="left", padx=2)

        # Column picker
        col_frame = tk.Frame(parent, bg=t.hdr)
        col_frame.pack(fill="x", padx=20, pady=(0, 2))
        col_row = tk.Frame(col_frame, bg=t.hdr)
        col_row.pack(fill="x", padx=8, pady=(6, 4))
        tk.Label(col_row, text="Columns:", font=("Segoe UI", 8),
                 bg=t.hdr, fg=t.txt2).pack(side="left", padx=(0, 6))
        cur_cols = blk.get("cols", 3)
        for n in range(1, 9):
            is_sel = cur_cols == n
            def _set_dcols(c=n, did=blk["id"]):
                self.mgr.set_docs_cols(did, c)
                self._rebuild()
            _btn(col_row, str(n), _set_dcols, t,
                 accent=is_sel, padx=8, pady=3).pack(side="left", padx=1)

        # Per-widget preset override
        cf = tk.Frame(parent, bg=t.hdr)
        cf.pack(fill="x", padx=20, pady=(0, 6))

        def on_preset(name, did=blk["id"]):
            b = next((x for x in self.mgr.data.get("docs_widgets", [])
                      if x["id"] == did), None)
            if b is None: return
            if name == "__global__":
                b["theme_override"] = None
            else:
                b["theme_override"] = {**PRESETS[name].to_dict(), "__preset__": name}
            config.save(self.mgr.data)
            dw = self.mgr.docs_wins.get(did)
            if dw: dw.redraw()
            self._rebuild()

        ov = blk.get("theme_override") or {}
        cur_ov = ov.get("__preset__", "__global__")
        hdr_row = tk.Frame(cf, bg=t.hdr); hdr_row.pack(fill="x", padx=8, pady=(6,2))
        tk.Label(hdr_row, text="Widget theme:", font=("Segoe UI", 8),
                 bg=t.hdr, fg=t.txt2).pack(side="left")
        if cur_ov != "__global__":
            _btn(hdr_row, "Reset to global",
                 lambda did=blk["id"]: on_preset("__global__", did),
                 t, font=("Segoe UI", 8), padx=6, pady=2).pack(side="right")
        pf = tk.Frame(cf, bg=t.hdr); pf.pack(fill="x", padx=8, pady=(0, 6))
        _preset_swatch_row(pf, t, cur_ov,
                           lambda name, did=blk["id"]: on_preset(name, did),
                           bg=t.hdr)

    # ── System ─────────────────────────────────────────────

    def _tab_system(self, t):
        from utils import task_exists, create_task, remove_task
        import sys, os
        p = self._scroll_inner
        PAD = 20

        self._section(p, t, "Auto-start with Windows")
        has_task = task_exists()
        tk.Label(p, text="✓  Enabled" if has_task else "✗  Disabled",
                 font=("Segoe UI", 9), bg=t.bg,
                 fg=t.ok if has_task else t.txt2).pack(anchor="w", padx=PAD, pady=(4,8))

        def toggle():
            if task_exists(): remove_task()
            else:
                exe = sys.executable if getattr(sys,"frozen",False) \
                      else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                create_task(exe)
            self._rebuild()

        _btn(p, "Disable" if has_task else "Enable auto-start", toggle, t,
             accent=not has_task, padx=16, pady=7
             ).pack(anchor="w", padx=PAD)

        self._section(p, t, "Data")
        tk.Label(p, text=f"Saved to:  {config.DATA_FILE}",
                 font=("Segoe UI", 8), bg=t.bg, fg=t.txt2).pack(
                 anchor="w", padx=PAD, pady=(4,0))

        self._section(p, t, "About")
        tk.Label(p, text="Desktop Widget\nPython + tkinter",
                 font=("Segoe UI", 9), bg=t.bg, fg=t.txt2,
                 justify="left").pack(anchor="w", padx=PAD, pady=(4,0))

    # ── Helpers ────────────────────────────────────────────

    def _section(self, parent, t, title):
        bg = parent.cget("bg")
        f = tk.Frame(parent, bg=bg)
        f.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(f, text=title, font=("Segoe UI", 10, "bold"),
                 bg=bg, fg=t.txt).pack(side="left")
        tk.Frame(f, bg=t.border, height=1).pack(
            side="left", fill="x", expand=True, padx=(10, 0), pady=5)

    def _rename_widget(self, g: dict) -> None:
        self.mgr.rename_group(g)
        self._rebuild()

    def _apply_preset(self, name: str) -> None:
        preset = PRESETS[name]
        self.mgr.data["theme"] = preset.to_dict()
        self.mgr.data["theme_preset"] = name
        config.save(self.mgr.data)
        self.mgr.apply_theme()
        self._rebuild()

    def _set_icon_size(self, val):
        self.mgr.data["icon_size"] = val
        import theme as th, utils
        th.ICON_SZ = val
        utils._CACHE.clear()
        config.save(self.mgr.data)
        for gw in self.mgr.wins.values():
            gw._refresh_size(); gw.redraw()
        self._rebuild()

    def _set_cell_size(self, val):
        self.mgr.data["cell_size"] = val
        import theme as th
        cw, ch, pad = {"compact":(72,74,10),"normal":(88,90,14),"spacious":(104,108,18)}[val]
        th.CELL_W = cw; th.CELL_H = ch; th.PAD = pad
        config.save(self.mgr.data)
        for gw in self.mgr.wins.values():
            gw._refresh_size(); gw.redraw()
        self._rebuild()

    def _set_ui_font(self, font_name: str) -> None:
        """Apply font universally — stored in data and pushed to theme + notes widget."""
        self.mgr.data["ui_font"] = font_name
        # Also update stat_font in theme so stats widgets pick it up
        self.mgr.data.setdefault("theme", {})["stat_font"] = font_name
        config.save(self.mgr.data)
        # Push to theme module so all widgets get it on next redraw
        import theme as th
        th.active.stat_font = font_name
        # Redraw everything
        self.mgr.apply_theme()
        # Update notes widget font live if open
        if self.mgr.notes_win and self.mgr.notes_win._text_widget:
            self.mgr.notes_win._text_widget.configure(font=(font_name, 10))
        self._rebuild()

    def close(self):
        try: self.win.unbind_all("<MouseWheel>")
        except: pass
        try: self.win.grab_release()
        except: pass
        try: self.bg.destroy()
        except: pass
        try: self.win.destroy()
        except: pass
        self.mgr.settings_screen = None