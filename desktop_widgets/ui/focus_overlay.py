"""Focus view: a big hero card for the selected app above a shelf of the folder's apps.

Modelled on the media widget: the hero shows the app large with a blurred
colour wash from its own icon, like the album-art backdrop.
"""
from __future__ import annotations

import os
import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

from desktop_widgets import config
from desktop_widgets.theme import CHROMA, TYPE
from desktop_widgets.widgets.base_widget import _rounded_rect
from desktop_widgets.services.screens import area_for
from desktop_widgets.utils import launch_app, clip
from desktop_widgets.ui.tiles import tile_photo, fit_label, icon_color, icon_image, _mix
from desktop_widgets.ui.drawing import recolor_shape, rounded_image

HERO_TOP, HERO_H = 100, 200          # hero card under the title
SHELF_TOP = HERO_TOP + HERO_H + 18
TILE_W, TILE_H, TILE_GAP = 112, 124, 12
TILE_ICON, TILE_ICON_Y = 56, 50
ARROW_W = 40                          # room for the shelf's scroll buttons
FOOTER = 86


def focus_width(area):
    left, top, right, bottom = area
    return min(880, right-left-64)


def focus_height(area):
    left, top, right, bottom = area
    return min(SHELF_TOP + TILE_H + 22 + FOOTER, bottom-top-64)


def shelf_tile(master, app, t, state='idle'):
    return tile_photo(master, app, t, TILE_W, TILE_H, TILE_ICON, TILE_ICON_Y, state, 16,
                      tint=icon_color(app, t.accent))


def prewarm(mgr):
    """Render every folder's shelf tiles a few at a time while the app is
    idle, so opening and switching folders is instant."""
    jobs = [(group, app) for group in mgr.data.get('groups', []) for app in group.get('apps', [])]
    def step():
        for _ in range(3):
            if not jobs:
                return
            if mgr.focus is not None:          # never compete with an open overlay
                break
            group, app = jobs.pop(0)
            try:
                shelf_tile(mgr.root, app, config.get_theme(mgr.data, group.get('theme_override')))
            except Exception:
                pass
        mgr.root.after(30, step)
    mgr.root.after_idle(step)


# ── Hero card ──────────────────────────────────────────────

def app_kind(app):
    launch = (app.get('launch') or '').lower()
    path = app.get('path', '').lower()
    if launch.startswith('steam://'):
        return 'Steam game'
    if launch and '://' in launch:
        return 'Game'
    if path.startswith('shell:appsfolder'):
        return 'Store app'
    if path.endswith('.url'):
        return 'Link'
    return 'App'


def _font(name, size):
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def _wrap(text, font, width, lines=2):
    words, out, line = text.split(), [], ''
    for word in words:
        test = (line + ' ' + word).strip()
        if font.getlength(test) <= width:
            line = test
        else:
            if line:
                out.append(line)
            line = word
    if line:
        out.append(line)
    if len(out) > lines:
        out = out[:lines]
        while out[-1] and font.getlength(out[-1] + '…') > width:
            out[-1] = out[-1][:-1]
        out[-1] = out[-1].rstrip() + '…'
    return out or ['']


_hero_cache: dict = {}


