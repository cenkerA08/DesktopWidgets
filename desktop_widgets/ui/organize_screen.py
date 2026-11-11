"""Organize folders: review suggested moves and clean-ups, then apply them."""
import threading
import tkinter as tk

from PIL import ImageTk

from desktop_widgets import config
from desktop_widgets import theme as th
from desktop_widgets.theme import CHROMA, TYPE, R_CTRL, on_color
from desktop_widgets.services import organize
from desktop_widgets.services.screens import area_for
from desktop_widgets.ui.components import paint_shell, RoundedButton, thin_scrollbar
from desktop_widgets.ui.drawing import rounded_rect

ROW_H, HEAD_H = 46, 40

# (plan key, heading, ticked by default, explanation shown under the heading)
SECTIONS = (
    ("moves", "Move to a better folder", True, None),
    ("new_folders", "New folders", True, "Groups apps that are mixed into a general folder."),
    ("duplicates", "Same app in two folders", True, None),
    ("broken", "Shortcuts that no longer work", True, "The program was moved or uninstalled."),
    ("not_installed", "Steam games that are not installed", False,
     "Removing only takes the tile away. Steam keeps your game and you can add it back any time."),
    ("names", "Garbled names", True, None),
    ("empty", "Empty folders", True, None),
)


class OrganizeScreen:
    def __init__(self, mgr):
        self.mgr = mgr
        self.t = t = config.get_theme(mgr.data)
        self.plan = None
        self.chosen: set = set()
        self._icons: dict = {}
        self._rows: list = []
        left, top, right, bottom = area_for(mgr.root, mgr.root.winfo_pointerx(), mgr.root.winfo_pointery())
        self.W, self.H = W, H = min(640, right - left - 40), min(680, bottom - top - 40)
        self.win = tk.Toplevel(mgr.root)
        self.win.overrideredirect(True)
        self.win.attributes("-transparentcolor", CHROMA)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=CHROMA)
        self.win.geometry(f"{W}x{H}+{left + (right - left - W) // 2}+{top + (bottom - top - H) // 2}")
        self.win.bind("<Escape>", lambda e: self.close())
        self.cv = cv = tk.Canvas(self.win, bg=CHROMA, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        paint_shell(cv, W, H, t, "Organize folders", self.close,
                    "Review the suggestions. Nothing changes until you apply them.")

        holder = tk.Frame(cv, bg=t.bg)
        cv.create_window(28, 88, window=holder, anchor="nw", width=W - 48, height=H - 88 - 76)
        self.list = tk.Canvas(holder, bg=t.bg, highlightthickness=0)
        self.list.pack(side="left", fill="both", expand=True)
        bar, self._sb = thin_scrollbar(holder, self.list, t, bg=t.bg)
        bar.pack(side="right", fill="y")
        self.list.bind("<MouseWheel>", lambda e: (self.list.yview_scroll(int(-e.delta / 120), "units"),
                                                  self._sb()))
        self.list.bind("<ButtonRelease-1>", self._click)
        self.list.bind("<Motion>", self._motion)

        cv.create_line(1, H - 72, W - 1, H - 72, fill=t.border)
        self.status = tk.Label(cv, text="", bg=t.bg, fg=t.txt2, font=TYPE["caption"])
        self.status.place(x=28, y=H - 36, anchor="w")
        self.apply_button = None
        if mgr.data.get("organize_undo"):
            RoundedButton(cv, "Undo last organize", self._undo, t, padx=12, height=32).place(
                x=28, y=H - 52)
            self.status.place(x=200, y=H - 36, anchor="w")
        RoundedButton(cv, "Cancel", self.close, t, width=96, height=32).place(x=W - 28 - 96 - 8 - 140, y=H - 52)
        self._update_footer()
        self.win.focus_force()
        self._start()

    # ── Analysis (Steam genres are fetched in the background) ──

    def _start(self):
        info = self.mgr.data.get("steam_info", {})
        ids = [organize.steam_appid(a) for g in self.mgr.data["groups"] for a in g["apps"]]
        missing = [i for i in ids if i and i not in info]
        if not missing:
            self._analyze(info)
            return
        self._message("Checking Steam for game genres…")
        result = {}
        def run():
            try:
                result["info"] = organize.fetch_steam_info(missing, info)
            except Exception:
                result["info"] = info
        thread = threading.Thread(target=run, daemon=True, name="steam-genres")
        thread.start()
        def wait():
            if not self.win.winfo_exists():
                return
            if thread.is_alive():
                self.win.after(150, wait)
                return
            self.mgr.data["steam_info"] = result.get("info", info)
            config.save(self.mgr.data)
            self._analyze(self.mgr.data["steam_info"])
        wait()

    def _analyze(self, info):
        self.plan = organize.analyze(self.mgr.data, info)
        self.chosen = {item["id"] for key, _, ticked, _ in SECTIONS if ticked
                       for item in self.plan[key]}
        self._draw()
        self._update_footer()

    def _message(self, text):
        self.list.delete("all")
        self.list.create_text(int(self.list.winfo_reqwidth() / 2) or 280, 60, text=text,
                              fill=self.t.txt2, font=TYPE["body"])

    # ── List ───────────────────────────────────────────────

    def _icon(self, app):
        key = app.get("path")
        if key not in self._icons:
            try:
                from desktop_widgets.ui.tiles import icon_image
                self._icons[key] = ImageTk.PhotoImage(icon_image(app, 48, self.t.accent).resize((24, 24)),
                                                      master=self.list)
            except Exception:
                self._icons[key] = None
        return self._icons[key]

    def _describe(self, key, item):
        if key == "moves":
            return item["app"]["name"], f"{item['from_name']}  →  {item['to_name']}", item["app"]
        if key == "new_folders":
            names = ", ".join(m["app"]["name"] for m in item["apps"])
            return (f"Create “{item['name']}” with {len(item['apps'])} apps",
                    f"{names}  (from {item['apps'][0]['from_name']})", None)
        if key == "duplicates":
            folder = next((g["name"] for g in self.mgr.data["groups"] if g["id"] == item["gid"]), "")
            return item["app"]["name"], f"Remove from {folder}, keep it in {item['keep']}", item["app"]
        if key in ("broken", "not_installed"):
            folder = next((g["name"] for g in self.mgr.data["groups"] if g["id"] == item["gid"]), "")
            return item["app"]["name"], f"Remove from {folder}", item["app"]
        if key == "names":
            return item["app"]["name"], f"Rename to “{item['new']}”", item["app"]
        return item["name"], "Delete this empty folder", None

    def _draw(self):
        t, c = self.t, self.list
        c.delete("all")
        self._rows = []
        width = int(c.winfo_width()) if c.winfo_width() > 1 else self.W - 56
        y = 0
        if not organize.count(self.plan):
            c.create_text(width // 2, 50, text="Everything is already tidy.", fill=t.txt, font=TYPE["strong"])
            c.create_text(width // 2, 74, text="Every app sits in a folder that fits it.",
                          fill=t.txt2, font=TYPE["caption"])
            c.configure(scrollregion=(0, 0, width, 120))
            return
        for key, heading, _, note in SECTIONS:
            items = self.plan[key]
            if not items:
                continue
            c.create_text(2, y + 22, text=heading, anchor="w", fill=t.txt, font=TYPE["strong"])
            c.create_text(width - 4, y + 22, text=str(len(items)), anchor="e", fill=t.txt2, font=TYPE["caption"])
            y += HEAD_H if not note else HEAD_H - 6
            if note:
                c.create_text(2, y + 4, text=note, anchor="w", fill=t.txt2, font=TYPE["caption"],
                              width=width - 8)
                y += 22
            for item in items:
                title, detail, app = self._describe(key, item)
                on = item["id"] in self.chosen
                rounded_rect(c, 0, y, width, y + ROW_H, R_CTRL, fill=t.btn,
                             outline=t.accent if on else t.border)
                cy = y + ROW_H // 2
                if on:
                    rounded_rect(c, 14, cy - 9, 32, cy + 9, 4, fill=t.accent)
                    c.create_text(23, cy, text=th.ICON["check"], fill=on_color(t.accent),
                                  font=(th.ICON_FONT, -11))
                else:
                    rounded_rect(c, 14, cy - 9, 32, cy + 9, 4, fill=t.btn, outline=t.txt2)
                tx = 46
                photo = self._icon(app) if app else None
                if photo:
                    c.create_image(58, cy, image=photo)
                    tx = 80
                c.create_text(tx, cy - 9, text=title, anchor="w", fill=t.txt, font=TYPE["body"],
                              width=width - tx - 12)
                c.create_text(tx, cy + 10, text=detail, anchor="w", fill=t.txt2, font=TYPE["caption"],
                              width=width - tx - 12)
                self._rows.append((y, y + ROW_H, item["id"]))
                y += ROW_H + 4
            y += 10
        c.configure(scrollregion=(0, 0, width, y))
        self._sb()

    def _row_at(self, e):
        y = self.list.canvasy(e.y)
        return next((rid for y1, y2, rid in self._rows if y1 <= y <= y2), None)

    def _motion(self, e):
        self.list.config(cursor="hand2" if self._row_at(e) else "")

    def _click(self, e):
        rid = self._row_at(e)
        if rid is None:
            return
        self.chosen.symmetric_difference_update({rid})
        top = self.list.yview()[0]
        self._draw()
        self.list.yview_moveto(top)
        self._update_footer()

    # ── Footer ─────────────────────────────────────────────

    def _update_footer(self):
        if self.apply_button:
            self.apply_button.destroy()
        n = len(self.chosen)
        self.apply_button = RoundedButton(self.cv, f"Apply {n} change{'s' if n != 1 else ''}" if n else "Apply",
                                          self._apply, self.t, accent=bool(n), width=140, height=32)
        self.apply_button.place(x=self.W - 28 - 140, y=self.H - 52)
        if self.plan is not None:
            self.status.configure(text=f"{n} of {organize.count(self.plan)} selected" if organize.count(self.plan)
                                  else "")

    def _apply(self):
        if not self.plan or not self.chosen:
            return
        plan, chosen = self.plan, set(self.chosen)
        self.close()
        self.mgr.apply_organize(plan, chosen)

    def _undo(self):
        self.close()
        self.mgr.undo_organize()

    def close(self):
        try: self.win.destroy()
        except tk.TclError: pass
