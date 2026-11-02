"""Pick installed apps from an icon grid, browse for shortcuts, or drop them in."""
import tkinter as tk
from tkinter import filedialog
from concurrent.futures import ThreadPoolExecutor

from desktop_widgets.services.apps import app_entry, installed_apps
from desktop_widgets.utils import get_icon, clip
from desktop_widgets.ui.components import RoundedButton, paint_shell
from desktop_widgets.ui.drawing import rounded_rect, recolor_shape
from desktop_widgets.theme import CHROMA, TYPE, R_TILE
from desktop_widgets import config

try:
    from tkinterdnd2 import DND_FILES
    DND_OK = True
except ImportError:
    DND_OK = False

TILE_W, TILE_H, GAP = 104, 104, 10
ICON = 40
SIDE = 28                     # left/right margin inside the shell
GRID_TOP = 196                # below title, search and tabs
FOOTER_H = 76
# Folders and launchers games install under; matched against the shortcut
# path with separators so "MSTeams" does not count as Steam.
_GAME_DIRS = tuple(f'\\{d}' for d in (
    'steam\\', 'steamapps\\', 'epic games\\', 'battle.net\\', 'riot games\\', 'ubisoft',
    'xboxgames\\', 'rockstar games\\', 'ea games\\', 'electronic arts\\', 'gog galaxy\\',
    'games\\'))
_GAME_NAMES = ('steam', 'epic games launcher', 'battle.net', 'riot client', 'ubisoft connect',
               'ea app', 'rockstar games launcher', 'gog galaxy', 'minecraft', 'roblox player')
_GAME_SCHEMES = ('steam://', 'com.epicgames.launcher://', 'uplay://', 'origin://',
                 'battlenet://', 'riotclient://', 'heroic://')


def is_game(entry):
    path = entry['path'].casefold()
    name = entry['name'].casefold()
    if name.startswith(_GAME_NAMES) or any(d in path for d in _GAME_DIRS):
        return True
    if path.endswith('.url'):                  # Steam/Epic shortcuts, not web links
        try:
            with open(entry['path'], encoding='utf-8', errors='ignore') as f:
                return any(line.strip().casefold().startswith('url=' + scheme)
                           for line in f for scheme in _GAME_SCHEMES)
        except OSError:
            return False
    return False


