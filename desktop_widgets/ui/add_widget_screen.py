"""Widget picker using the same rounded shell and cards as settings and the widgets."""
import tkinter as tk
from desktop_widgets import config
from desktop_widgets.theme import CHROMA, TYPE, R_PANEL
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.components import paint_shell
from desktop_widgets.widgets.base_widget import _rounded_rect
from desktop_widgets.ui.drawing import widget_icon, recolor_shape, glyph
from desktop_widgets.ui.tiles import _mix
from PIL import Image, ImageDraw, ImageTk


def _hex(rgb):
    return '#%02x%02x%02x' % rgb


def _badge(kind, color, base, size=52):
    """Icon on a rounded square tinted with the card's colour."""
    S = 3
    image = Image.new('RGBA', (size*S, size*S), _mix(base, color, 0.2) + (0,))
    ImageDraw.Draw(image).rounded_rectangle((0, 0, size*S-1, size*S-1), radius=15*S,
                                            fill=_mix(base, color, 0.2) + (255,))
    icon = widget_icon(kind, color, size=30*S)
    image.alpha_composite(icon, ((size*S-icon.width)//2, (size*S-icon.height)//2))
    return image.resize((size, size), Image.Resampling.LANCZOS)


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
        paint_shell(cv, width, height, t, 'Make room for more', self.close, 'ADD A WIDGET',
                    glows=[(t.accent, 0.15), (t.up_col, 0.9)])
        # Each kind gets its own colour from the theme, used for its badge.
        choices = [('App folder', 'Your everyday apps and games', 'folder', t.accent, mgr.new_group_dialog),
                   ('System stats', 'Live CPU, RAM and GPU graphs', 'statsplus', t.ok, mgr.toggle_statsplus),
                   ('Notes', 'A space for your ideas', 'notes', t.warn, mgr.toggle_notes),
                   ('Files', 'Keep useful files close', 'docs', t.up_col, mgr.new_docs_dialog),
                   ('Media', 'Now playing, within reach', 'media', t.dn_col, mgr.toggle_media)]
        cw, ch = (width-60)//2, (height-140)//3
        self._icons = []
        self.card_bounds = {}
        for i, (label, desc, key, color, command) in enumerate(choices):
            x, y = 24+(i % 2)*(cw+12), 110+(i//2)*(ch+10)
            card_width = width-48 if key == 'media' else cw
            self.card_bounds[key] = (x, y, card_width, ch)
            active = key in ('notes', 'statsplus', 'media') and mgr.data.get(key, {}).get('enabled', False)
            tag = f'choice_{i}'
            before = set(cv.find_all())
            shape = _rounded_rect(cv, x, y, x+card_width, y+ch, R_PANEL, fill=t.btn, outline=t.border)
            # Hover outline exists from the start and is only shown/hidden:
            # recreating items from <Enter>/<Leave> would loop.
            ring = _rounded_rect(cv, x, y, x+card_width, y+ch, R_PANEL, fill='', outline=t.accent, width=2)
            cv.itemconfigure(ring, state='hidden')
            badge = ImageTk.PhotoImage(_badge(key, color, t.btn), master=cv)
            self._icons.append(badge)
            cv.create_image(x+20, y+20, image=badge, anchor='nw')
            cv.create_text(x+20, y+ch-44, text=label, anchor='w', fill=t.txt, font=TYPE['title'])
            cv.create_text(x+20, y+ch-21, text='Already on your desktop' if active else desc,
                           anchor='w', fill=t.txt2, font=TYPE['caption'])
            if active:
                pill_w = 104
                _rounded_rect(cv, x+card_width-pill_w-16, y+18, x+card_width-16, y+46, 14,
                              fill=_hex(_mix(t.btn, t.ok, 0.22)), outline='')
                cv.create_text(x+card_width-pill_w/2-16, y+32, text='✓  On desktop',
                               fill=t.txt, font=TYPE['label'])
            else:
                cx, cy = x+card_width-34, y+34
                _rounded_rect(cv, cx-16, cy-16, cx+17, cy+17, 16, fill=_hex(_mix(t.btn, t.txt, 0.07)),
                              outline=t.border)
                glyph(cv, cx, cy, 'plus', t.txt, 16)
            for item in set(cv.find_all())-before:
                cv.addtag_withtag(tag, item)
            if not active:
                cv.tag_bind(tag, '<Button-1>', lambda e, cmd=command: self._choose(cmd))
                cv.tag_bind(tag, '<Enter>', lambda e, s=shape, r=ring: self._hover(cv, s, r, True, t))
                cv.tag_bind(tag, '<Leave>', lambda e, s=shape, r=ring: self._hover(cv, s, r, False, t))
        self.win.focus_force()
        self.win.bind('<Destroy>', self._destroyed)

    @staticmethod
    def _hover(cv, shape, ring, on, t):
        cv.config(cursor='hand2' if on else '')
        recolor_shape(cv, shape, t.hov if on else t.btn)
        cv.itemconfigure(ring, state='normal' if on else 'hidden')

    def _destroyed(self, event):
        if event.widget is self.win:
            self.mgr._add_picker = None

    def _choose(self, command):
        self.close()
        command()

    def close(self):
        self.win.destroy()
