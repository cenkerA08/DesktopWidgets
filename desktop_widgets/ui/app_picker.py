"""Search registered Windows apps or browse to an executable/launcher shortcut."""
import tkinter as tk
from tkinter import filedialog
from concurrent.futures import ThreadPoolExecutor

from desktop_widgets.services.apps import app_entry, installed_apps
from desktop_widgets.utils import get_icon
from desktop_widgets.ui.components import RoundedButton
from desktop_widgets import config


class AppPicker:
    def __init__(self, mgr, on_add):
        self.root = mgr.root
        self.on_add = on_add
        self.apps = []
        self.visible = []
        t = config.get_theme(mgr.data)
        self.win = tk.Toplevel(mgr.root)
        self.win.title('Add apps')
        self.win.configure(bg=t.bg)
        from desktop_widgets.services.screens import area_for
        left, top, right, bottom = area_for(
            mgr.root, mgr.root.winfo_pointerx(), mgr.root.winfo_pointery())
        sw, sh = right - left, bottom - top
        margin = min(48, max(16, min(sw, sh) // 12))
        width, height = min(680, sw - 2 * margin), min(660, sh - 2 * margin)
        x, y = left + (sw - width) // 2, top + (sh - height) // 2
        self.win.geometry(f'{width}x{height}+{x}+{y}')
        self.win.minsize(min(420, width), min(440, height))

        header = tk.Frame(self.win, bg=t.bg)
        header.pack(fill='x', padx=28, pady=(24, 16))
        tk.Label(header, text='ADD TO YOUR DESKTOP', bg=t.bg, fg=t.accent,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        tk.Label(header, text='Apps and games', bg=t.bg, fg=t.txt,
                 font=('Segoe UI', 21, 'bold')).pack(anchor='w', pady=(4, 4))
        tk.Label(header, text='Find an installed app, or browse to a game shortcut.',
                 bg=t.bg, fg=t.txt2, justify='left',
                 font=('Segoe UI', 10)).pack(anchor='w')

        self.query = tk.StringVar()
        search_frame = tk.Frame(self.win, bg=t.btn, highlightthickness=1,
                                highlightbackground=t.border)
        search_frame.pack(fill='x', padx=28, pady=(0, 16))
        tk.Label(search_frame, text='⌕', bg=t.btn, fg=t.txt2,
                 font=('Segoe UI', 16)).pack(side='left', padx=(12, 4))
        search = tk.Entry(search_frame, textvariable=self.query, bg=t.btn, fg=t.txt,
                          insertbackground=t.txt, font=('Segoe UI', 11),
                          relief='flat', highlightthickness=0, borderwidth=0)
        search.pack(side='left', fill='x', expand=True, padx=(0, 12), ipady=10)
        search.focus_set()
        self.query.trace_add('write', lambda *_: self.filter())

        results = tk.Frame(self.win, bg=t.hdr, highlightthickness=1,
                           highlightbackground=t.border)
        results.pack(fill='both', expand=True, padx=28)
        list_frame = tk.Frame(results, bg=t.btn)
        list_frame.pack(fill='both', expand=True, padx=1, pady=1)
        self.list = tk.Listbox(list_frame, bg=t.btn, fg=t.txt,
                               selectbackground=t.accent, selectforeground=t.bg,
                               relief='flat', highlightthickness=0,
                               selectmode='extended', exportselection=False,
                               font=('Segoe UI', 10), activestyle='none',
                               borderwidth=0)
        scrollbar = tk.Scrollbar(list_frame, command=self.list.yview,
                                 relief='flat', borderwidth=0,
                                 troughcolor=t.btn, bg=t.hdr,
                                 activebackground=t.accent)
        scrollbar.pack(side='right', fill='y')
        self.list.pack(side='left', fill='both', expand=True)
        self.list.configure(yscrollcommand=scrollbar.set)
        self.list.bind('<Double-Button-1>', lambda e: self.add_selected())
        self.list.bind('<Return>', lambda e: self.add_selected())
        self.list.bind('<<ListboxSelect>>', self.preview_selection)

        preview = tk.Frame(self.win, bg=t.btn, highlightthickness=1,
                           highlightbackground=t.border)
        preview.pack(fill='x', padx=28, pady=(12, 0))
        self.preview_icon = tk.Label(preview, bg=t.btn, width=56, height=56)
        self.preview_icon.pack(side='left', padx=(12, 8), pady=8)
        details = tk.Frame(preview, bg=t.btn)
        details.pack(side='left', fill='x', expand=True)
        self.preview_name = tk.Label(details, text='Select an app to preview its icon',
                                     bg=t.btn, fg=t.txt, anchor='w', font=('Segoe UI', 10, 'bold'))
        self.preview_name.pack(fill='x')
        self.preview_hint = tk.Label(details, text='Use a game shortcut for its original artwork.',
                                     bg=t.btn, fg=t.txt2, anchor='w', font=('Segoe UI', 9))
        self.preview_hint.pack(fill='x')
        self._preview_image = None

        footer = tk.Frame(self.win, bg=t.bg)
        footer.pack(fill='x', padx=28, pady=(12, 22))
        self.status = tk.Label(footer, text='Loading installed apps…', bg=t.bg,
                               fg=t.txt2, font=('Segoe UI', 9))
        self.status.pack(side='left', anchor='w')
        actions = tk.Frame(footer, bg=t.bg)
        actions.pack(side='right')
        RoundedButton(actions, 'Browse files…', self.browse, t).pack(side='left', padx=(0, 8))
        RoundedButton(actions, 'Add selected', self.add_selected, t, accent=True).pack(side='left')
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='installed-apps')
        self.future = pool.submit(installed_apps)
        pool.shutdown(wait=False)
        self.root.after(100, self.poll)

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
            self.status.configure(text='Could not list installed apps. Use Browse files to add a shortcut.')

    def filter(self):
        query = self.query.get().casefold().strip()
        self.visible = [a for a in self.apps if query in a['name'].casefold()]
        self.list.delete(0, 'end')
        for app in self.visible:
            self.list.insert('end', app['name'])
        if not self.apps:
            message = 'No installed apps found. Browse for a shortcut to add one.'
        elif not self.visible:
            message = 'No matches. Try another search or browse for a shortcut.'
        else:
            message = f'{len(self.visible)} apps · Select one or more to add'
        self.status.configure(text=message)

    def add_selected(self):
        entries = [self.visible[i] for i in self.list.curselection()]
        if entries:
            self.on_add(entries)
            self.win.destroy()

    def preview_selection(self, event=None):
        selected = self.list.curselection()
        if not selected or selected[0] >= len(self.visible):
            return
        entry = self.visible[selected[0]]
        self.preview_name.configure(text=entry['name'])
        self.preview_hint.configure(text='Windows shortcut' if entry['path'].lower().endswith('.lnk')
                                    else 'Installed app')
        self._preview_image = get_icon(entry['path'], 48, entry.get('icon_path'))
        self.preview_icon.configure(image=self._preview_image)

    def browse(self):
        paths = filedialog.askopenfilenames(parent=self.win, title='Choose apps or game shortcuts',
                 filetypes=[('Apps and shortcuts', '*.exe *.lnk *.url *.appref-ms'), ('All files', '*.*')])
        entries = []
        try:
            for path in paths:
                entries.append(app_entry(path))
        except ValueError as exc:
            self.status.configure(text=str(exc))
            return
        if entries:
            self.on_add(entries)
            self.win.destroy()
