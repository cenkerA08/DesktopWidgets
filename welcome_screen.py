"""
welcome_screen.py — First-run onboarding screen.
Shown once when the user launches the app for the very first time.
"""
from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manager import Manager


STEPS = [
    {
        "icon":  "👋",
        "title": "Welcome to DesktopWidget",
        "body":  (
            "A lightweight desktop companion that keeps\n"
            "your apps, files, stats and media always\n"
            "one click away — right on your desktop."
        ),
    },
    {
        "icon":  "🗂",
        "title": "Organizer widgets",
        "body":  (
            "Create folders to group your apps, files\n"
            "and shortcuts. Drag & drop anything onto\n"
            "a widget to add it instantly."
        ),
    },
    {
        "icon":  "📊",
        "title": "Stats & system info",
        "body":  (
            "The Stats+ widget shows CPU, RAM, GPU\n"
            "and disk usage in real time, so you always\n"
            "know what your PC is doing."
        ),
    },
    {
        "icon":  "🎵",
        "title": "Media & Notes",
        "body":  (
            "The Media widget shows what's playing in\n"
            "Spotify or any other player. Notes keeps\n"
            "a sticky pad right on your desktop."
        ),
    },
    {
        "icon":  "🎨",
        "title": "Make it yours",
        "body":  (
            "Choose from different built-in themes to match\n"
            "your wallpaper. Open Settings with the ⚙\n"
            "button to get started."
        ),
    },
]


class WelcomeScreen:
    def __init__(self, mgr: "Manager", on_done) -> None:
        self.mgr     = mgr
        self.on_done = on_done
        self._step   = 0

        import config
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

        # Panel
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", False)
        self.win.configure(bg=t.bg)
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
        for w in self.win.winfo_children():
            w.destroy()
        t    = self._t
        step = STEPS[self._step]
        last = self._step == len(STEPS) - 1

        # ── Content area ──────────────────────────────────
        content = tk.Frame(self.win, bg=t.bg)
        content.pack(fill="both", expand=True, padx=40, pady=(40, 16))

        # Icon
        tk.Label(content, text=step["icon"],
                 font=("Segoe UI", 48),
                 bg=t.bg, fg=t.txt).pack()

        # Title
        tk.Label(content, text=step["title"],
                 font=("Segoe UI", 16, "bold"),
                 bg=t.bg, fg=t.txt).pack(pady=(12, 6))

        # Body
        tk.Label(content, text=step["body"],
                 font=("Segoe UI", 11),
                 bg=t.bg, fg=t.txt2,
                 justify="center").pack()

        # ── Step dots ─────────────────────────────────────
        dots_frame = tk.Frame(self.win, bg=t.bg)
        dots_frame.pack(pady=(0, 8))
        for i in range(len(STEPS)):
            is_active = i == self._step
            w2 = 24 if is_active else 6
            tk.Frame(dots_frame, bg=t.accent if is_active else t.border,
                     width=w2, height=6).pack(side="left", padx=3)

        # ── Footer ────────────────────────────────────────
        tk.Frame(self.win, bg=t.border, height=1).pack(fill="x")
        footer = tk.Frame(self.win, bg=t.hdr)
        footer.pack(fill="x")

        # Skip
        if not last:
            skip = tk.Label(footer, text="Skip intro",
                            font=("Segoe UI", 9),
                            bg=t.hdr, fg=t.txt2, cursor="hand2",
                            padx=20, pady=14)
            skip.pack(side="left")
            skip.bind("<Enter>", lambda e: skip.config(fg=t.txt))
            skip.bind("<Leave>", lambda e: skip.config(fg=t.txt2))
            skip.bind("<ButtonRelease-1>", lambda e: self._finish())

        # Next / Get started
        btn_text = "Get started  ✓" if last else "Next  →"
        btn_cmd  = self._finish if last else self._next

        try:
            c  = t.accent.lstrip("#")
            r2, g2, b2 = int(c[0:2],16), int(c[2:4],16), int(c[4:6],16)
            fg = "#000000" if (r2*299+g2*587+b2*114)/1000 > 160 else "#ffffff"
        except Exception:
            fg = "#ffffff"

        btn = tk.Button(footer, text=btn_text, command=btn_cmd,
                        font=("Segoe UI", 10, "bold"),
                        bg=t.accent, fg=fg,
                        activebackground=t.accent, activeforeground=fg,
                        relief="flat", bd=0, cursor="hand2",
                        padx=24, pady=10)
        btn.pack(side="right", padx=16, pady=10)

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
