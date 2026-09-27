"""A rounded focus card with stable layout and in-place group navigation."""
from __future__ import annotations

import tkinter as tk
from desktop_widgets import config
from desktop_widgets.theme import CHROMA
from desktop_widgets.widgets.base_widget import _rounded_rect
from desktop_widgets.services.screens import area_for
from desktop_widgets.utils import get_icon, launch_app, clip


class FocusOverlay:
    def __init__(self, mgr, group):
        self.mgr = mgr
        self.group = group
        self._groups = mgr.data.get('groups', [])
        self._group_idx = next((i for i, g in enumerate(self._groups) if g['id'] == group['id']), 0)
        self._animating = False
        self._closed = False
        self._after = None
        self._refs = []
        self._t = config.get_theme(mgr.data, group.get('theme_override'))
        source = mgr.wins.get(group['id'])
        rect = source.rect() if source else (group.get('x', 0), group.get('y', 0), 300, 200)
        self._area = area_for(mgr.root, *rect)
        left, top, right, bottom = self._area
        self._ww = min(880, right-left-64)
        columns = max(1, min(6, (self._ww-48)//128))
        rows = max(1, max(((len(g.get('apps', []))+columns-1)//columns
                          for g in self._groups), default=1))
        self._wh = min(590, max(350, 190+rows*144), bottom-top-64)
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
        self.body = tk.Canvas(self.win, highlightthickness=0, yscrollincrement=32)
        self.body.place(x=24, y=104, width=self._ww-48, height=self._wh-190)
        self.win.bind('<Escape>', lambda e: self.close())
        self.win.bind('<Left>', lambda e: self._nav_dir('left'))
        self.win.bind('<Right>', lambda e: self._nav_dir('right'))
        self.win.bind('<MouseWheel>', self._wheel)
        self._render()
        self.win.lift(self.bg)
        self.win.focus_force()

    def _button(self, x, y, w, label, command, tag):
        t = self._t
        first = set(self.cv.find_all())
        _rounded_rect(self.cv, x, y, x+w, y+40, 12, fill=t.btn, outline=t.border)
        for item in set(self.cv.find_all()) - first:
            self.cv.addtag_withtag(tag, item)
        self.cv.create_text(x+w/2, y+20, text=label, fill=t.txt,
                            font=('Segoe UI', 10), tags=tag)
        self.cv.tag_bind(tag, '<Button-1>', lambda e: command())
        self.cv.tag_bind(tag, '<Enter>', lambda e: self.cv.config(cursor='hand2'))
        self.cv.tag_bind(tag, '<Leave>', lambda e: self.cv.config(cursor=''))

    def _render(self):
        t = self._t
        w, h = self._ww, self._wh
        self.cv.delete('all')
        from desktop_widgets.ui.components import paint_shell
        paint_shell(self.cv, w, h, t, clip(self.group['name'], 42), self.close)
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
        self._render_apps()

    def _render_apps(self):
        t = self._t
        self.body.configure(bg=t.bg)
        self.body.delete('all')
        self._refs.clear()
        apps = self.group.get('apps', [])
        width = self._ww-48
        cols = max(1, min(6, width//128))
        cell = width/cols
        tile_w, tile_h = int(cell)-12, 128
        rows = max(1, (len(apps)+cols-1)//cols)
        self.body.configure(scrollregion=(0, 0, width, rows*144))
        self.body.yview_moveto(0)
        if not apps:
            self.body.create_text(width/2, (self._wh-190)/2,
                                  text='A little space for your next idea.\nAdd apps to this folder to get started.',
                                  justify='center', fill=t.txt2, font=('Segoe UI', 12))
        for i, app in enumerate(apps):
            x, y = int((i % cols)*cell)+6, (i//cols)*144+4
            tag = f'app_{i}'
            first = set(self.body.find_all())
            _rounded_rect(self.body, x, y, x+tile_w, y+tile_h, 16,
                          fill=t.btn, outline='')
            for item in set(self.body.find_all())-first:
                self.body.addtag_withtag(tag, item)
            icon = get_icon(app['path'], 56)
            if icon:
                self._refs.append(icon)
                self.body.create_image(x+tile_w/2, y+45, image=icon, tags=tag)
            else:
                self.body.create_text(x+tile_w/2, y+45, text=app.get('name', '?')[:1].upper(),
                                      fill=t.accent, font=('Segoe UI', 26, 'bold'), tags=tag)
            self.body.create_text(x+tile_w/2, y+100, text=clip(app['name'], 24),
                                  width=tile_w-16, fill=t.txt, font=('Segoe UI', 10), tags=tag)
            self.body.tag_bind(tag, '<Double-Button-1>', lambda e, a=app: self._launch(a))
            self.body.tag_bind(tag, '<Button-3>', lambda e, a=app: self.mgr.app_ctx(a['path'], a['name'], self.group['id']))
            self.body.tag_bind(tag, '<Enter>', lambda e, key=tag: self._hover(key, True))
            self.body.tag_bind(tag, '<Leave>', lambda e, key=tag: self._hover(key, False))

    def _hover(self, tag, active):
        self.body.config(cursor='hand2' if active else '')
        for item in self.body.find_withtag(tag):
            from desktop_widgets.ui.drawing import recolor_shape
            recolor_shape(self.body, item, self._t.hov if active else self._t.btn)

    def _launch(self, app):
        launch_app(app['path'])
        self.close()

    def _wheel(self, event):
        if self._animating:
            return 'break'
        top, bottom = self.body.yview()
        if event.state & 1 or bottom-top >= 0.999:
            if event.delta:
                self._nav_dir('left' if event.delta > 0 else 'right')
        else:
            self.body.yview_scroll(-1 if event.delta > 0 else 1, 'units')
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
