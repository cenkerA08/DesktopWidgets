"""
welcome_screen.py — First-run onboarding screen.
Shown once when the user launches the app for the very first time.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desktop_widgets.manager import Manager


STEPS = [
    {
        "icon":  "desktop",
        "title": "Welcome to DesktopWidget",
        "body":  (
            "A lightweight desktop companion that keeps\n"
            "your apps, files, stats and media always\n"
            "one click away — right on your desktop."
        ),
    },
    {
        "icon":  "folder",
        "title": "Organizer widgets",
        "body":  (
            "Create folders to group your apps, files\n"
            "and shortcuts. Drag & drop anything onto\n"
            "a widget to add it instantly."
        ),
    },
    {
        "icon":  "stats",
        "title": "Stats & system info",
        "body":  (
            "The System stats widget shows CPU, RAM, GPU\n"
            "and disk usage in real time, so you always\n"
            "know what your PC is doing."
        ),
    },
    {
        "icon":  "music",
        "title": "Media & Notes",
        "body":  (
            "The Media widget shows what's playing in\n"
            "Spotify or any other player. Notes keeps\n"
            "a sticky pad right on your desktop."
        ),
    },
    {
        "icon":  "palette",
        "title": "Make it yours",
        "body":  (
            "Choose a theme that suits your wallpaper.\n"
            "Open Settings with the gear button\n"
            "to get started."
        ),
    },
]


class WelcomeScreen:
    def __init__(self, mgr: "Manager", on_done) -> None:
        self.mgr     = mgr
        self.on_done = on_done
        self._step   = 0

        import desktop_widgets.config as config
        t  = config.get_theme(mgr.data)
        sw = mgr.root.winfo_screenwidth()
        sh = mgr.root.winfo_screenheight()
        PW, PH = 520, 400
        px, py = (sw - PW) // 2, (sh - PH) // 2

        # Backdrop
        self.bg = tk.Toplevel(mgr.root)
        self.bg.overrideredirect(True)
        self.bg.attributes("-topmost", False)
        self.bg.attributes("-alpha", 0.0)
        self.bg.configure(bg="#000000")
        self.bg.geometry(f"{sw}x{sh}+0+0")
        self._fade(0.0)

        # Panel: a rounded window keyed out of a transparent background
        from desktop_widgets.theme import CHROMA
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", False)
        self.win.configure(bg=CHROMA)
        self.win.attributes("-transparentcolor", CHROMA)
        self.win.geometry(f"{PW}x{PH}+{px}+{py}")
        self.win.bind("<Escape>", lambda e: self._finish())
        self.PW, self.PH = PW, PH
        self._t = t

        self.bg.update_idletasks()
        self.win.lift(self.bg)
        self.win.focus_force()
        self.win.grab_set()

        self._build()

    # ── Fade backdrop ──────────────────────────────────────

    def _fade(self, cur=0.0):
        cur = round(min(0.55, cur + 0.05), 3)
        try: self.bg.attributes("-alpha", cur)
        except: return
        if cur < 0.55: self.bg.after(14, lambda: self._fade(cur))

    # ── Build ──────────────────────────────────────────────

    def _build(self):
        from desktop_widgets.theme import CHROMA, TYPE, ICON, mix
        from desktop_widgets import theme as th
        from desktop_widgets.ui.drawing import rounded_rect
        from desktop_widgets.ui.components import RoundedButton
        for w in self.win.winfo_children():
            w.destroy()
        t    = self._t
        step = STEPS[self._step]
        last = self._step == len(STEPS) - 1
        W, H = self.PW, self.PH
        cv = tk.Canvas(self.win, width=W, height=H, bg=CHROMA, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        rounded_rect(cv, 0, 0, W, H, 8, fill=t.bg, outline=t.border, hard=True)
        rounded_rect(cv, 1, H - 72, W - 1, H - 1, 7, fill=t.btn, corners="bottom")
        cv.create_line(1, H - 72, W - 1, H - 72, fill=t.border)

        # Icon on a softly tinted tile
        rounded_rect(cv, W//2 - 36, 48, W//2 + 36, 120, 12, fill=mix(t.bg, t.accent, 0.16))
        cv.create_text(W//2, 84, text=ICON[step["icon"]], fill=t.accent, font=(th.ICON_FONT, -34))
        cv.create_text(W//2, 158, text=step["title"], fill=t.txt, font=TYPE["display"])
        cv.create_text(W//2, 218, text=step["body"], fill=t.txt2, font=TYPE["body"],
                       justify="center")

        # Pips: one per step, the current one wider and in the accent colour
        n = len(STEPS)
        x = W//2 - (n * 12 + 14) // 2
        for i in range(n):
            wide = i == self._step
            rounded_rect(cv, x, 280, x + (20 if wide else 6), 286, 3,
                         fill=t.accent if wide else mix(t.bg, t.txt, 0.25))
            x += (20 if wide else 6) + 6

        footer = tk.Frame(cv, bg=t.btn)
        cv.create_window(24, H - 36, window=footer, anchor="w", width=W - 48, height=34)
        bw = (W - 48 - 8) // 2
        if last:
            RoundedButton(footer, "Get started", self._finish, t, accent=True,
                          width=W - 48, height=32).pack(side="left")
        else:
            RoundedButton(footer, "Next", self._next, t, accent=True,
                          width=bw, height=32).pack(side="left")
            RoundedButton(footer, "Skip intro", self._finish, t,
                          width=bw, height=32).pack(side="right")

    # ── Navigation ─────────────────────────────────────────

    def _next(self):
        self._step += 1
        self._build()

    def _finish(self):
        try: self.win.grab_release()
        except: pass
        try: self.bg.destroy()
        except: pass
        try: self.win.destroy()
        except: pass
        self.on_done()
