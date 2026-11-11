"""Create a folder stack: name it and tick the app folders that go in it."""
import tkinter as tk

from desktop_widgets import config
from desktop_widgets import theme as th
from desktop_widgets.theme import CHROMA, TYPE, R_CTRL, on_color
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.components import paint_shell, RoundedButton, thin_scrollbar
from desktop_widgets.ui.drawing import rounded_rect

ROW_H = 48


class StackDialog:
    def __init__(self, mgr, preselect=None):
        self.mgr = mgr
        self.t = t = config.get_theme(mgr.data)
        stacked = mgr.stacked_ids()
        self.folders = [g for g in mgr.data["groups"] if g["id"] not in stacked]
        self.chosen = [g["id"] for g in self.folders if g["id"] == preselect]

        left, top, right, bottom = area_for(mgr.root, mgr.root.winfo_pointerx(),
                                            mgr.root.winfo_pointery())
        list_h = min(max(1, len(self.folders)) * (ROW_H + 4), 360)
        width = min(520, right - left - 40)
        height = min(196 + list_h + 92, bottom - top - 40)
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes('-transparentcolor', CHROMA)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=CHROMA)
        self.win.geometry(f'{width}x{height}+{left + (right - left - width) // 2}'
                          f'+{top + (bottom - top - height) // 2}')
        self.win.bind('<Escape>', lambda e: self.close())
        cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        cv.pack(fill='both', expand=True)
        paint_shell(cv, width, height, t, 'Create a stack', self.close,
                    'Flip through several folders in one widget')

        # Name field
        tk.Label(cv, text='Stack name', bg=t.bg, fg=t.txt, font=TYPE['body']).place(x=28, y=88)
        rounded_rect(cv, 28, 112, width - 28, 148, R_CTRL, fill=t.btn, outline=t.border)
        cv.create_line(28 + R_CTRL, 147, width - 28 - R_CTRL, 147, fill=t.accent, width=2)
        self.name = tk.StringVar(value='Games' if any('game' in g['name'].lower() for g in self.folders)
                                 else 'My folders')
        entry = tk.Entry(cv, textvariable=self.name, bg=t.btn, fg=t.txt, insertbackground=t.txt,
                         selectbackground=t.accent, selectforeground=on_color(t.accent),
                         font=TYPE['body'], relief='flat', highlightthickness=0, borderwidth=0)
        cv.create_window(40, 130, window=entry, anchor='w', width=width - 80, height=24)
        entry.select_range(0, 'end')
        entry.bind('<Return>', lambda e: self.create())

        tk.Label(cv, text='Folders in this stack', bg=t.bg, fg=t.txt,
                 font=TYPE['body']).place(x=28, y=164)
        holder = tk.Frame(cv, bg=t.bg)
        cv.create_window(28, 192, window=holder, anchor='nw', width=width - 56,
                         height=height - 192 - 88)
        self.list = tk.Canvas(holder, bg=t.bg, highlightthickness=0)
        self.list.pack(side='left', fill='both', expand=True)
        bar, self._sb = thin_scrollbar(holder, self.list, t, bg=t.bg)
        bar.pack(side='right', fill='y')
        self.list.bind('<MouseWheel>', lambda e: (self.list.yview_scroll(int(-e.delta / 120), 'units'),
                                                  self._sb()))
        self.list.bind('<Configure>', lambda e: self._draw_rows())

        # Footer
        cv.create_line(1, height - 72, width - 1, height - 72, fill=t.border)
        self.status = tk.Label(cv, text='', bg=t.bg, fg=t.txt2, font=TYPE['caption'])
        self.status.place(x=28, y=height - 48, anchor='w')
        self.create_button = None
        self._footer = (cv, width, height)
        RoundedButton(cv, 'Cancel', self.close, t, width=96, height=32).place(
            x=width - 28 - 96 - 8 - 132, y=height - 52)
        self._update_footer()
        if not self.folders:
            self.status.configure(text='Every folder is already in a stack.')
        self.win.focus_force()
        entry.focus_set()

    def _draw_rows(self):
        t, c = self.t, self.list
        c.delete('all')
        width = c.winfo_width()
        for i, g in enumerate(self.folders):
            y = i * (ROW_H + 4)
            on = g['id'] in self.chosen
            tag = f'row{i}'
            rounded_rect(c, 0, y, width, y + ROW_H, R_CTRL, fill=t.btn,
                         outline=t.accent if on else t.border)
            bx, by = 16, y + ROW_H // 2
            if on:
                rounded_rect(c, bx, by - 9, bx + 18, by + 9, 4, fill=t.accent)
                c.create_text(bx + 9, by, text=th.ICON['check'], fill=on_color(t.accent),
                              font=(th.ICON_FONT, -11))
            else:
                rounded_rect(c, bx, by - 9, bx + 18, by + 9, 4, fill=t.btn, outline=t.txt2)
            c.create_text(48, by, text=g['name'], anchor='w', fill=t.txt, font=TYPE['body'])
            n = len(g.get('apps', []))
            label = f"{n} app{'s' if n != 1 else ''}"
            if on and len(self.chosen) > 1:
                label = f"Tab {self.chosen.index(g['id']) + 1}  ·  " + label
            c.create_text(width - 16, by, text=label, anchor='e', fill=t.txt2, font=TYPE['caption'])
            c.create_rectangle(0, y, width, y + ROW_H, fill='', outline='', tags=tag)
            c.tag_bind(tag, '<ButtonRelease-1>', lambda e, gid=g['id']: self.toggle(gid))
            c.tag_bind(tag, '<Enter>', lambda e: c.config(cursor='hand2'))
            c.tag_bind(tag, '<Leave>', lambda e: c.config(cursor=''))
        c.configure(scrollregion=(0, 0, width, len(self.folders) * (ROW_H + 4)))
        self._sb()

    def toggle(self, gid):
        if gid in self.chosen:
            self.chosen.remove(gid)
        else:
            self.chosen.append(gid)
        self._draw_rows()
        self._update_footer()

    def _update_footer(self):
        cv, width, height = self._footer
        if self.create_button:
            self.create_button.destroy()
        n = len(self.chosen)
        self.create_button = RoundedButton(cv, f'Stack {n} folder{"s" if n != 1 else ""}' if n else 'Create',
                                           self.create, self.t, accent=bool(n), width=132, height=32)
        self.create_button.place(x=width - 28 - 132, y=height - 52)
        if n:
            self.status.configure(text='Tabs follow the order you tick them in.')

    def create(self):
        if not self.chosen:
            self.status.configure(text='Tick at least one folder.')
            return
        name = self.name.get().strip() or 'Stack'
        self.close()
        self.mgr.create_stack(name, list(self.chosen))

    def close(self):
        self.win.destroy()
