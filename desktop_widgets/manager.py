"""
manager.py — The application orchestrator.
Creates and manages all widgets, handles menus, reflow, theme animation.
"""
from __future__ import annotations
import os, sys, threading
import tkinter as tk
from tkinter import filedialog

import desktop_widgets.config as config
from desktop_widgets.theme import CHROMA, MARGIN
from desktop_widgets.utils import ask_string, ask_confirm, push_desktop, allow_dnd_from_explorer, launch_app, task_exists, create_task, remove_task, create_desktop_shortcut
from desktop_widgets.widgets.group_widget import GroupWidget
from desktop_widgets.widgets.stack_widget import StackWidget
from desktop_widgets.widgets.statsplus_widget import StatsPlusWidget
from desktop_widgets.widgets.notes_widget import NotesWidget
from desktop_widgets.widgets.docs_widget import DocsWidget
from desktop_widgets.widgets.media_widget import MediaWidget
from desktop_widgets.ui.context_menu import ContextMenu
from desktop_widgets.ui.settings_screen import SettingsScreen
from desktop_widgets.ui.tray_bar import TrayBar

try:
    from tkinterdnd2 import TkinterDnD
    DND_OK = True
except ImportError:
    DND_OK = False

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_OK = True
except ImportError:
    TRAY_OK = False


