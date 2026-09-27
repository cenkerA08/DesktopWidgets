"""Shared card, button and theme-picker styling for application screens."""
import tkinter as tk
import tkinter.font as tkfont
from desktop_widgets.widgets.base_widget import _rounded_rect
from desktop_widgets.theme import PRESETS


def paint_shell(cv, width, height, theme, title, close, eyebrow='YOUR WORKSPACE'):
    _rounded_rect(cv, 1, 1, width-1, height-1, 24, fill=theme.bg, outline=theme.border)
    _rounded_rect(cv, 26, 27, 34, 35, 4, fill=theme.accent)
    cv.create_text(44, 31, text=eyebrow, anchor='w', fill=theme.txt2,
                   font=('Segoe UI', 9, 'bold'))
    cv.create_text(26, 66, text=title, anchor='w', fill=theme.txt,
                   font=('Segoe UI', 23, 'bold'))
    close_shape = _rounded_rect(cv, width-66, 24, width-26, 64, 20,
                                fill=theme.btn, outline=theme.border)
    cv.addtag_withtag('close', close_shape)
    cv.create_text(width-46, 44, text='×', fill=theme.txt2, font=('Segoe UI', 15), tags='close')
    cv.tag_bind('close', '<Button-1>', lambda e: close())
    cv.tag_bind('close', '<Enter>', lambda e: cv.config(cursor='hand2'))
    cv.tag_bind('close', '<Leave>', lambda e: cv.config(cursor=''))


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, theme, accent=False, **kw):
        font = kw.pop('font', ('Segoe UI', 10))
        padx, pady = kw.pop('padx', 14), kw.pop('pady', 8)
        width = kw.pop('width', tkfont.Font(font=font).measure(text)+2*padx)
        height = kw.pop('height', tkfont.Font(font=font).metrics('linespace')+2*pady)
        bg = kw.pop('bg', theme.accent if accent else theme.btn)
        fg = kw.pop('fg', theme.bg if accent else theme.txt)
        super().__init__(parent, width=width, height=height,
                         bg=parent.cget('bg'), highlightthickness=0, cursor='hand2', takefocus=True)
        def draw(hover=False):
            self.delete('all')
            _rounded_rect(self, 1, 1, width-1, height-1, min(12, height//2),
                          fill=theme.hov if hover and not accent else bg)
            self.create_text(width/2, height/2, text=text, font=font, fill=fg)
        draw()
        self.bind('<Enter>', lambda e: draw(True))
        self.bind('<Leave>', lambda e: draw())
        self.bind('<ButtonRelease-1>', lambda e: command())
        self.bind('<Return>', lambda e: command())
        self.bind('<space>', lambda e: command())
        self.bind('<FocusIn>', lambda e: draw(True))
        self.bind('<FocusOut>', lambda e: draw())


def theme_picker(parent, theme, current, on_select, bg=None):
    """One preview-card picker, reused for global and per-widget themes."""
    background = bg or theme.bg
    gallery = tk.Frame(parent, bg=background)
    gallery.pack(fill='x')
    cards = []
    for name, preset in PRESETS.items():
        if name == 'Dark Blue' and current != name:
            continue  # Legacy alias of Graphite; preserve saved selections.
        cv = tk.Canvas(gallery, width=132, height=104, bg=background,
                       highlightthickness=0, cursor='hand2')
        cards.append(cv)
        cv.grid(row=(len(cards)-1)//3, column=(len(cards)-1)%3, padx=(0, 10), pady=(0, 10))
        _rounded_rect(cv, 2, 2, 130, 76, 12, fill=preset.bg,
                      outline=theme.accent if current == name else preset.border,
                      width=2 if current == name else 1)
        cv.create_line(16, 20, 62, 20, fill=preset.txt, width=3)
        for j, color in enumerate((preset.accent, preset.btn_h, preset.hov)):
            _rounded_rect(cv, 16+j*35, 35, 42+j*35, 61, 7, fill=color)
        cv.create_text(3, 92, text=name+('  ✓' if name == current else ''),
                       anchor='w', fill=theme.txt, font=('Segoe UI', 9))
        cv.bind('<Button-1>', lambda e, n=name: on_select(n))
    def arrange(event):
        cols = max(1, event.width//142)
        for i, card in enumerate(cards):
            card.grid_configure(row=i//cols, column=i%cols)
    gallery.bind('<Configure>', arrange)
