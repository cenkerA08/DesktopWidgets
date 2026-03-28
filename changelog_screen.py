"""
changelog_screen.py — Post-update what's new screen.
Shown once on first launch after an update.
"""
from __future__ import annotations
import tkinter as tk
import theme as _th
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manager import Manager


class ChangelogScreen:
    def __init__(self, mgr: "Manager", version: str, notes: list[str]) -> None:
        self.mgr = mgr

        import config
        t  = config.get_theme(mgr.data)
        sw = mgr.root.winfo_screenwidth()
        sh = mgr.root.winfo_screenheight()
        PW, PH = 480, 360 + max(0, len(notes) - 4) * 28
        px, py = (sw - PW) // 2, (sh - PH) // 2

        # Backdrop
        self.bg = tk.Toplevel(mgr.root)
        self.bg.overrideredirect(True)
        self.bg.attributes("-topmost", False)
        self.bg.attributes("-alpha", 0.0)
        self.bg.configure(bg="#000000")
        self.bg.geometry(f"{sw}x{sh}+0+0")
        self._fade(0.0)

        # Panel
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", False)
        self.win.configure(bg=t.bg)
        self.win.geometry(f"{PW}x{PH}+{px}+{py}")
        self.win.bind("<Escape>", lambda e: self._close())

        self._built_t = t

        self.bg.update_idletasks()
        self.win.lift(self.bg)
        self.win.focus_force()
        self.win.grab_set()

        mgr.overlay_screen = self
        self._build(t, version, notes)

    # ── Fade ───────────────────────────────────────────────

    def _fade(self, cur=0.0):
        cur = round(min(0.55, cur + 0.05), 3)
        try: self.bg.attributes("-alpha", cur)
        except: return
        if cur < 0.55: self.bg.after(14, lambda: self._fade(cur))

    # ── Build ──────────────────────────────────────────────

    def _build(self, t, version: str, notes: list[str]):
        # ── Header ────────────────────────────────────────
        hdr = tk.Frame(self.win, bg=t.hdr)
        hdr.pack(fill="x")

        tk.Label(hdr, text="🎉  Updated!",
                 font=("Segoe UI", 13, "bold"),
                 bg=t.hdr, fg=t.txt, padx=20, pady=14).pack(side="left")

        ver_lbl = tk.Label(hdr, text=f"v{version}",
                           font=("Segoe UI", 9),
                           bg=t.accent, fg="white",
                           padx=10, pady=4)
        ver_lbl.pack(side="left", pady=14)

        close_lbl = tk.Label(hdr, text="✕", font=("Segoe UI", 12),
                             bg=t.hdr, fg=t.txt2, cursor="hand2",
                             padx=16, pady=14)
        close_lbl.pack(side="right")
        close_lbl.bind("<Enter>",           lambda e: close_lbl.config(bg="#2a1515", fg="#ff5555"))
        close_lbl.bind("<Leave>",           lambda e: close_lbl.config(bg=_th.active.hdr, fg=_th.active.txt2))
        close_lbl.bind("<ButtonRelease-1>", lambda e: self._close())

        # Accent line
        tk.Frame(self.win, bg=t.accent, height=2).pack(fill="x")

        # ── Body ──────────────────────────────────────────
        body = tk.Frame(self.win, bg=t.bg)
        body.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(body, text="What's new in this update:",
                 font=("Segoe UI", 9, "bold"),
                 bg=t.bg, fg=t.txt2).pack(anchor="w", pady=(0, 10))

        for note in notes:
            row = tk.Frame(body, bg=t.bg)
            row.pack(fill="x", pady=3)
            tk.Frame(row, bg=t.accent, width=4, height=4).pack(
                side="left", padx=(4, 10), pady=6)
            tk.Label(row, text=note, font=("Segoe UI", 10),
                     bg=t.bg, fg=t.txt, anchor="w").pack(side="left", fill="x")

        # ── Footer ────────────────────────────────────────
        tk.Frame(self.win, bg=t.border, height=1).pack(fill="x")
        footer = tk.Frame(self.win, bg=t.hdr)
        footer.pack(fill="x")

        tk.Label(footer, text="Thanks for staying updated  ♥",
                 font=("Segoe UI", 9), bg=t.hdr, fg=t.txt2,
                 padx=20, pady=14).pack(side="left")

        try:
            c  = t.accent.lstrip("#")
            r, g, b = int(c[0:2],16), int(c[2:4],16), int(c[4:6],16)
            fg = "#000000" if (r*299+g*587+b*114)/1000 > 160 else "#ffffff"
        except Exception:
            fg = "#ffffff"

        tk.Button(footer, text="Got it  ✓", command=self._close,
                  font=("Segoe UI", 10, "bold"),
                  bg=t.accent, fg=fg,
                  activebackground=t.accent, activeforeground=fg,
                  relief="flat", bd=0, cursor="hand2",
                  padx=24, pady=10).pack(side="right", padx=16, pady=10)

    # ── Close ──────────────────────────────────────────────

    def _live_recolor(self, new_t) -> None:
        old_t = getattr(self, "_built_t", None)
        if old_t is None:
            self._built_t = new_t
            return
        color_map: dict[str, str] = {}
        for k, old_v in old_t.to_dict().items():
            if isinstance(old_v, str) and old_v.startswith("#"):
                new_v = getattr(new_t, k, old_v)
                if old_v.lower() != new_v.lower():
                    color_map[old_v.lower()] = new_v
        if not color_map:
            return
        def _walk(w):
            for attr in ("bg", "fg", "highlightbackground", "activebackground", "activeforeground"):
                try:
                    cur = w.cget(attr)
                    rep = color_map.get(cur.lower() if cur else "")
                    if rep: w.configure(**{attr: rep})
                except Exception: pass
            for child in w.winfo_children(): _walk(child)
        _walk(self.win)
        self._built_t = new_t

    def _close(self):
        try: self.mgr.overlay_screen = None
        except: pass
        try: self.win.grab_release()
        except: pass
        try: self.bg.destroy()
        except: pass
        try: self.win.destroy()
        except: pass
