"""Release notes and responsive update progress; Tk stays on its own thread."""
import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor

from desktop_widgets.theme import Theme
from desktop_widgets.ui.components import RoundedButton, release_notes_view
from desktop_widgets.services.screens import area_for
from desktop_widgets.services import updater


class UpdateScreen:
    def __init__(self, root, release, before_install=lambda: None, theme=None):
        self.root, self.release, self.before_install = root, release, before_install
        self.theme = t = theme or Theme()
        self.busy = False
        self._poll_id = None
        self.events = queue.SimpleQueue()
        self.win = tk.Toplevel(root)
        self.win.title('DesktopWidget update')
        self.win.configure(bg=t.bg)
        left, top, right, bottom = area_for(root, root.winfo_pointerx(), root.winfo_pointery())
        w, h = min(620, right-left-40), min(620, bottom-top-40)
        self.win.geometry(f'{w}x{h}+{left+(right-left-w)//2}+{top+(bottom-top-h)//2}')
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        self.win.bind('<Escape>', lambda e: self.close())
        tk.Label(self.win, text='A fresh update is ready', font=('Segoe UI', 22, 'bold'),
                 bg=t.bg, fg=t.txt).pack(anchor='w', padx=24, pady=(24, 8))
        tk.Label(self.win, text=f'Installed {updater.VERSION}  →  {release["tag_name"]}',
                 font=('Segoe UI', 11), bg=t.bg, fg=t.accent).pack(anchor='w', padx=24)
        tk.Label(self.win, text='WHAT’S NEW', font=('Segoe UI', 9, 'bold'),
                 bg=t.bg, fg=t.txt2).pack(anchor='w', padx=24, pady=(24, 8))
        notes_frame = release_notes_view(self.win, release.get('body') or
                                         'Improvements and fixes for DesktopWidget.', t)
        notes_frame.pack(fill='both', expand=True, padx=24)
        self.status = tk.Label(self.win, text='Your widgets and settings will be kept. The app will restart.',
                               bg=t.bg, fg=t.txt2, wraplength=w-48, justify='left')
        self.status.pack(fill='x', padx=24, pady=(16, 8))
        self.progress = tk.Canvas(self.win, height=6, bg=t.btn, highlightthickness=0)
        self.progress.pack(fill='x', padx=24, pady=(0, 16))
        self.actions = tk.Frame(self.win, bg=t.bg)
        self.actions.pack(fill='x', padx=24, pady=(0, 24))
        self.show_actions('Download and restart')
        self.win.grab_set()
        self.win.lift()

    def show_actions(self, label):
        for child in self.actions.winfo_children(): child.destroy()
        RoundedButton(self.actions, 'Later', self.close, self.theme).pack(side='left')
        RoundedButton(self.actions, label, self.start, self.theme, accent=True).pack(side='right')

    def close(self):
        if not self.busy:
            if self._poll_id:
                self.root.after_cancel(self._poll_id)
                self._poll_id = None
            self.win.grab_release()
            self.win.destroy()

    def start(self):
        if self.busy: return
        self.before_install()
        self.busy = True
        for child in self.actions.winfo_children(): child.destroy()
        self.status.configure(text='Preparing download…')
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='update-install')
        self.future = pool.submit(updater.apply_update, self.release,
                                  progress=lambda label, fraction: self.events.put((label, fraction)),
                                  restart=False)
        pool.shutdown(wait=False)
        self._poll_id = self.root.after(100, self.poll)

    def poll(self):
        if self._poll_id:
            self.root.after_cancel(self._poll_id)
            self._poll_id = None
        if not self.win.winfo_exists():
            return
        latest = None
        while not self.events.empty(): latest = self.events.get()
        if latest:
            label, fraction = latest
            self.status.configure(text=label + (f' · {fraction:.0%}' if fraction is not None else '…'))
            self.progress.delete('all')
            self.progress.create_rectangle(0, 0, self.progress.winfo_width() *
                (fraction if fraction is not None else 0.12), 6, fill=self.theme.accent, outline='')
        if not self.future.done():
            self._poll_id = self.root.after(100, self.poll)
            return
        try:
            restart = self.future.result()
            if not callable(restart):
                raise RuntimeError('Check your connection and available disk space, then try again.')
            restart()  # Restart and exit on the main thread, after the worker has finished.
        except Exception as exc:
            self.busy = False
            self.status.configure(text=f'Update could not finish. {exc}')
            self.show_actions('Try again')
