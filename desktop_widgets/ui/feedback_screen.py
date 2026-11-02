"""Occasional feedback card: a 1–5 rating and an optional comment."""
import tkinter as tk
from desktop_widgets import config
from desktop_widgets.theme import CHROMA, TYPE
from desktop_widgets.services import telemetry
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.components import paint_shell, RoundedButton

RATINGS = ((1, 'Not great'), (2, 'Meh'), (3, 'Okay'), (4, 'Good'), (5, 'Love it'))


class FeedbackScreen:
    def __init__(self, mgr, version):
        self.mgr, self.version = mgr, version
        self.rating = None
        self.t = t = config.get_theme(mgr.data)
        left, top, right, bottom = area_for(mgr.root, mgr.root.winfo_pointerx(),
                                            mgr.root.winfo_pointery())
        width, height = min(500, right-left-40), min(440, bottom-top-40)
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes('-transparentcolor', CHROMA)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=CHROMA)
        self.win.geometry(f'{width}x{height}+{left+(right-left-width)//2}'
                          f'+{top+(bottom-top-height)//2}')
        self.win.bind('<Escape>', lambda e: self.later())
        cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        cv.pack(fill='both', expand=True)
        paint_shell(cv, width, height, t, 'How’s it going?', self.later, 'QUICK QUESTION')

        body = tk.Frame(self.win, bg=t.bg)
        body.place(x=26, y=100, width=width-52, height=height-100-84)
        tk.Label(body, text='How happy are you with DesktopWidgets so far?', bg=t.bg,
                 fg=t.txt2, font=TYPE['body']).pack(anchor='w')

        chips = tk.Frame(body, bg=t.bg)
        chips.pack(fill='x', pady=(12, 16))
        self._chips = {}
        for value, label in RATINGS:
            chip = RoundedButton(chips, label, lambda v=value: self.choose(v), t,
                                 font=TYPE['label'], padx=12, pady=8)
            chip.pack(side='left', padx=(0, 6))
            self._chips[value] = chip

        tk.Label(body, text='ANYTHING WE SHOULD CHANGE?  (optional)', bg=t.bg, fg=t.txt2,
                 font=TYPE['meta']).pack(anchor='w', pady=(0, 6))
        box = tk.Frame(body, bg=t.border)
        box.pack(fill='both', expand=True)
        self.text = tk.Text(box, bg=t.btn, fg=t.txt, insertbackground=t.txt,
                            selectbackground=t.accent, selectforeground=t.bg,
                            font=TYPE['body'], relief='flat', wrap='word',
                            highlightthickness=0, padx=12, pady=10, height=5)
        self.text.pack(fill='both', expand=True, padx=1, pady=1)

        footer = tk.Frame(self.win, bg=t.bg)
        footer.place(x=26, y=height-70, width=width-52, height=46)
        never = tk.Label(footer, text='Don’t ask again', bg=t.bg, fg=t.txt2,
                         font=TYPE['caption'], cursor='hand2')
        never.pack(side='left')
        never.bind('<Button-1>', lambda e: self.never())
        self.send_button = RoundedButton(footer, 'Send feedback', self.send, t, accent=True)
        self.send_button.pack(side='right')
        RoundedButton(footer, 'Not now', self.later, t).pack(side='right', padx=(0, 8))
        self.status = tk.Label(body, text='', bg=t.bg, fg=t.txt2, font=TYPE['caption'])
        self.win.focus_force()

    def choose(self, value):
        self.rating = value
        for v, chip in self._chips.items():
            chip.set_selected(v == value)

    def send(self):
        if self.rating is None:
            self.status.configure(text='Pick a rating first.', fg=self.t.warn)
            self.status.pack(anchor='w', pady=(6, 0))
            return
        telemetry.send_feedback(self.mgr.data, self.version, self.rating,
                                self.text.get('1.0', 'end-1c'))
        self._finish()

    def later(self):
        self._finish()

    def never(self):
        self._finish(never=True)

    def _finish(self, never=False):
        telemetry.mark_asked(self.mgr.data, never=never)
        config.save(self.mgr.data)
        self.win.destroy()
