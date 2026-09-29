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
from desktop_widgets.widgets.statsplus_widget import StatsPlusWidget
from desktop_widgets.widgets.notes_widget import NotesWidget
from desktop_widgets.widgets.docs_widget import DocsWidget
from desktop_widgets.widgets.media_widget import MediaWidget
from desktop_widgets.ui.context_menu import ContextMenu
from desktop_widgets.ui.focus_overlay import FocusOverlay
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
        self.wins:         dict[int, GroupWidget]  = {}
        self.focus:        FocusOverlay | None     = None
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

        # Build widgets
        for g in self.data["groups"]:
            self._create_group(g)

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
        from desktop_widgets.services.screens import work_areas
        self._screen_areas = work_areas(self.root)
        self.root.after(2000, self._check_screens)

    def _check_screens(self):
        """Recover widgets after a display is removed or its work area changes."""
        from desktop_widgets.services.screens import work_areas, area_for, clamp
        areas = work_areas(self.root)
        widgets = (list(self.wins.values()) + list(self.docs_wins.values()) +
                   [w for w in (self.statsplus_win, self.notes_win, self.media_win) if w])
        if areas != self._screen_areas and not any(w._mode for w in widgets):
            self._screen_areas = areas
            if self.tray_bar:
                self.tray_bar.reposition()
            for widget in widgets:
                old_rect = widget.rect()
                widget.redraw()
                if widget.rect() != old_rect:
                    widget._save_geometry()
        self.root.after(2000, self._check_screens)

    # ── Widget creation ────────────────────────────────────

    def _create_group(self, g: dict) -> GroupWidget:
        gw = GroupWidget(self, g)
        gw.bind_events()
        self.wins[g["id"]] = gw
        return gw

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
        rects = []
        for gw in self.wins.values():
            if gw is exclude: continue
            rects.append(gw.rect())
        for w in [self.statsplus_win, self.notes_win, self.media_win]:
            if w and w is not exclude:
                rects.append(w.rect())
        for dw in self.docs_wins.values():
            if dw is not exclude:
                rects.append(dw.rect())
        return rects

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

        all_widgets = (
            list(self.wins.values()) +
            [w for w in [self.statsplus_win, self.notes_win, self.media_win] if w] +
            list(self.docs_wins.values())
        )

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

        all_widgets = (
            list(self.wins.values()) +
            [w for w in [self.statsplus_win, self.notes_win, self.media_win] if w] +
            list(self.docs_wins.values())
        )

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
        AppPicker(self, lambda entries: self.add_app_entries(gid, entries))

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
                existing.add(key)
        config.save(self.data)
        gw = self.wins.get(gid)
        if gw:
            gw._refresh_size()
            gw.redraw()

    def remove_app(self, path: str, gid: int) -> None:
        t = config.get_theme(self.data)
        if not ask_confirm(self.root, "Remove app?\n(File will not be deleted.)", theme=t):
            return
        group = next((g for g in self.data["groups"] if g["id"] == gid), None)
        if group:
            group["apps"] = [a for a in group["apps"] if a["path"] != path]
        config.save(self.data)
        gw = self.wins.get(gid)
        if gw: gw._refresh_size(); gw.redraw()

    # ── Cross-widget drag helpers ──────────────────────────

    def find_group_widget_at(self, x_root: int, y_root: int,
                              exclude_gid: int | None = None
                              ) -> "GroupWidget | None":
        """Return the GroupWidget whose window contains the screen point (x_root, y_root)."""
        for gid, gw in self.wins.items():
            if gid == exclude_gid:
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
        src_gw = self.wins.get(src_gid)
        if src_gw:
            src_gw._refresh_size(); src_gw.redraw()
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
        src_gw = self.wins.get(src_gid)
        if src_gw:
            src_gw._refresh_size(); src_gw.redraw()

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
        config.save(self.data)

    def rename_group(self, group: dict) -> None:
        t = config.get_theme(self.data)
        name = ask_string(self.root, "Rename", "New name:",
                          initial=group["name"], theme=t)
        if name and name.strip():
            group["name"] = name.strip()
            config.save(self.data)
            gw = self.wins.get(group["id"])
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
        gw = self.wins.get(gid)
        if gw: gw._refresh_size(); gw.redraw()


    # ── Focus overlay ──────────────────────────────────────

    def open_focus(self, group: dict) -> None:
        if self.focus: self.focus.close()
        self.focus = FocusOverlay(self, group)

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
        for gw in self.wins.values():
            gw.redraw()
        for w in [self.statsplus_win, self.notes_win, self.media_win]:
            if w: w.redraw()
        for dw in self.docs_wins.values():
            dw.redraw()
        if self.tray_bar: self.tray_bar.redraw()
        # Push font to notes text widget live
        ui_font = self.data.get("ui_font", "Segoe UI")
        if self.notes_win and self.notes_win._text_widget:
            try: self.notes_win._text_widget.configure(font=(ui_font, 10))
            except Exception: pass
        # Keep focus overlay in sync
        if self.focus:
            try: self.focus._apply_theme()
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
        for gw in self.wins.values():
            try: gw.win.lift()
            except: pass
        for dw in self.docs_wins.values():
            try: dw.win.lift()
            except: pass
        for w in [self.statsplus_win, self.notes_win, self.media_win]:
            if w:
                try: w.win.lift()
                except: pass

    def push_widgets(self) -> None:
        """Push all widgets back to desktop level."""
        for gw in self.wins.values():
            try: push_desktop(gw.win.winfo_id())
            except: pass
        for dw in self.docs_wins.values():
            try: push_desktop(dw.win.winfo_id())
            except: pass
        for w in [self.statsplus_win, self.notes_win, self.media_win]:
            if w:
                try: push_desktop(w.win.winfo_id())
                except: pass

    # ── Context menus ──────────────────────────────────────

    def _menu(self):
        t = config.get_theme(self.data)
        return ContextMenu(self.root, t)

    def group_ctx(self, e: tk.Event, group: dict) -> None:
        m = self._menu()
        m.add_command(label="⤢  Open focus", command=lambda: self.open_focus(group))
        m.add_separator()
        m.add_command(label="✎  Rename",       command=lambda: self.rename_group(group))
        m.add_command(label="🗑  Clear all",   command=lambda: self.clear_group(group["id"]))
        m.add_separator()
        m.add_command(label="✕  Delete widget", command=lambda: self.delete_group(group["id"]))
        m.add_separator()
        m.add_command(label="⚙  Settings",
                      command=lambda gid=group["id"]: self.open_settings("widgets", scroll_to=gid))
        m.add_command(label="⏻  Quit",         command=self._quit)
        m.tk_popup(e.x_root, e.y_root)

    def app_ctx(self, path: str, name: str, gid: int) -> None:
        m = self._menu()
        m.add_command(label=f"▶  Launch {name}", command=lambda: launch_app(path))
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
            gw = self.wins.get(gid)
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
        if gid in self.wins:
            self.wins[gid].redraw()

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
        self.root.after(0, lambda: [gw.win.deiconify() for gw in self.wins.values()])

    def _tray_quit(self, *_) -> None:
        if self.tray: self.tray.stop()
        self.root.after(0, self._quit)

    def _quit(self) -> None:
        if self.tray:
            try: self.tray.stop()
            except: pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