def hero_image(app, w, h, t, folder_name):
    """The selected app, large, on a wash made from its own icon (cached)."""
    key = (app.get('path') if app else None, app.get('icon_path') if app else None,
           w, h, t.bg, t.btn, t.border, t.accent, t.txt, folder_name)
    if key in _hero_cache:
        return _hero_cache[key]
    image = Image.new('RGBA', (w, h), _mix(t.bg, t.bg, 0) + (255,))
    panel = rounded_image(w, h, 18, t.btn, t.border)
    inner = Image.new('L', (w, h))
    ImageDraw.Draw(inner).rounded_rectangle((1, 1, w-2, h-2), radius=17, fill=255)
    if app:
        icon = icon_image(app, 256, t.accent)
        # Album-art style wash: the icon blurred across the card, then tinted.
        small = icon.resize((max(1, w//10), max(1, h//10)), Image.Resampling.BILINEAR)
        bed = Image.new('RGBA', small.size, _mix(t.btn, icon_color(app, t.accent), 0.25) + (255,))
        bed.alpha_composite(small)
        wash = bed.filter(ImageFilter.GaussianBlur(2)).resize((w, h), Image.Resampling.BILINEAR)
        wash = Image.blend(wash, Image.new('RGBA', (w, h), _mix(t.btn, t.btn, 0) + (255,)), 0.68)
        panel.paste(wash, (0, 0), inner)
        border = rounded_image(w, h, 18, '', t.border)
        panel.alpha_composite(border)
    image.alpha_composite(panel)
    draw = ImageDraw.Draw(image)
    if not app:
        draw.text((w//2, h//2 - 10), 'No apps in this folder yet', fill=t.txt,
                  font=_font('segoeuib.ttf', 18), anchor='mm')
        draw.text((w//2, h//2 + 16), 'Press + on the folder or drop shortcuts on it.', fill=t.txt2,
                  font=_font('segoeui.ttf', 11), anchor='mm')
        _hero_cache[key] = image
        return image

    size = h - 64
    big = icon_image(app, 256, t.accent).resize((size, size), Image.Resampling.LANCZOS)
    x, y = 32, (h - size)//2
    shadow = Image.new('RGBA', (w//2, h//2))
    shadow.paste((0, 0, 0, 255), ((x)//2, (y + 6)//2), big.getchannel('A').resize((size//2, size//2))
                 .point(lambda a: a*0.55))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(5)).resize((w, h), Image.Resampling.BILINEAR))
    image.alpha_composite(big, (x, y))

    tx = x + size + 28
    room = w - tx - 32
    draw = ImageDraw.Draw(image)
    draw.ellipse((tx, 36, tx+6, 42), fill=t.accent)
    draw.text((tx+13, 39), app_kind(app).upper(), fill=t.txt2, font=_font('segoeuib.ttf', 11), anchor='lm')
    title_font = _font('segoeuib.ttf', 26)
    lines = _wrap(app.get('name', ''), title_font, room)
    for i, line in enumerate(lines):
        draw.text((tx, 56 + i*32), line, fill=t.txt, font=title_font)
    draw.text((tx, 64 + len(lines)*32), f'In {folder_name}', fill=t.txt2, font=_font('segoeui.ttf', 12))
    _hero_cache[key] = image
    while len(_hero_cache) > 48:
        _hero_cache.pop(next(iter(_hero_cache)))
    return image


class FocusOverlay:
    def __init__(self, mgr, group):
        self.mgr = mgr
        self.group = group
        self._groups = mgr.data.get('groups', [])
        self._group_idx = next((i for i, g in enumerate(self._groups) if g['id'] == group['id']), 0)
        self._animating = False
        self._closed = False
        self._after = None
        self._selected = 0           # app shown in the hero / opened by Enter
        self._previewed = None       # app under the pointer, shown in the hero
        self._t = config.get_theme(mgr.data, group.get('theme_override'))
        source = mgr.wins.get(group['id'])
        rect = source.rect() if source else (group.get('x', 0), group.get('y', 0), 300, 200)
        self._area = area_for(mgr.root, *rect)
        left, top, right, bottom = self._area
        self._ww, self._wh = focus_width(self._area), focus_height(self._area)
        self._wx = left + (right-left-self._ww)//2
        self._wy = top + (bottom-top-self._wh)//2

        self.bg = tk.Toplevel(mgr.root)
        self.bg.overrideredirect(True)
        self.bg.configure(bg='#05070d')
        self.bg.attributes('-topmost', True)
        self.bg.attributes('-alpha', 0.62)
        self.bg.geometry(f'{right-left}x{bottom-top}+{left}+{top}')
        self.bg.bind('<Button-1>', lambda e: self.close())

        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.configure(bg=CHROMA)
        self.win.attributes('-transparentcolor', CHROMA)
        self.win.attributes('-topmost', True)
        self.win.geometry(f'{self._ww}x{self._wh}+{self._wx}+{self._wy}')
        self.cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        self.cv.pack(fill='both', expand=True)
        self.cv.bind('<Motion>', self._track_buttons)
        self.cv.bind('<Leave>', lambda e: self._track_buttons(type('E', (), {'x': -1, 'y': -1})))
        self.body = tk.Canvas(self.win, highlightthickness=0, xscrollincrement=TILE_W + TILE_GAP)
        self.body.place(x=24 + ARROW_W, y=SHELF_TOP, width=self._ww - 48 - 2*ARROW_W, height=TILE_H + 20)
        self.body.bind('<Leave>', lambda e: self._preview(None))
        self.win.bind('<Escape>', lambda e: self.close())
        self.win.bind('<Left>', lambda e: self._step(-1))
        self.win.bind('<Right>', lambda e: self._step(1))
        self.win.bind('<Up>', lambda e: self._nav_dir('left'))
        self.win.bind('<Down>', lambda e: self._nav_dir('right'))
        self.win.bind('<Return>', lambda e: self._open_selected())
        self.win.bind('<MouseWheel>', self._wheel)
        self._render()
        self.win.lift(self.bg)
        self.win.focus_force()

    # ── Buttons (footer, shelf arrows) ─────────────────────

    def _button(self, x, y, w, label, command, tag):
        """Hover is tracked from the pointer position (see _track_buttons):
        redrawing on <Enter>/<Leave> would replace the item under the cursor,
        fire <Leave>/<Enter> again and loop forever."""
        self._buttons[tag] = (x, y, w, label, command)
        self._draw_button(tag, hover=False)
        self.cv.tag_bind(tag, '<Button-1>', lambda e: command())

    def _draw_button(self, tag, hover):
        t = self._t
        x, y, w, label, _ = self._buttons[tag]
        self.cv.delete(tag)
        first = set(self.cv.find_all())
        _rounded_rect(self.cv, x, y, x+w, y+40, 12 if w > 60 else 20,
                      fill=t.hov if hover else t.btn,
                      outline=t.accent if hover else t.border, width=2 if hover else 1)
        for item in set(self.cv.find_all()) - first:
            self.cv.addtag_withtag(tag, item)
        self.cv.create_text(x+w/2, y+20, text=label, fill=t.txt if hover else t.txt3,
                            font=TYPE['header'] if hover else TYPE['body'], tags=tag)

    def _track_buttons(self, event):
        hovered = next((tag for tag, (x, y, w, *_ ) in self._buttons.items()
                        if x <= event.x <= x+w and y <= event.y <= y+40), None)
        if hovered == self._hovered_button:
            return
        for tag in (self._hovered_button, hovered):
            if tag in self._buttons:
                self._draw_button(tag, hover=tag == hovered)
        self._hovered_button = hovered
        self.cv.config(cursor='hand2' if hovered or self._over_play(event) else '')

    def _over_play(self, event):
        box = getattr(self, '_play_box', None)
        return bool(box) and box[0] <= event.x <= box[2] and box[1] <= event.y <= box[3]

    # ── Layout ─────────────────────────────────────────────

    def _render(self):
        t = self._t
        w, h = self._ww, self._wh
        self.cv.delete('all')
        self._buttons, self._hovered_button = {}, None
        from desktop_widgets.ui.components import paint_shell
        apps = self.group.get('apps', [])
        self._selected = min(self._selected, max(0, len(apps)-1))
        self._previewed = None
        accent = icon_color(apps[0], t.accent) if apps else t.accent
        paint_shell(self.cv, w, h, t, clip(self.group['name'], 42), self.close,
                    f"{len(apps)} APP{'S' if len(apps) != 1 else ''}  ·  DOUBLE-CLICK OR ENTER TO OPEN",
                    glows=[(accent, 0.2), (t.accent, 0.85)])
        self._hero_item = self.cv.create_image(24, HERO_TOP, anchor='nw')
        self._paint_play()
        mid = SHELF_TOP + TILE_H//2 - 12
        self._button(24, mid, ARROW_W - 6, '‹', lambda: self._scroll_shelf(-1), 'shelf_left')
        self._button(w - 24 - ARROW_W + 6, mid, ARROW_W - 6, '›', lambda: self._scroll_shelf(1), 'shelf_right')
        self.cv.create_line(24, h-70, w-24, h-70, fill=t.border)
        n = len(self._groups)
        if n > 1:
            prev = self._groups[(self._group_idx-1) % n]['name']
            nxt = self._groups[(self._group_idx+1) % n]['name']
            bw = min(220, (w-160)//2)
            self._button(24, h-56, bw, '‹  '+clip(prev, 20), lambda: self._nav_dir('left'), 'prev')
            self._button(w-bw-24, h-56, bw, clip(nxt, 20)+'  ›', lambda: self._nav_dir('right'), 'next')
        self.cv.create_text(w//2, h-36, text=f'{self._group_idx+1} / {max(n, 1)}',
                            fill=t.txt2, font=('Segoe UI', 10))
        self._render_shelf()
        self._show_hero()

    def _paint_play(self):
        """Play/Open button on the hero; recoloured in place on hover."""
        t = self._t
        bw, bh = 132, 42
        x2, y2 = self._ww - 24 - 22, HERO_TOP + HERO_H - 22
        x1, y1 = x2 - bw, y2 - bh
        self._play_box = (x1, y1, x2, y2)
        before = set(self.cv.find_all())
        shape = _rounded_rect(self.cv, x1, y1, x2, y2, bh//2, fill=t.accent, outline='')
        r, g, b = (int(t.accent[i:i+2], 16) for i in (1, 3, 5))
        on_accent = '#10141d' if (r*299 + g*587 + b*114)/1000 > 160 else '#ffffff'
        self._play_text = self.cv.create_text((x1+x2)/2, (y1+y2)/2, text='▶  Play',
                                              fill=on_accent, font=TYPE['header'])
        for item in set(self.cv.find_all()) - before:
            self.cv.addtag_withtag('play', item)
        hover_fill = '#%02x%02x%02x' % _mix(t.accent, '#ffffff', 0.18)
        self.cv.tag_bind('play', '<Button-1>', lambda e: self._open_selected())
        self.cv.tag_bind('play', '<Enter>', lambda e: recolor_shape(self.cv, shape, hover_fill))
        self.cv.tag_bind('play', '<Leave>', lambda e: recolor_shape(self.cv, shape, t.accent))

    def _render_shelf(self):
        t = self._t
        self.body.configure(bg=t.bg)
        self.body.delete('all')
        apps = self.group.get('apps', [])
        self._tiles, self._shown = {}, {}
        self.body.configure(scrollregion=(0, 0, max(1, len(apps)*(TILE_W+TILE_GAP) - TILE_GAP), TILE_H + 20))
        self.body.xview_moveto(0)
        label_font = TYPE['caption']
        for i, app in enumerate(apps):
            x, y = i*(TILE_W + TILE_GAP), 4
            tag = f'app_{i}'
            photo = shelf_tile(self.body, app, t, self._state(i))
            self._shown[i] = photo
            image = self.body.create_image(x, y, image=photo, anchor='nw', tags=tag)
            label = self.body.create_text(x+TILE_W/2, y+TILE_H-20,
                                          text=fit_label(self.body, app['name'], label_font, TILE_W-16),
                                          fill=t.txt if i == self._selected else t.txt3,
                                          font=label_font, tags=tag)
            self._tiles[i] = (image, label)
            self.body.tag_bind(tag, '<Button-1>', lambda e, k=i: self._select(k))
            self.body.tag_bind(tag, '<Double-Button-1>', lambda e, a=app: self._launch(a))
            self.body.tag_bind(tag, '<Button-3>', lambda e, a=app: self.mgr.app_ctx(a['path'], a['name'], self.group['id']))
            self.body.tag_bind(tag, '<Enter>', lambda e, k=i: self._preview(k))

    def _state(self, i):
        if i == self._selected:
            return 'selected_hover' if i == self._previewed else 'selected'
        return 'hover' if i == self._previewed else 'idle'

    def _refresh_tile(self, i):
        """Swap a tile's image in place (never recreate items from <Enter>)."""
        if i is None or i not in self._tiles:
            return
        apps = self.group.get('apps', [])
        image, label = self._tiles[i]
        photo = shelf_tile(self.body, apps[i], self._t, self._state(i))
        self._shown[i] = photo
        self.body.itemconfigure(image, image=photo)
        lit = i in (self._selected, self._previewed)
        self.body.itemconfigure(label, fill=self._t.txt if lit else self._t.txt3)

    def _show_hero(self):
        apps = self.group.get('apps', [])
        index = self._previewed if self._previewed is not None else self._selected
        app = apps[index] if apps else None
        image = hero_image(app, self._ww - 48, HERO_H, self._t, self.group['name'])
        self._hero_photo = ImageTk.PhotoImage(image, master=self.cv)
        self.cv.itemconfigure(self._hero_item, image=self._hero_photo)
        state = 'normal' if app else 'hidden'
        self.cv.itemconfigure('play', state=state)
        if app:
            self.cv.itemconfigure(self._play_text,
                                  text='▶  Play' if 'game' in app_kind(app).lower() else '▶  Open')

    # ── Interaction ────────────────────────────────────────

    def _preview(self, i):
        if i == self._previewed:
            return
        old, self._previewed = self._previewed, i
        self.body.config(cursor='hand2' if i is not None else '')
        self._refresh_tile(old)
        self._refresh_tile(i)
        self._show_hero()

    def _select(self, i):
        old, self._selected = self._selected, i
        self._refresh_tile(old)
        self._refresh_tile(i)
        self._show_hero()

    def _step(self, delta):
        apps = self.group.get('apps', [])
        if not apps:
            return
        self._select((self._selected + delta) % len(apps))
        self._scroll_into_view(self._selected)

    def _scroll_into_view(self, i):
        width = int(self.body.winfo_width()) or 1
        left = self.body.canvasx(0)
        x1 = i*(TILE_W + TILE_GAP)
        if x1 < left or x1 + TILE_W > left + width:
            self.body.xview_moveto(max(0, x1 - (width - TILE_W)/2) / max(1, len(self.group.get('apps', []))*(TILE_W+TILE_GAP)))

    def _scroll_shelf(self, direction):
        visible = max(1, int(self.body.winfo_width()) // (TILE_W + TILE_GAP))
        self.body.xview_scroll(direction * visible, 'units')

    def _open_selected(self):
        apps = self.group.get('apps', [])
        if apps:
            self._launch(apps[self._selected])

    def _launch(self, app):
        launch_app(app['path'])
        self.close()

    def _wheel(self, event):
        if self._animating:
            return 'break'
        if event.state & 1:          # Shift + wheel switches folders
            if event.delta:
                self._nav_dir('left' if event.delta > 0 else 'right')
        else:
            self.body.xview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def _nav_dir(self, side):
        if self._closed or self._animating or len(self._groups) <= 1:
            return
        index = (self._group_idx + (-1 if side == 'left' else 1)) % len(self._groups)
        self._navigate_to(self._groups[index], side)

    def _navigate_to(self, group, direction='right'):
        if self._closed or self._animating:
            return
        self._animating = True
        # Reuse the same card and backdrop: no clipped preview windows or handoffs.
        def fade(step=0):
            if self._closed:
                return
            if step == 4:
                self.group = group
                self._group_idx = self._groups.index(group)
                self._selected = 0
                self._t = config.get_theme(self.mgr.data, group.get('theme_override'))
                self._render()
            self.win.attributes('-alpha', 1-0.07*(step if step <= 4 else 8-step))
            if step < 8:
                self._after = self.win.after(16, lambda: fade(step+1))
            else:
                self._after = None
                self._animating = False
        fade()

    def _apply_theme(self):
        self._t = config.get_theme(self.mgr.data, self.group.get('theme_override'))
        self._render()

    def close(self):
        self._closed = True
        if self._after is not None:
            self.win.after_cancel(self._after)
        self.win.destroy()
        self.bg.destroy()
        self.mgr.focus = None
