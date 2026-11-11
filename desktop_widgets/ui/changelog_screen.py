"""A themed, scrollable summary shown once after an update."""
import tkinter as tk
from desktop_widgets import config
from desktop_widgets.theme import CHROMA, TYPE
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.components import paint_shell, RoundedButton, release_notes_view


class ChangelogScreen:
    def __init__(self, mgr, version, notes):
        self.mgr = mgr
        t = config.get_theme(mgr.data)
        left, top, right, bottom = area_for(mgr.root, mgr.root.winfo_pointerx(), mgr.root.winfo_pointery())
        width, height = min(640, right-left-48), min(600, bottom-top-48)
        self.bg = tk.Toplevel(mgr.root)
        self.bg.overrideredirect(True)
        self.bg.configure(bg='#000000')
        self.bg.attributes('-alpha', 0.5)
        self.bg.geometry(f'{right-left}x{bottom-top}+{left}+{top}')
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.configure(bg=CHROMA)
        self.win.attributes('-transparentcolor', CHROMA)
        self.win.geometry(f'{width}x{height}+{left+(right-left-width)//2}+{top+(bottom-top-height)//2}')
        self.win.bind('<Escape>', lambda e: self._close())
        shell = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        shell.pack(fill='both', expand=True)
        paint_shell(shell, width, height, t, 'You’re up to date', self._close,
                    f'DesktopWidget {version}')
        body = tk.Frame(self.win, bg=t.bg)
        body.place(x=28, y=100, width=width-56, height=height-182)
        tk.Label(body, text='What’s new', bg=t.bg, fg=t.txt,
                 font=TYPE['strong']).pack(anchor='w', pady=(0, 10))
        release_notes_view(body, '\n'.join(notes), t).pack(fill='both', expand=True)
        footer = tk.Frame(self.win, bg=t.bg)
        footer.place(x=28, y=height-64, width=width-56, height=44)
        tk.Label(footer, text='Your workspace is ready.', bg=t.bg, fg=t.txt2,
                 font=TYPE['body']).pack(side='left')
        RoundedButton(footer, 'Back to desktop', self._close, t, accent=True).pack(side='right')
        self.win.lift(self.bg)
        self.win.grab_set()
        self.win.focus_set()

    def _close(self):
        self.win.grab_release()
        self.win.destroy()
        self.bg.destroy()
