"""Widget picker using the same rounded shell as focus and settings."""
import tkinter as tk
from desktop_widgets import config
from desktop_widgets.theme import CHROMA
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.components import paint_shell
from desktop_widgets.widgets.base_widget import _rounded_rect
from desktop_widgets.ui.drawing import widget_icon, recolor_shape
from PIL import ImageTk


class AddWidgetScreen:
    def __init__(self, mgr):
        self.mgr = mgr
        t = config.get_theme(mgr.data)
        left, top, right, bottom = area_for(mgr.root, mgr.root.winfo_pointerx(), mgr.root.winfo_pointery())
        width, height = min(650, right-left-40), min(550, bottom-top-40)
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes('-transparentcolor', CHROMA)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=CHROMA)
        self.win.geometry(f'{width}x{height}+{left+(right-left-width)//2}+{top+(bottom-top-height)//2}')
        self.win.bind('<Escape>', lambda e: self.close())
        cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        cv.pack(fill='both', expand=True)
        paint_shell(cv, width, height, t, 'Make room for more', self.close, 'ADD A WIDGET')
        choices = [('App Folder', 'Your everyday essentials', 'folder', mgr.new_group_dialog),
                   ('Stats+', 'Your system at a glance', 'statsplus', mgr.toggle_statsplus),
                   ('Notes', 'A space for your ideas', 'notes', mgr.toggle_notes),
                   ('Files', 'Keep useful files close', 'docs', mgr.new_docs_dialog),
                   ('Media', 'Now playing, within reach', 'media', mgr.toggle_media)]
        cw, ch = (width-60)//2, (height-140)//3
        self._icons = []
        self.card_bounds = {}
        for i, (label, desc, key, command) in enumerate(choices):
            x, y = 24+(i%2)*(cw+12), 110+(i//2)*(ch+10)
            card_width = width-48 if key == 'media' else cw
            self.card_bounds[key] = (x, y, card_width, ch)
            active = key in ('notes', 'statsplus', 'media') and mgr.data.get(key, {}).get('enabled', False)
            tag = f'choice_{i}'
            before = set(cv.find_all())
            shape = _rounded_rect(cv, x, y, x+card_width, y+ch, 16, fill=t.btn,
                                  outline=t.border)
            for item in set(cv.find_all())-before:
                cv.addtag_withtag(tag, item)
            icon = ImageTk.PhotoImage(widget_icon(key, t.accent), master=cv)
            self._icons.append(icon)
            if key == 'media':
                cv.create_image(x+46, y+ch/2, image=icon, tags=tag)
                cv.create_text(x+84, y+ch/2-14, text=label, anchor='w', fill=t.txt,
                               font=('Segoe UI', 14, 'bold'), tags=tag)
                cv.create_text(x+84, y+ch/2+16, text='Already on your desktop' if active else desc,
                               anchor='w', fill=t.txt2, font=('Segoe UI', 10), tags=tag)
            else:
                cv.create_image(x+card_width/2, y+32, image=icon, tags=tag)
                cv.create_text(x+card_width/2, y+76, text=label, fill=t.txt,
                               font=('Segoe UI', 12, 'bold'), tags=tag)
                cv.create_text(x+card_width/2, y+105, text='Already on your desktop' if active else desc,
                               fill=t.txt2, font=('Segoe UI', 9), tags=tag)
            cv.create_text(x+card_width-22, y+24, text='✓' if active else '+', fill=t.accent,
                           font=('Segoe UI', 17), tags=tag)
            if not active:
                cv.tag_bind(tag, '<Button-1>', lambda e, cmd=command: self._choose(cmd))
                cv.tag_bind(tag, '<Enter>', lambda e, s=shape: (cv.config(cursor='hand2'), recolor_shape(cv, s, t.hov)))
                cv.tag_bind(tag, '<Leave>', lambda e, s=shape: (cv.config(cursor=''), recolor_shape(cv, s, t.btn)))
        self.win.focus_force()
        self.win.bind('<Destroy>', self._destroyed)

    def _destroyed(self, event):
        if event.widget is self.win:
            self.mgr._add_picker = None

    def _choose(self, command):
        self.close()
        command()

    def close(self):
        self.win.destroy()