class Manager:
    def __init__(self) -> None:
        self.data = config.load()
        import desktop_widgets.theme as _theme
        _theme.apply_sizes(self.data)   # saved icon / tile size settings
        from desktop_widgets.services.apps import repair_missing_shortcuts
        if repair_missing_shortcuts(self.data):     # game shortcuts deleted from the desktop
            for group in self.data["groups"]:
                for app in group["apps"]:
                    if app.get("launch"):
                        config.URL_APPS[app["path"]] = {"launch": app["launch"],
                                                        "icon_path": app.get("icon_path")}
            config.save(self.data)
        self.wins:         dict[int, GroupWidget]  = {}
        self.stack_wins:   dict[int, StackWidget]  = {}
        self.statsplus_win: StatsPlusWidget | None = None
        self.notes_win:    NotesWidget | None      = None
        self.docs_wins:    dict[int, DocsWidget]   = {}
        self.media_win:    MediaWidget | None      = None
        self.settings_screen: SettingsScreen | None = None
        self.tray    = None
        self.tray_bar: TrayBar | None = None

        # Root window (invisible)
        self.root = TkinterDnD.Tk() if DND_OK else tk.Tk()
        self.root.withdraw()
        _theme.init_fonts(self.root)

        # Build widgets (folders inside a stack are shown by the stack)
        stacked = self.stacked_ids()
        for g in self.data["groups"]:
            if g["id"] not in stacked:
                self._create_group(g)
        for st in self.data.get("stacks", []):
            self._create_stack(st)

        if self.data.get("statsplus", {}).get("enabled"):
            try: self.statsplus_win = StatsPlusWidget(self)
            except Exception as e: print(f"[manager] statsplus error: {e}")

        if self.data.get("notes", {}).get("enabled"):
            try: self.notes_win = NotesWidget(self)
            except Exception as e: print(f"[manager] notes error: {e}")

        for dw_blk in self.data.get("docs_widgets", []):
            try:
                dw = DocsWidget(self, dw_blk)
                self.docs_wins[dw_blk["id"]] = dw
            except Exception as e:
                print(f"[manager] docs error: {e}")

        if self.data.get("media", {}).get("enabled"):
            try: self.media_win = MediaWidget(self)
            except Exception as e: print(f"[manager] media error: {e}")

        self.tray_bar = TrayBar(self)

        # System tray icon
        if TRAY_OK:
            threading.Thread(target=self._tray_loop, daemon=True).start()

        self._add_picker: tk.Toplevel | None = None

        # Quick launcher on a system-wide shortcut
        from desktop_widgets.services.hotkey import Hotkey, DEFAULT
        self.launcher = None
        self.hotkey = Hotkey(self.root, self.toggle_launcher)
        self.hotkey.set(self.data.setdefault("launcher_hotkey", DEFAULT))
        from desktop_widgets.services.screens import work_areas
        self._screen_areas = work_areas(self.root)
        self.root.after(2000, self._check_screens)
        self._wall_sig = None
        self.root.after(3000, self._check_wallpaper)

    def _check_screens(self):
        """Recover widgets after a display is removed or its work area changes."""
        from desktop_widgets.services.screens import work_areas, area_for, clamp
        areas = work_areas(self.root)
        widgets = self.all_widgets()
        if areas != self._screen_areas and not any(w._mode for w in widgets):
            # Displays changed (often right after sign-in, before the real
            # resolution or second monitor is ready). Put every widget back at
            # its saved spot; never save the squeezed positions.
            self._screen_areas = areas
            if self.tray_bar:
                self.tray_bar.reposition()
            for widget in widgets:
                widget.restore_home()
        self.root.after(2000, self._check_screens)

    def uses_wallpaper_theme(self) -> bool:
        blocks = (self.data.get("groups", []) + self.data.get("stacks", []) +
                  self.data.get("docs_widgets", []) +
                  [self.data.get(k, {}) for k in ("statsplus", "notes", "media")])
        return (self.data.get("theme_preset") == "Wallpaper" or
                any((b.get("theme_override") or {}).get("__preset__") == "Wallpaper" for b in blocks))

    def _check_wallpaper(self):
        """Follow the wallpaper: rebuild the theme when the picture changes."""
        try:
            if self.uses_wallpaper_theme():
                from desktop_widgets.services import wallpaper
                sig = wallpaper.signature()
                if sig and sig != self._wall_sig:
                    first = self._wall_sig is None
                    self._wall_sig = sig
                    live = wallpaper.theme()
                    if live is not None and self.data.get("theme_preset") == "Wallpaper":
                        changed = self.data.get("theme") != live.to_dict()
                        self.data["theme"] = live.to_dict()
                        if changed:
                            config.save(self.data)
                    if not first or live is not None:
                        self.apply_theme()
        except Exception as exc:
            print(f"[wallpaper] {exc}")
        self.root.after(15000, self._check_wallpaper)

    # ── Widget creation ────────────────────────────────────

    def _create_group(self, g: dict) -> GroupWidget:
        gw = GroupWidget(self, g)
        gw.bind_events()
        self.wins[g["id"]] = gw
        return gw

    def _create_stack(self, st: dict) -> StackWidget:
        sw = StackWidget(self, st)
        sw.bind_events()
        self.stack_wins[st["id"]] = sw
        return sw

    def all_widgets(self) -> list:
        """Every widget window on the desktop."""
        return (list(self.wins.values()) + list(self.stack_wins.values()) +
                [w for w in (self.statsplus_win, self.notes_win, self.media_win) if w] +
                list(self.docs_wins.values()))

    # ── Folder stacks ──────────────────────────────────────

    def stacked_ids(self) -> set:
        return {gid for st in self.data.get("stacks", []) for gid in st.get("groups", [])}

    def stack_of(self, gid: int) -> dict | None:
        return next((st for st in self.data.get("stacks", []) if gid in st.get("groups", [])), None)

    def group_widget(self, gid):
        """The widget showing folder `gid`: its own window or the stack holding it."""
        if gid in self.wins:
            return self.wins[gid]
        st = self.stack_of(gid)
        return self.stack_wins.get(st["id"]) if st else None

    def _refresh_group(self, gid) -> None:
        gw = self.group_widget(gid)
        if gw:
            gw._refresh_size(); gw.redraw()

    def create_stack(self, name: str, gids: list[int]) -> None:
        """Put existing folders into a new stack, where the first one was."""
        gids = [gid for gid in gids if gid not in self.stacked_ids()]
        if not gids:
            return
        first = next(g for g in self.data["groups"] if g["id"] == gids[0])
        gw = self.wins.get(gids[0])
        x, y = (gw._win_x(), gw._win_y()) if gw else (first.get("x", 60), first.get("y", 60))
        cols = max((g.get("cols", 5) for g in self.data["groups"] if g["id"] in gids), default=5)
        st = {"id": self.data["next_id"], "name": name, "groups": gids, "active": 0,
              "cols": cols, "x": x, "y": y, "collapsed": False, "theme_override": None}
        self.data["next_id"] += 1
        self.data.setdefault("stacks", []).append(st)
        for gid in gids:
            if gid in self.wins:
                self.wins.pop(gid).destroy()
        config.save(self.data)
        self._create_stack(st)

    def add_to_stack(self, gid: int, sid: int) -> None:
        st = next((s for s in self.data.get("stacks", []) if s["id"] == sid), None)
        if not st or gid in self.stacked_ids():
            return
        st["groups"].append(gid)
        st["active"] = len(st["groups"]) - 1
        if gid in self.wins:
            self.wins.pop(gid).destroy()
        config.save(self.data)
        self._refresh_group(gid)

    def take_out_of_stack(self, gid: int) -> None:
        """Give a folder its own widget again, next to the stack."""
        st = self.stack_of(gid)
        if not st:
            return
        sw = self.stack_wins.get(st["id"])
        st["groups"].remove(gid)
        st["active"] = max(0, min(st.get("active", 0), len(st["groups"]) - 1))
        group = next(g for g in self.data["groups"] if g["id"] == gid)
        if sw:
            x, y, w, h = sw.rect()
            group["x"], group["y"] = x + w + MARGIN, y
        group["collapsed"] = False
        if not st["groups"]:
            self._drop_stack(st)
        elif sw:
            sw._refresh_size(); sw.redraw()
        config.save(self.data)
        self._create_group(group)

    def unstack(self, sid: int) -> None:
        st = next((s for s in self.data.get("stacks", []) if s["id"] == sid), None)
        if not st:
            return
        sw = self.stack_wins.get(sid)
        x, y = (sw._win_x(), sw._win_y()) if sw else (st.get("x", 60), st.get("y", 60))
        gids = list(st["groups"])
        self._drop_stack(st)
        for i, gid in enumerate(gids):
            group = next((g for g in self.data["groups"] if g["id"] == gid), None)
            if group:
                group["x"], group["y"], group["collapsed"] = x + 24 * i, y + 24 * i, False
                self._create_group(group)
        config.save(self.data)

    def _drop_stack(self, st: dict) -> None:
        sw = self.stack_wins.pop(st["id"], None)
        if sw:
            sw.destroy()
        self.data["stacks"] = [s for s in self.data.get("stacks", []) if s is not st]

    def rename_stack(self, st: dict) -> None:
        t = config.get_theme(self.data)
        name = ask_string(self.root, "Rename stack", "Stack name", initial=st["name"], theme=t)
        if name and name.strip():
            st["name"] = name.strip()
            config.save(self.data)
            if st["id"] in self.stack_wins:
                self.stack_wins[st["id"]].redraw()

    def new_stack_folder(self, st: dict) -> None:
        """A new, empty folder created straight inside a stack."""
        t = config.get_theme(self.data)
        name = ask_string(self.root, "New folder", "Folder name", theme=t)
        if not name or not name.strip():
            return
        g = {"id": self.data["next_id"], "name": name.strip(), "apps": [], "x": 60, "y": 60,
             "cols": st.get("cols", 5), "collapsed": False, "theme_override": None}
        self.data["next_id"] += 1
        self.data["groups"].append(g)
        st["groups"].append(g["id"])
        st["active"] = len(st["groups"]) - 1
        config.save(self.data)
        self._refresh_group(g["id"])

    def move_in_stack(self, gid: int, step: int) -> None:
        st = self.stack_of(gid)
        if not st:
            return
        ids = st["groups"]
        i = ids.index(gid)
        j = max(0, min(len(ids) - 1, i + step))
        ids[i], ids[j] = ids[j], ids[i]
        st["active"] = j
        config.save(self.data)
        self._refresh_group(gid)

    def new_stack_dialog(self, preselect: int | None = None) -> None:
        from desktop_widgets.ui.stack_dialog import StackDialog
        StackDialog(self, preselect)

    def stack_ctx(self, e: tk.Event, st: dict) -> None:
        m = self._menu()
        m.add_command(label="➕  New folder in this stack", command=lambda: self.new_stack_folder(st))
        m.add_command(label="✎  Rename stack", command=lambda: self.rename_stack(st))
        m.add_command(label="📂  Unstack all folders", command=lambda: self.unstack(st["id"]))
        m.add_command(label="✨  Organize folders…", command=self.open_organizer)
        m.add_separator()
        m.add_command(label="⚙  Settings", command=lambda: self.open_settings("widgets"))
        m.add_command(label="⏻  Quit", command=self._quit)
        m.tk_popup(e.x_root, e.y_root)

    def stack_tab_ctx(self, e: tk.Event, st: dict, group: dict) -> None:
        gid = group["id"]
        ids = st["groups"]
        m = self._menu()
        m.add_command(label="✎  Rename folder", command=lambda: self.rename_group(group))
        if ids.index(gid) > 0:
            m.add_command(label="Move left", command=lambda: self.move_in_stack(gid, -1))
        if ids.index(gid) < len(ids) - 1:
            m.add_command(label="Move right", command=lambda: self.move_in_stack(gid, 1))
        m.add_command(label="↗  Take out of stack", command=lambda: self.take_out_of_stack(gid))
        m.add_separator()
        m.add_command(label="✕  Delete folder", command=lambda: self.delete_group(gid))
        m.tk_popup(e.x_root, e.y_root)

    # ── All rects (for snapping / reflow) ─────────────────

    def reset_to_natural_size(self) -> None:
        """
        Called when resize is disabled — snap every widget back to its
        content-driven natural size so nothing stays at a weird manual size.
        """
        import desktop_widgets.theme as _th
        from desktop_widgets.theme import HDR_H

        for gw in self.wins.values():
            if gw._collapsed: continue
            gw.W = gw._natural_w
            gw._full_h = gw._natural_h
            gw.H = gw._full_h
            gw.win.geometry(f"{gw.W}x{gw.H}")
            gw.cv.config(width=gw.W, height=gw.H)
            gw.redraw()

        for sw in self.stack_wins.values():
            if not sw._collapsed:
                sw._refresh_size(); sw.redraw()

        for dw in self.docs_wins.values():
            if dw._collapsed: continue
            dw.W = dw._natural_w
            dw._full_h = dw._natural_h
            dw.H = dw._full_h
            dw.win.geometry(f"{dw.W}x{dw.H}")
            dw.cv.config(width=dw.W, height=dw.H)
            dw.redraw()

        # Notes: reset to default 240×300
        if self.notes_win and not self.notes_win._collapsed:
            self.notes_win.W = 240
            self.notes_win._full_h = 300
            self.notes_win.H = 300
            self.notes_win.win.geometry("240x300")
            self.notes_win.cv.config(width=240, height=300)
            self.notes_win.redraw()

        config.save(self.data)

    def set_group_cols(self, gid: int, cols: int) -> None:
        """Change column count for a group widget and refresh its size."""
        import desktop_widgets.theme as _th
        cols = max(1, min(12, cols))
        group = next((g for g in self.data["groups"] if g["id"] == gid), None)
        if not group: return
        group["cols"] = cols
        config.save(self.data)
        gw = self.wins.get(gid)
        if gw:
            gw._refresh_size()
            gw.redraw()

    def set_stack_cols(self, sid: int, cols: int) -> None:
        st = next((s for s in self.data.get("stacks", []) if s["id"] == sid), None)
        if not st: return
        st["cols"] = max(1, min(12, cols))
        config.save(self.data)
        sw = self.stack_wins.get(sid)
        if sw:
            sw._refresh_size(); sw.redraw()

    def set_docs_cols(self, did: int, cols: int) -> None:
        """Change column count for a docs widget and refresh its size."""
        cols = max(1, min(8, cols))
        blk = next((b for b in self.data.get("docs_widgets", [])
                    if b["id"] == did), None)
        if not blk: return
        blk["cols"] = cols
        config.save(self.data)
        dw = self.docs_wins.get(did)
        if dw:
            dw._refresh_size()
            dw.redraw()

    def all_rects(self, exclude=None) -> list[tuple[int,int,int,int]]:
        return [w.rect() for w in self.all_widgets() if w is not exclude]

    def reflow_after_resize(self, changed_widget, old_h: int, new_h: int) -> None:
        """
        Called when a widget changes height (items added or removed).
        Pushes widgets below down when growing, pulls them up when shrinking.
        delta > 0 → push down (process top-first)
        delta < 0 → pull up  (process bottom-first to avoid conflicts)
        """
        delta = new_h - old_h
        if delta == 0:
            return

        cx, cy, cw, ch = changed_widget.rect()
        from desktop_widgets.services.screens import area_for, clamp
        area = area_for(self.root, cx, cy, cw, ch)

        all_widgets = self.all_widgets()

        below = []
        for w in all_widgets:
            if w is changed_widget:
                continue
            rx, ry, rw, rh = w.rect()
            x_overlap = rx < cx + cw and rx + rw > cx
            if x_overlap and ry > cy and area_for(self.root, rx, ry, rw, rh) == area:
                below.append(w)

        if not below:
            return

        # Growing → top-first so each push doesn't stomp the next
        # Shrinking → bottom-first so each pull doesn't create a gap above
        for w in sorted(below, key=lambda w: w.rect()[1], reverse=(delta < 0)):
            rx, ry, rw, rh = w.rect()
            ny = ry + delta
            rx, ny = clamp(rx, ny, rw, rh, area)
            w.win.geometry(f"+{rx}+{ny}")
            w._save_geometry()

    # ── Collapse reflow ────────────────────────────────────

    def reflow_after_collapse(self, changed_widget) -> None:
        """
        After a widget collapses or expands, shift only the widgets that are
        directly stacked below it (touching chain), not ones far below with a gap.
        """
        from desktop_widgets.theme import HDR_H

        # At call time toggle_collapse has already applied the new height.
        # _full_h is always the expanded height; H is the current (new) height.
        if changed_widget._collapsed:
            # just collapsed: shrank from _full_h to HDR_H
            delta = HDR_H - changed_widget._full_h          # negative → move up
        else:
            # just expanded: grew from HDR_H to _full_h
            delta = changed_widget._full_h - HDR_H          # positive → move down

        if delta == 0:
            return

        cx, cy, cw, ch = changed_widget.rect()
        from desktop_widgets.services.screens import area_for, clamp
        area = area_for(self.root, cx, cy, cw, ch)

        # Old bottom before the size change (H is already updated, delta = new−old)
        old_bottom = cy + ch - delta

        all_widgets = self.all_widgets()

        # Collect candidates: x-overlapping widgets strictly below changed widget
        below = []
        for w in all_widgets:
            if w is changed_widget:
                continue
            rx, ry, rw, rh = w.rect()
            x_overlap = rx < cx + cw and rx + rw > cx
            if x_overlap and ry > cy and area_for(self.root, rx, ry, rw, rh) == area:
                below.append(w)

        if not below:
            return

        # Chain cascade: walk downward, stop as soon as there's a gap.
        # Only widgets that were touching the widget above them get moved.
        below.sort(key=lambda w: w.rect()[1])
        chain_bottom = old_bottom
        to_move: list = []
        for w in below:
            rx, ry, rw, rh = w.rect()
            if ry <= chain_bottom + MARGIN:
                to_move.append(w)
                chain_bottom = ry + rh   # advance chain to this widget's old bottom
            else:
                break                    # gap found — chain ends here

        if not to_move:
            return

        # Moving up → top-first; moving down → bottom-first (prevents stomping)
        for w in sorted(to_move, key=lambda w: w.rect()[1], reverse=(delta < 0)):
            rx, ry, rw, rh = w.rect()
            rx, ny = clamp(rx, ry + delta, rw, rh, area)
            w.win.geometry(f"+{rx}+{ny}")
            w._save_geometry()

    # ── App management ─────────────────────────────────────

    def add_app(self, gid: int) -> None:
        from desktop_widgets.ui.app_picker import AppPicker
        group = next((g for g in self.data['groups'] if g['id'] == gid), None)
        if group is None:
            return
        AppPicker(self, lambda entries: self.add_app_entries(gid, entries), group.get('name'))

    def add_app_entries(self, gid, entries):
        from desktop_widgets.services.apps import cache_store_icon
        group = next((g for g in self.data['groups'] if g['id'] == gid), None)
        if group is None:
            return
        existing = {os.path.normcase(a['path']) for a in group['apps']}
        for entry in entries:
            key = os.path.normcase(entry['path'])
            if key not in existing:
                group['apps'].append(cache_store_icon(dict(entry)))
                if entry.get('launch'):
                    config.URL_APPS[entry['path']] = {'launch': entry['launch'],
                                                      'icon_path': entry.get('icon_path')}
                existing.add(key)
        config.save(self.data)
        self._refresh_group(gid)

    def remove_app(self, path: str, gid: int) -> None:
        t = config.get_theme(self.data)
        if not ask_confirm(self.root, "Remove app?\n(File will not be deleted.)", theme=t):
            return
        group = next((g for g in self.data["groups"] if g["id"] == gid), None)
        if group:
            group["apps"] = [a for a in group["apps"] if a["path"] != path]
        config.save(self.data)
        self._refresh_group(gid)

    # ── Cross-widget drag helpers ──────────────────────────

    def find_group_widget_at(self, x_root: int, y_root: int,
                              exclude_gid: int | None = None
                              ) -> "GroupWidget | None":
        """Return the GroupWidget whose window contains the screen point (x_root, y_root)."""
        targets = list(self.wins.items()) + [(None, sw) for sw in self.stack_wins.values()]
        for gid, gw in targets:
            if gid is not None and gid == exclude_gid:
                continue
            if gid is None and gw.group.get("id") in (None, exclude_gid):
                continue
            try:
                wx = gw._win_x(); wy = gw._win_y()
                ww = gw.win.winfo_width(); wh = gw.win.winfo_height()
                if wx <= x_root <= wx + ww and wy <= y_root <= wy + wh:
                    return gw
            except Exception:
                pass
        return None

    def move_app_to_group(self, app: dict, src_gid: int, dst_gw: "GroupWidget") -> None:
        """Remove app from src group and append it to dst group, then refresh both."""
        src_group = next((g for g in self.data["groups"] if g["id"] == src_gid), None)
        if not src_group:
            return
        src_group["apps"] = [a for a in src_group["apps"] if a["path"] != app["path"]]
        dst_gw.group["apps"].append(app)
        config.save(self.data)
        self._refresh_group(src_gid)
        dst_gw._refresh_size(); dst_gw.redraw()

    def send_app_to_desktop(self, app: dict, src_gid: int) -> None:
        """Create a desktop shortcut and remove the app from its widget."""
        ok = create_desktop_shortcut(app["path"], app["name"])
        if not ok:
            import tkinter.messagebox as mb
            mb.showerror("Error", f"Could not create shortcut for {app['name']}.")
            return
        src_group = next((g for g in self.data["groups"] if g["id"] == src_gid), None)
        if src_group:
            src_group["apps"] = [a for a in src_group["apps"]
                                  if a["path"] != app["path"]]
        config.save(self.data)
        self._refresh_group(src_gid)

    # ── Group management ───────────────────────────────────

    def new_group_dialog(self) -> None:
        t = config.get_theme(self.data)
        name = ask_string(self.root, "New widget", "Name:", theme=t)
        if not name: return
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # Find a free spot
        max_y = max((g.get("y", 60) for g in self.data["groups"]), default=60)
        from desktop_widgets.utils import snap_to_grid
        g = {
            "id":      self.data["next_id"],
            "name":    name.strip(),
            "apps":    [],
            "x":       60,
            "y":       snap_to_grid(max_y + 300),
            "cols":    5,
            "collapsed":     False,
            "theme_override": None,
        }
        self.data["groups"].append(g)
        self.data["next_id"] += 1
        config.save(self.data)
        self._create_group(g)

    def delete_group(self, gid: int) -> None:
        group = next((g for g in self.data["groups"] if g["id"] == gid), None)
        if not group: return
        t = config.get_theme(self.data)
        if not ask_confirm(self.root, f"Delete widget '{group['name']}'?", theme=t):
            return
        if gid in self.wins:
            self.wins[gid].destroy(); del self.wins[gid]
        self.data["groups"] = [g for g in self.data["groups"] if g["id"] != gid]
        st = self.stack_of(gid)
        if st:
            st["groups"].remove(gid)
            st["active"] = max(0, min(st.get("active", 0), len(st["groups"]) - 1))
            if not st["groups"]:
                self._drop_stack(st)
            elif st["id"] in self.stack_wins:
                self.stack_wins[st["id"]]._refresh_size(); self.stack_wins[st["id"]].redraw()
        config.save(self.data)

    def rename_group(self, group: dict) -> None:
        t = config.get_theme(self.data)
        name = ask_string(self.root, "Rename", "New name:",
                          initial=group["name"], theme=t)
        if name and name.strip():
            group["name"] = name.strip()
            config.save(self.data)
            gw = self.group_widget(group["id"])
            if gw: gw.redraw()

    def clear_group(self, gid: int) -> None:
        group = next((g for g in self.data["groups"] if g["id"] == gid), None)
        if not group or not group["apps"]: return
        t = config.get_theme(self.data)
        if not ask_confirm(self.root,
            f"Remove all {len(group['apps'])} apps from '{group['name']}'?\n"
            "(Files will not be deleted.)", theme=t): return
        group["apps"] = []
        config.save(self.data)
        self._refresh_group(gid)


    # ── Quick launcher ─────────────────────────────────────

    def toggle_launcher(self) -> None:
        if self.launcher:
            self.launcher.close()
            return
        from desktop_widgets.ui.launcher import Launcher
        self.launcher = Launcher(self)

    def set_launcher_hotkey(self, label: str) -> bool:
        self.data["launcher_hotkey"] = label
        config.save(self.data)
        return self.hotkey.set(None if label == "Off" else label)

    def launch(self, path: str) -> None:
        """Start an app and remember it for Recent and ranking in the launcher."""
        from desktop_widgets.services.search import record_launch
        record_launch(self.data, path)
        config.save(self.data)
        launch_app(path)

    # ── Organize folders ───────────────────────────────────

    def open_organizer(self) -> None:
        from desktop_widgets.ui.organize_screen import OrganizeScreen
        OrganizeScreen(self)

    def apply_organize(self, plan: dict, chosen: set) -> int:
        """Carry out the ticked suggestions. The folders as they were are kept
        in data["organize_undo"] so the whole change can be undone."""
        import copy
        from desktop_widgets.services.organize import CATEGORIES
        self.data["organize_undo"] = {"groups": copy.deepcopy(self.data["groups"]),
                                      "stacks": copy.deepcopy(self.data.get("stacks", [])),
                                      "next_id": self.data["next_id"]}
        groups = {g["id"]: g for g in self.data["groups"]}
        touched, done = set(), 0

        def take(gid, path):
            g = groups.get(gid)
            if not g:
                return None
            app = next((a for a in g["apps"] if a["path"] == path), None)
            if app:
                g["apps"].remove(app)
                touched.add(gid)
            return app

        def put(gid, app):
            g = groups[gid]
            if all(os.path.normcase(a["path"]) != os.path.normcase(app["path"]) for a in g["apps"]):
                g["apps"].append(app)
            touched.add(gid)

        for kind in ("duplicates", "broken", "not_installed"):
            for item in plan.get(kind, []):
                if item["id"] in chosen and take(item["gid"], item["app"]["path"]):
                    done += 1
        for item in plan.get("names", []):
            if item["id"] in chosen:
                app = next((a for a in groups[item["gid"]]["apps"] if a["path"] == item["app"]["path"]), None)
                if app:
                    app["name"] = item["new"]; touched.add(item["gid"]); done += 1
        for item in plan.get("moves", []):
            if item["id"] in chosen and item["to"] in groups:
                app = take(item["gid"], item["app"]["path"])
                if app:
                    put(item["to"], app); done += 1
        new_groups = []
        for item in plan.get("new_folders", []):
            if item["id"] not in chosen:
                continue
            names = {g["name"].casefold() for g in self.data["groups"]}
            name, n = item["name"], 2
            while name.casefold() in names:
                name, n = f"{item['name']} {n}", n + 1
            first = groups.get(item["apps"][0]["gid"]) if item["apps"] else None
            src = self.group_widget(first["id"]) if first else None
            x, y = ((src.rect()[0] + src.rect()[2] + MARGIN, src.rect()[1]) if src else (60, 60))
            g = {"id": self.data["next_id"], "name": name, "apps": [], "x": x, "y": y,
                 "cols": 4, "collapsed": False, "theme_override": None}
            self.data["next_id"] += 1
            self.data["groups"].append(g)
            groups[g["id"]] = g
            for member in item["apps"]:
                app = take(member["gid"], member["app"]["path"])
                if app:
                    put(g["id"], app); done += 1
            sources = {self.stack_of(m["gid"])["id"] if self.stack_of(m["gid"]) else None
                       for m in item["apps"]}
            new_groups.append((g, sources.pop() if len(sources) == 1 else None))
        for item in plan.get("empty", []):
            if item["id"] in chosen and item["gid"] in groups and not groups[item["gid"]]["apps"]:
                self._remove_group(item["gid"]); done += 1
        config.save(self.data)
        for g, sid in new_groups:
            if sid is not None:
                self.add_to_stack(g["id"], sid)
            else:
                self._create_group(g)
        for gid in touched:
            if gid in groups and any(x["id"] == gid for x in self.data["groups"]):
                self._refresh_group(gid)
        return done

    def undo_organize(self) -> None:
        undo = self.data.pop("organize_undo", None)
        if not undo:
            return
        self.data["groups"] = undo["groups"]
        self.data["stacks"] = undo["stacks"]
        self.data["next_id"] = max(self.data["next_id"], undo["next_id"])
        config.save(self.data)
        self._rebuild_folders()

    def _remove_group(self, gid: int) -> None:
        """Delete a folder without asking (callers have confirmed)."""
        if gid in self.wins:
            self.wins.pop(gid).destroy()
        self.data["groups"] = [g for g in self.data["groups"] if g["id"] != gid]
        st = self.stack_of(gid)
        if st:
            st["groups"].remove(gid)
            st["active"] = max(0, min(st.get("active", 0), len(st["groups"]) - 1))
            if not st["groups"]:
                self._drop_stack(st)
            elif st["id"] in self.stack_wins:
                self.stack_wins[st["id"]]._refresh_size(); self.stack_wins[st["id"]].redraw()

    def _rebuild_folders(self) -> None:
        """Recreate every folder and stack widget from the data."""
        for w in list(self.wins.values()) + list(self.stack_wins.values()):
            w.destroy()
        self.wins.clear(); self.stack_wins.clear()
        stacked = self.stacked_ids()
        for g in self.data["groups"]:
            if g["id"] not in stacked:
                self._create_group(g)
        for st in self.data.get("stacks", []):
            self._create_stack(st)

    # ── Layouts ────────────────────────────────────────────

    def save_layout(self, name: str) -> None:
        from desktop_widgets.services import layouts
        layouts.save(self.data, name.strip())
        config.save(self.data)

    def save_layout_dialog(self) -> None:
        t = config.get_theme(self.data)
        n = len(self.data.get("layouts", [])) + 1
        name = ask_string(self.root, "Save layout", "Layout name",
                          initial=f"Layout {n}" if n > 1 else "Main", theme=t)
        if name and name.strip():
            from desktop_widgets.services import layouts
            if layouts.find(self.data, name.strip()) and not ask_confirm(
                    self.root, f"Replace the saved layout '{name.strip()}' with this one?", theme=t):
                return
            self.save_layout(name)

    def apply_layout(self, name: str) -> None:
        """Move every widget to the layout's spots and switch widgets on or off."""
        from desktop_widgets.services import layouts
        layout = layouts.find(self.data, name)
        if not layout:
            return
        layouts.apply_to_data(self.data, layout)
        self.data["active_layout"] = layout["name"]
        if self.data.get("theme_preset") == "Wallpaper":     # today's wallpaper, not the saved one
            from desktop_widgets.services import wallpaper
            live = wallpaper.theme()
            if live is not None:
                self.data["theme"] = live.to_dict()
        for key, widget, create in (("statsplus", self.statsplus_win, StatsPlusWidget),
                                    ("notes", self.notes_win, NotesWidget),
                                    ("media", self.media_win, MediaWidget)):
            enabled = self.data.get(key, {}).get("enabled")
            if enabled and not widget:
                setattr(self, f"{key}_win", create(self))
            elif not enabled and widget:
                widget.destroy()
                setattr(self, f"{key}_win", None)
        blocks = {}
        for gid, gw in self.wins.items():
            blocks[gw] = gw.group
        for sw in self.stack_wins.values():
            blocks[sw] = sw.stack
        for dw in self.docs_wins.values():
            blocks[dw] = dw._blk
        for key in ("statsplus", "notes", "media"):
            widget = getattr(self, f"{key}_win")
            if widget:
                blocks[widget] = self.data[key]
        for widget, blk in blocks.items():
            widget._collapsed = bool(blk.get("collapsed"))
            widget.restore_home()
        config.save(self.data)
        self.apply_theme()

    def delete_layout(self, name: str) -> None:
        self.data["layouts"] = [l for l in self.data.get("layouts", []) if l["name"] != name]
        if self.data.get("active_layout") == name:
            self.data["active_layout"] = None
        config.save(self.data)

    def rename_layout(self, name: str) -> None:
        from desktop_widgets.services import layouts
        layout = layouts.find(self.data, name)
        if not layout:
            return
        t = config.get_theme(self.data)
        new = ask_string(self.root, "Rename layout", "Layout name", initial=name, theme=t)
        if new and new.strip() and not layouts.find(self.data, new.strip()):
            layout["name"] = new.strip()
            if self.data.get("active_layout") == name:
                self.data["active_layout"] = layout["name"]
            config.save(self.data)

    def layouts_menu(self, x: int, y: int) -> None:
        m = self._menu()
        active = self.data.get("active_layout")
        for layout in self.data.get("layouts", []):
            mark = "\u2713  " if layout["name"] == active else "\U0001F5A5  "
            m.add_command(label=f"{mark}{layout['name']}",
                          command=lambda n=layout["name"]: self.apply_layout(n))
        if self.data.get("layouts"):
            m.add_separator()
        m.add_command(label="\u2795  Save current layout\u2026", command=self.save_layout_dialog)
        m.add_command(label="\u2699  Manage layouts", command=lambda: self.open_settings("widgets"))
        m.tk_popup(x, y)

    # ── Settings ───────────────────────────────────────────

    def open_settings(self, tab: str = "appearance", scroll_to: int | None = None) -> None:
        if self.settings_screen:
            try:
                self.settings_screen.win.lift()
                # If already open on a different tab, switch to requested one
                if tab != self.settings_screen._tab:
                    self.settings_screen._switch(tab)
            except: pass
            return
        import traceback
        try:
            self.settings_screen = SettingsScreen(self, initial_tab=tab, scroll_to=scroll_to)
        except Exception as e:
            print("SETTINGS ERROR:")
            traceback.print_exc()
            self.settings_screen = None

    # ── Live window recoloring ────────────────────────────

    def _recolor_window(self, win: tk.Toplevel, old_t, new_t) -> None:
        """Walk a tk widget tree and swap theme colours without rebuilding."""
        color_map: dict[str, str] = {}
        for k, ov in old_t.to_dict().items():
            if isinstance(ov, str) and ov.startswith("#"):
                nv = getattr(new_t, k, ov)
                if ov.lower() != nv.lower():
                    color_map[ov.lower()] = nv
        if not color_map:
            return

        def _walk(widget):
            for attr in ("bg", "fg", "highlightbackground", "activebackground"):
                try:
                    cur = widget.cget(attr)
                    rep = color_map.get(cur.lower() if cur else "")
                    if rep:
                        widget.configure(**{attr: rep})
                except Exception:
                    pass
            for child in widget.winfo_children():
                _walk(child)

        _walk(win)

    def apply_theme(self) -> None:
        """Redraw all widgets after a theme change."""
        for w in self.all_widgets():
            w.redraw()
        if self.tray_bar: self.tray_bar.redraw()
        # Push font to notes text widget live
        from desktop_widgets.theme import ui_font as _uf; ui_font = _uf(self.data)
        if self.notes_win and self.notes_win._text_widget:
            try: self.notes_win._text_widget.configure(font=(ui_font, 10))
            except Exception: pass

    # ── Stats+ ─────────────────────────────────────────────

    def toggle_statsplus(self) -> None:
        if self.statsplus_win:
            self.remove_statsplus()
        else:
            self.data.setdefault("statsplus", {})["enabled"] = True
            config.save(self.data)
            self.statsplus_win = StatsPlusWidget(self)

    def remove_statsplus(self) -> None:
        if self.statsplus_win:
            self.statsplus_win.destroy(); self.statsplus_win = None
        self.data.setdefault("statsplus", {})["enabled"] = False
        config.save(self.data)

    # ── Notes ──────────────────────────────────────────────

    def toggle_notes(self) -> None:
        if self.notes_win:
            self.remove_notes()
        else:
            self.data.setdefault("notes", {})["enabled"] = True
            config.save(self.data)
            self.notes_win = NotesWidget(self)

    def remove_notes(self) -> None:
        if self.notes_win:
            self.notes_win.destroy(); self.notes_win = None
        self.data.setdefault("notes", {})["enabled"] = False
        config.save(self.data)

    # ── Media widget ───────────────────────────────────────

    def toggle_media(self) -> None:
        if self.media_win:
            self.remove_media()
        else:
            self.data.setdefault("media", {})["enabled"] = True
            config.save(self.data)
            self.media_win = MediaWidget(self)

    def remove_media(self) -> None:
        if self.media_win:
            self.media_win.destroy(); self.media_win = None
        self.data.setdefault("media", {})["enabled"] = False
        config.save(self.data)

    # ── Docs widgets ───────────────────────────────────────

    def new_docs_dialog(self) -> None:
        t = config.get_theme(self.data)
        name = ask_string(self.root, "New files widget", "Name:", theme=t)
        if not name: return
        blk = {
            "id":             self.data["next_id"],
            "name":           name.strip(),
            "files":          [],
            "x":              60,
            "y":              500,
            "cols":           3,
            "collapsed":      False,
            "theme_override": None,
        }
        self.data.setdefault("docs_widgets", []).append(blk)
        self.data["next_id"] += 1
        config.save(self.data)
        dw = DocsWidget(self, blk)
        self.docs_wins[blk["id"]] = dw

    def delete_docs(self, did: int) -> None:
        blk = next((b for b in self.data.get("docs_widgets", []) if b["id"] == did), None)
        if not blk: return
        t = config.get_theme(self.data)
        if not ask_confirm(self.root, f"Delete files widget '{blk['name']}'?", theme=t):
            return
        if did in self.docs_wins:
            self.docs_wins[did].destroy(); del self.docs_wins[did]
        self.data["docs_widgets"] = [b for b in self.data.get("docs_widgets", [])
                                     if b["id"] != did]
        config.save(self.data)

    def rename_docs(self, blk: dict) -> None:
        t = config.get_theme(self.data)
        name = ask_string(self.root, "Rename", "New name:", initial=blk["name"], theme=t)
        if name and name.strip():
            blk["name"] = name.strip()
            config.save(self.data)
            dw = self.docs_wins.get(blk["id"])
            if dw: dw.redraw()

    # ── Add picker (+ button) ──────────────────────────────

    def show_add_picker(self) -> None:
        if self._add_picker and self._add_picker.winfo_exists():
            self._add_picker.lift()
            return
        from desktop_widgets.ui.add_widget_screen import AddWidgetScreen
        picker = AddWidgetScreen(self)
        self._add_picker = picker.win

    def lift_widgets(self) -> None:
        """Bring all widget windows to the front temporarily (e.g. for dialogs)."""
        for w in self.all_widgets():
            try: w.win.lift()
            except: pass

    def push_widgets(self) -> None:
        """Push all widgets back to desktop level."""
        for w in self.all_widgets():
            try: push_desktop(w.win.winfo_id())
            except: pass

    # ── Context menus ──────────────────────────────────────

    def _menu(self):
        t = config.get_theme(self.data)
        return ContextMenu(self.root, t)

    def group_ctx(self, e: tk.Event, group: dict) -> None:
        m = self._menu()
        m.add_command(label="✎  Rename",       command=lambda: self.rename_group(group))
        m.add_command(label="🗑  Clear all",   command=lambda: self.clear_group(group["id"]))
        m.add_separator()
        for st in self.data.get("stacks", []):
            m.add_command(label=f"📁  Add to stack '{st['name']}'",
                          command=lambda sid=st["id"]: self.add_to_stack(group["id"], sid))
        m.add_command(label="📁  Stack with other folders…",
                      command=lambda: self.new_stack_dialog(group["id"]))
        m.add_command(label="✨  Organize folders…", command=self.open_organizer)
        m.add_separator()
        m.add_command(label="✕  Delete widget", command=lambda: self.delete_group(group["id"]))
        m.add_separator()
        m.add_command(label="⚙  Settings",
                      command=lambda gid=group["id"]: self.open_settings("widgets", scroll_to=gid))
        m.add_command(label="⏻  Quit",         command=self._quit)
        m.tk_popup(e.x_root, e.y_root)

    def app_ctx(self, path: str, name: str, gid: int) -> None:
        m = self._menu()
        m.add_command(label=f"▶  Launch {name}", command=lambda: self.launch(path))
        m.add_separator()
        m.add_command(label="✎  Rename", command=lambda: self.rename_app(path, gid))
        m.add_command(label="◈  Change icon", command=lambda: self.change_app_icon(path, gid))
        m.add_command(label="✕  Remove", command=lambda: self.remove_app(path, gid))
        m.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def rename_app(self, path: str, gid: int) -> None:
        group = next((g for g in self.data["groups"] if g["id"] == gid), None)
        if not group: return
        app = next((a for a in group["apps"] if a["path"] == path), None)
        if not app: return
        t = config.get_theme(self.data)
        name = ask_string(self.root, "Rename", "New name:", initial=app["name"], theme=t)
        if name and name.strip():
            app["name"] = name.strip()
            config.save(self.data)
            gw = self.group_widget(gid)
            if gw: gw.redraw()

    def change_app_icon(self, path: str, gid: int) -> None:
        group = next((g for g in self.data['groups'] if g['id'] == gid), None)
        app = next((a for a in group['apps'] if a['path'] == path), None) if group else None
        if app is None:
            return
        image = filedialog.askopenfilename(parent=self.root, title='Choose an app icon',
                  filetypes=[('Icon or image', '*.ico *.png *.jpg *.jpeg *.webp *.exe'),
                             ('All files', '*.*')])
        if not image:
            return
        app['icon_path'] = image
        from desktop_widgets.utils import clear_icon_cache
        clear_icon_cache(path)
        config.save(self.data)
        gw = self.group_widget(gid)
        if gw:
            gw.redraw()

    # ── System tray ────────────────────────────────────────

    def _tray_loop(self) -> None:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([2, 2, 62, 62], radius=10, fill="#1c1f26")
        d.text((32, 32), "W", fill="white", anchor="mm")
        menu = pystray.Menu(
            pystray.MenuItem("Show",     self._tray_show, default=True),
            pystray.MenuItem("Settings", lambda: self.root.after(0, self.open_settings)),
            pystray.MenuItem("Quit",     self._tray_quit))
        self.tray = pystray.Icon("DW", img, "Desktop Widget", menu)
        self.tray.run()

    def _tray_show(self, *_) -> None:
        self.root.after(0, lambda: [w.win.deiconify() for w in self.all_widgets()])

    def _tray_quit(self, *_) -> None:
        if self.tray: self.tray.stop()
        self.root.after(0, self._quit)

    def _quit(self) -> None:
        try: self.hotkey.stop()
        except Exception: pass
        if self.tray:
            try: self.tray.stop()
            except: pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
