"""Widget picker using the same rounded shell and cards as settings and the widgets."""
import tkinter as tk
from desktop_widgets import config
from desktop_widgets.theme import CHROMA, TYPE, R_PANEL, ICON
from desktop_widgets import theme as theme_mod
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.components import paint_shell
from desktop_widgets.widgets.base_widget import _rounded_rect
from desktop_widgets.ui.drawing import widget_icon, recolor_shape, glyph
from desktop_widgets.ui.tiles import _mix
from PIL import Image, ImageDraw, ImageTk


def _hex(rgb):
    return '#%02x%02x%02x' % rgb


def _badge(kind, color, base, size=44):
    """Icon on a rounded square softly tinted with its colour."""
    S = 3
    image = Image.new('RGBA', (size*S, size*S), _mix(base, color, 0.16) + (0,))
    ImageDraw.Draw(image).rounded_rectangle((0, 0, size*S-1, size*S-1), radius=8*S,
                                            fill=_mix(base, color, 0.16) + (255,))
    icon = widget_icon(kind, color, size=22*S)
    image.alpha_composite(icon, ((size*S-icon.width)//2, (size*S-icon.height)//2))
    return image.resize((size, size), Image.Resampling.LANCZOS)


class AddWidgetScreen:
    def __init__(self, mgr):
        self.mgr = mgr
        t = config.get_theme(mgr.data)
        left, top, right, bottom = area_for(mgr.root, mgr.root.winfo_pointerx(), mgr.root.winfo_pointery())
        width, height = min(640, right-left-40), min(400, bottom-top-40)
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes('-transparentcolor', CHROMA)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=CHROMA)
        self.win.geometry(f'{width}x{height}+{left+(right-left-width)//2}+{top+(bottom-top-height)//2}')
        self.win.bind('<Escape>', lambda e: self.close())
        cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        cv.pack(fill='both', expand=True)
        paint_shell(cv, width, height, t, 'Add a widget', self.close)
        # Each kind gets its own colour from the theme, used for its badge.
        choices = [('App folder', 'Your everyday apps and games', 'folder', t.accent, mgr.new_group_dialog),
                   ('System stats', 'Live CPU, RAM and GPU graphs', 'statsplus', t.accent, mgr.toggle_statsplus),
                   ('Notes', 'A space for your ideas', 'notes', t.accent, mgr.toggle_notes),
                   ('Files', 'Keep useful files close', 'docs', t.accent, mgr.new_docs_dialog),
                   ('Media', 'Control what is playing', 'media', t.accent, mgr.toggle_media),
                   ('Folder stack', 'Flip through folders in one widget', 'stack', t.accent,
                    mgr.new_stack_dialog)]
        cw, ch = (width-60)//2, (height-128)//3
        self._icons = []
        self.card_bounds = {}
        for i, (label, desc, key, color, command) in enumerate(choices):
            x, y = 24+(i % 2)*(cw+12), 84+(i//2)*(ch+10)
            card_width = width-48 if i == len(choices)-1 and len(choices) % 2 else cw
            self.card_bounds[key] = (x, y, card_width, ch)
            active = key in ('notes', 'statsplus', 'media') and mgr.data.get(key, {}).get('enabled', False)
            tag = f'choice_{i}'
            before = set(cv.find_all())
            shape = _rounded_rect(cv, x, y, x+card_width, y+ch, R_PANEL, fill=t.btn, outline=t.border)
            badge = ImageTk.PhotoImage(_badge(key, color, t.btn), master=cv)
            self._icons.append(badge)
            cy = y + ch//2
            cv.create_image(x+18, cy, image=badge, anchor='w')
            cv.create_text(x+76, cy-10, text=label, anchor='w', fill=t.txt, font=TYPE['strong'])
            cv.create_text(x+76, cy+10, text='Already on your desktop' if active else desc,
                           anchor='w', fill=t.txt2, font=TYPE['caption'])
            if active:
                cv.create_text(x+card_width-20, cy, text=ICON['check'], anchor='e',
                               fill=t.ok, font=(theme_mod.ICON_FONT, -14))
            else:
                glyph(cv, x+card_width-28, cy, 'add', t.txt2, 13)
            for item in set(cv.find_all())-before:
                cv.addtag_withtag(tag, item)
            if not active:
                cv.tag_bind(tag, '<ButtonRelease-1>', lambda e, cmd=command: self._choose(cmd))
                cv.tag_bind(tag, '<Enter>', lambda e, s=shape: self._hover(cv, s, True, t))
                cv.tag_bind(tag, '<Leave>', lambda e, s=shape: self._hover(cv, s, False, t))
        self.win.focus_force()
        self.win.bind('<Destroy>', self._destroyed)

    @staticmethod
    def _hover(cv, shape, on, t):
        cv.config(cursor='hand2' if on else '')
        recolor_shape(cv, shape, t.btn_h if on else t.btn)

    def _destroyed(self, event):
        if event.widget is self.win:
            self.mgr._add_picker = None

    def _choose(self, command):
        self.close()
        command()

    def close(self):
        self.win.destroy()