class AppPicker:
    def __init__(self, mgr, on_add, group_name=None):
        self.root = mgr.root
        self.on_add = on_add
        self.apps, self.visible = [], []
        self.selected = {}            # path -> entry, in click order
        self.tab = 'all'
        self._icons, self._icon_queue, self._icon_job = {}, [], None
        self._tiles = {}              # index -> background shape id
        self.t = t = config.get_theme(mgr.data)

        from desktop_widgets.services.screens import area_for
        left, top, right, bottom = area_for(
            mgr.root, mgr.root.winfo_pointerx(), mgr.root.winfo_pointery())
        sw, sh = right - left, bottom - top
        margin = min(48, max(16, min(sw, sh) // 12))
        self.width, self.height = width, height = min(680, sw - 2*margin), min(660, sh - 2*margin)
        x, y = left + (sw - width) // 2, top + (sh - height) // 2

        self.win = tk.Toplevel(mgr.root)
        self.win.title('Add apps')
        self.win.overrideredirect(True)
        self.win.attributes('-transparentcolor', CHROMA)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=CHROMA)
        self.win.geometry(f'{width}x{height}+{x}+{y}')
        self.win.bind('<Escape>', lambda e: self.close())

        self.shell = cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        cv.pack(fill='both', expand=True)
        eyebrow = f'ADD TO {group_name.upper()}' if group_name else 'ADD TO YOUR DESKTOP'
        paint_shell(cv, width, height, t, 'Apps and games', self.close, eyebrow)
        self._drag_window(cv)

        # Search field: a rounded canvas pill with a borderless Entry inside.
        sy = 92
        rounded_rect(cv, SIDE, sy, width-SIDE, sy+44, 14, fill=t.btn, outline=t.border)
        cv.create_text(SIDE+20, sy+22, text='⌕', fill=t.txt2, font=(TYPE['body'][0], 15))
        self.query = tk.StringVar()
        self.search = tk.Entry(cv, textvariable=self.query, bg=t.btn, fg=t.txt,
                               insertbackground=t.txt, font=(TYPE['body'][0], 11),
                               relief='flat', highlightthickness=0, borderwidth=0)
        cv.create_window(SIDE+38, sy+22, window=self.search, anchor='w',
                         width=width-2*SIDE-54, height=28)
        self.placeholder = tk.Label(cv, text='Search apps and games', bg=t.btn, fg=t.txt2,
                                    font=(TYPE['body'][0], 11), cursor='xterm')
        self.placeholder.bind('<Button-1>', lambda e: self.search.focus_set())
        self._placeholder_item = cv.create_window(SIDE+38, sy+22, window=self.placeholder,
                                                  anchor='w')
        self.query.trace_add('write', lambda *_: self.filter())
        self.search.bind('<Return>', lambda e: self.add_selected())
        self.search.bind('<Down>', lambda e: self.grid.focus_set())

        # Tabs
        self._tab_buttons = {}
        tx = SIDE
        for key, label in (('all', 'All apps'), ('games', 'Games')):
            button = RoundedButton(cv, label, lambda k=key: self.set_tab(k), t,
                                   accent=key == self.tab, font=TYPE['label'], padx=16, pady=6)
            button.configure(bg=t.bg)          # the shell canvas itself is see-through
            cv.create_window(tx, 152, window=button, anchor='nw')
            tx += int(button.cget('width')) + 8
            self._tab_buttons[key] = button

        # Grid area: its own scrolling canvas inside the shell.
        grid_h = height - GRID_TOP - FOOTER_H
        self.grid = tk.Canvas(cv, bg=t.bg, highlightthickness=0, width=width-2*SIDE,
                              height=grid_h, takefocus=True)
        cv.create_window(SIDE, GRID_TOP, window=self.grid, anchor='nw')
        self.cols = max(1, (width - 2*SIDE + GAP) // (TILE_W + GAP))
        self.grid_pad = (width - 2*SIDE - (self.cols*TILE_W + (self.cols-1)*GAP)) // 2
        for widget in (self.grid, self.win):
            widget.bind('<MouseWheel>', self._wheel)
        self.grid.bind('<Return>', lambda e: self.add_selected())

        # Footer
        fy = height - FOOTER_H + 20
        cv.create_line(SIDE, fy-12, width-SIDE, fy-12, fill=t.border)
        self.status = tk.Label(cv, text='Loading installed apps…', bg=t.bg, fg=t.txt2,
                               font=TYPE['caption'], anchor='w')
        cv.create_window(SIDE, fy+18, window=self.status, anchor='w')
        self.add_button = None
        self._footer_y = fy
        browse = RoundedButton(cv, 'Browse files…', self.browse, t)
        browse.configure(bg=t.bg)
        self._browse_w = int(browse.cget('width'))
        self._browse_item = cv.create_window(0, fy+18, window=browse, anchor='w')
        self._update_footer()

        if DND_OK:
            try:
                self.win.drop_target_register(DND_FILES)
                self.win.dnd_bind('<<Drop>>', self._on_drop)
            except (tk.TclError, AttributeError):
                pass

        self.grid.create_text((width-2*SIDE)//2, 60, text='Loading installed apps…',
                              fill=t.txt2, font=TYPE['body'])
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='installed-apps')
        self.future = pool.submit(installed_apps)
        pool.shutdown(wait=False)
        self.root.after(100, self.poll)
        self.win.focus_force()
        self.search.focus_set()

    # ── Window chrome ──────────────────────────────────────

    def _drag_window(self, cv):
        """The shell has no title bar; drag it by its header area."""
        def press(e):
            if e.y < 84 and e.x < self.width - 80:
                self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())
            else:
                self._drag = None
        def move(e):
            if getattr(self, '_drag', None):
                dx, dy = self._drag
                self.win.geometry(f'+{e.x_root-dx}+{e.y_root-dy}')
        cv.bind('<ButtonPress-1>', press, add='+')
        cv.bind('<B1-Motion>', move, add='+')

    def close(self):
        if self._icon_job:
            try:
                self.root.after_cancel(self._icon_job)
            except tk.TclError:
                pass
        self.win.destroy()

    # ── Data ───────────────────────────────────────────────

    def poll(self):
        if not self.win.winfo_exists():
            return
        if not self.future.done():
            self.root.after(100, self.poll)
            return
        try:
            self.apps = self.future.result()
            self.filter()
        except Exception:
            self.apps = []
            self.filter()
            self.status.configure(text='Could not list installed apps. Use Browse files to add a shortcut.')

    def set_tab(self, key):
        self.tab = key
        for name, button in self._tab_buttons.items():
            button.set_selected(name == key)
        self.filter()

    def filter(self):
        query = self.query.get().casefold().strip()
        self.shell.itemconfigure(self._placeholder_item,
                                 state='hidden' if self.query.get() else 'normal')
        apps = [a for a in self.apps if self.tab == 'all' or is_game(a)]
        self.visible = [a for a in apps if query in a['name'].casefold()]
        self.grid.yview_moveto(0)
        self._draw_grid()
        if not self.apps:
            message = 'No installed apps found. Browse for a shortcut to add one.'
        elif not self.visible:
            message = 'No matches. Try another search or browse for a shortcut.'
        else:
            message = None
        self._update_footer(message)

    # ── Grid ───────────────────────────────────────────────

    def _tile_xy(self, i):
        col, row = i % self.cols, i // self.cols
        return self.grid_pad + col*(TILE_W+GAP), row*(TILE_H+GAP)

    def _draw_grid(self):
        g = self.grid
        g.delete('all')
        self._tiles.clear()
        if not self.visible:
            g.configure(scrollregion=(0, 0, 1, 1))
            empty = 'Nothing here yet.' if self.apps else 'No apps to show.'
            g.create_text(int(g.cget('width'))//2, 70, text=empty, fill=self.t.txt2,
                          font=TYPE['body'])
            if DND_OK:
                g.create_text(int(g.cget('width'))//2, 96,
                              text='Drop a shortcut or .exe on this window to add it.',
                              fill=self.t.txt2, font=TYPE['caption'])
            return
        rows = -(-len(self.visible) // self.cols)
        g.configure(scrollregion=(0, 0, int(g.cget('width')), rows*(TILE_H+GAP)))
        for i in range(len(self.visible)):
            self._draw_tile(i)
        self._queue_visible_icons()

    def _draw_tile(self, i, hover=False):
        g, t, entry = self.grid, self.t, self.visible[i]
        tag = f'tile{i}'
        g.delete(tag)
        x, y = self._tile_xy(i)
        chosen = entry['path'] in self.selected
        fill = t.hov if hover or chosen else t.btn
        before = set(g.find_all())
        shape = rounded_rect(g, x, y, x+TILE_W, y+TILE_H, R_TILE, fill=fill,
                             outline=t.accent if chosen else t.border, width=2 if chosen else 1)
        self._tiles[i] = shape
        icon = self._icons.get(entry['path'])
        if icon:
            g.create_image(x+TILE_W//2, y+14+ICON//2, image=icon)
        else:
            rounded_rect(g, x+(TILE_W-ICON)//2, y+14, x+(TILE_W+ICON)//2, y+14+ICON, 10, fill=t.btn_h)
        g.create_text(x+TILE_W//2, y+62, text=clip(entry['name'], 24), fill=t.txt,
                      font=TYPE['caption'], width=TILE_W-12, justify='center', anchor='n')
        if chosen:
            cx, cy = x+TILE_W-14, y+14
            g.create_oval(cx-9, cy-9, cx+9, cy+9, fill=t.accent, outline='')
            g.create_text(cx, cy, text='✓', fill=t.bg, font=TYPE['meta'])
        for item in set(g.find_all()) - before:
            g.addtag_withtag(tag, item)
        g.tag_bind(tag, '<Enter>', lambda e: self._hover(i, True))
        g.tag_bind(tag, '<Leave>', lambda e: self._hover(i, False))
        g.tag_bind(tag, '<Button-1>', lambda e: self.toggle(i))
        g.tag_bind(tag, '<Double-Button-1>', lambda e: self.add_one(i))

    def _hover(self, i, on):
        if i not in self._tiles or i >= len(self.visible):
            return
        self.grid.config(cursor='hand2' if on else '')
        if self.visible[i]['path'] not in self.selected:
            recolor_shape(self.grid, self._tiles[i], self.t.hov if on else self.t.btn)

    def _wheel(self, event):
        if self.visible:
            self.grid.yview_scroll(-1 if event.delta > 0 else 1, 'units')
            self._queue_visible_icons()
        return 'break'

    # Icons come from COM/GDI and must be made on the Tk thread, so load the
    # visible ones a few at a time to keep scrolling and typing responsive.
    def _queue_visible_icons(self):
        g = self.grid
        top = g.canvasy(0)
        bottom = top + int(g.cget('height'))
        first = max(0, int(top // (TILE_H+GAP)) * self.cols)
        last = min(len(self.visible), (int(bottom // (TILE_H+GAP)) + 2) * self.cols)
        self._icon_queue = [i for i in range(first, last)
                            if self.visible[i]['path'] not in self._icons]
        if self._icon_queue and not self._icon_job:
            self._icon_job = self.root.after(10, self._load_icons)

    def _load_icons(self):
        self._icon_job = None
        if not self.win.winfo_exists():
            return
        for _ in range(4):
            if not self._icon_queue:
                return
            i = self._icon_queue.pop(0)
            if i >= len(self.visible):
                continue
            entry = self.visible[i]
            self._icons[entry['path']] = get_icon(entry['path'], ICON, entry.get('icon_path'))
            self._draw_tile(i)
        self._icon_job = self.root.after(10, self._load_icons)

    # ── Selection ──────────────────────────────────────────

    def toggle(self, i):
        entry = self.visible[i]
        if entry['path'] in self.selected:
            del self.selected[entry['path']]
        else:
            self.selected[entry['path']] = entry
        self._draw_tile(i, hover=True)
        self._update_footer()

    def _update_footer(self, message=None):
        count = len(self.selected)
        if message is None:
            if count:
                message = f'{count} selected · double-click adds one straight away'
            elif self.apps:
                shown = len(self.visible)
                message = f'{shown} app{"s" if shown != 1 else ""} · click to select'
            else:
                message = self.status.cget('text')
        self.status.configure(text=message)
        label = f'Add {count} app{"s" if count != 1 else ""}' if count else 'Add apps'
        if self.add_button:
            self.add_button.destroy()
        self.add_button = RoundedButton(self.shell, label, self.add_selected, self.t, accent=bool(count))
        self.add_button.configure(bg=self.t.bg)
        right = self.width - SIDE
        add_w = int(self.add_button.cget('width'))
        self.shell.create_window(right, self._footer_y+18, window=self.add_button, anchor='e')
        self.shell.coords(self._browse_item, right - add_w - 8 - self._browse_w, self._footer_y+18)

    def add_one(self, i):
        self.on_add([self.visible[i]])
        self.close()

    def add_selected(self):
        if not self.selected and len(self.visible) == 1:
            self.selected[self.visible[0]['path']] = self.visible[0]   # Enter on a unique match
        entries = list(self.selected.values())
        if entries:
            self.on_add(entries)
            self.close()
        else:
            self.status.configure(text='Select one or more apps first.')

    # ── Files and drops ────────────────────────────────────

    def _add_paths(self, paths):
        entries, rejected = [], []
        for path in paths:
            try:
                entries.append(app_entry(path))
            except ValueError:
                rejected.append(path)
        if entries:
            self.on_add(entries)
            self.close()
        elif rejected:
            self.status.configure(text='Only .exe, .lnk, .url and .appref-ms files can be added.')

    def _on_drop(self, event):
        try:
            paths = self.win.tk.splitlist(event.data)
        except tk.TclError:
            paths = [event.data]
        self._add_paths(paths)

    def browse(self):
        self.win.attributes('-topmost', False)
        paths = filedialog.askopenfilenames(parent=self.win, title='Choose apps or game shortcuts',
                 filetypes=[('Apps and shortcuts', '*.exe *.lnk *.url *.appref-ms'), ('All files', '*.*')])
        if self.win.winfo_exists():
            self.win.attributes('-topmost', True)
            self._add_paths(paths)
