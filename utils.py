"""
utils.py — Shared utilities: snapping, icon extraction, app launching,
           custom dialogs, autostart (scheduled task).
No circular imports — only imports theme and config.
"""
from __future__ import annotations
import os, sys, subprocess, ctypes, ctypes.wintypes, math
import tkinter as tk
from tkinter import filedialog
from theme import Theme, CHROMA, SNAP, MARGIN

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import win32gui, win32ui, win32con
    WIN32_OK = True
except ImportError:
    WIN32_OK = False

# ── Desktop positioning ────────────────────────────────────
def push_desktop(hwnd: int) -> None:
    """Push a window to desktop level (behind icons)."""
    try:
        hwnd = ctypes.windll.user32.GetAncestor(hwnd, 2)
        ctypes.windll.user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x0003 | 0x0010)
    except Exception:
        pass


def allow_dnd_from_explorer(hwnd: int) -> None:
    """
    Allow drag-and-drop from Explorer even when running as Administrator.

    When elevated, COM's OLE DnD (used by tkinterdnd2) cannot receive drops
    from medium-integrity Explorer because the IDataObject cannot be marshalled
    across the integrity boundary — RegisterDragDrop silently fails to receive.

    The fix: install a Win32 window subclass that catches WM_DROPFILES directly.
    WM_DROPFILES uses a simpler kernel path that only needs the UIPI message
    filter whitelisted — no COM marshalling required. We fire a synthetic
    tkinterdnd2-compatible <<Drop>> event so the existing _on_drop handler
    works unchanged.

    Also applies ChangeWindowMessageFilter(Ex) so the message can reach us.
    Safe to call when not elevated — the subclass just adds a tiny no-cost hook.
    """
    u32     = ctypes.windll.user32
    shell32 = ctypes.windll.shell32

    # ── 1. Whitelist WM_DROPFILES through UIPI on every relevant HWND ──
    MSGFLT_ALLOW = 1
    msgs = (0x0233, 0x004A, 0x0049)   # WM_DROPFILES, WM_COPYDATA, WM_COPYGLOBALDATA

    hwnds: set[int] = set()
    def _add(h):
        if h: hwnds.add(h)
    _add(hwnd)
    try: _add(u32.GetAncestor(hwnd, 2))
    except Exception: pass
    try: _add(u32.GetParent(hwnd))
    except Exception: pass
    try:
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool,
                                          ctypes.wintypes.HWND,
                                          ctypes.wintypes.LPARAM)
        def _cb(child, _): _add(child); return True
        u32.EnumChildWindows(hwnd, WNDENUMPROC(_cb), 0)
    except Exception: pass

    try:
        CWMFEx = u32.ChangeWindowMessageFilterEx
        CWMFEx.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint,
                           ctypes.c_uint, ctypes.c_void_p]
        CWMFEx.restype = ctypes.wintypes.BOOL
        for h in hwnds:
            for msg in msgs: CWMFEx(h, msg, MSGFLT_ALLOW, None)
    except Exception: pass

    try:                                        # process-wide fallback (XP)
        CWMF = u32.ChangeWindowMessageFilter
        CWMF.argtypes = [ctypes.c_uint, ctypes.c_uint]
        CWMF.restype  = ctypes.wintypes.BOOL
        for msg in msgs: CWMF(msg, MSGFLT_ALLOW)
    except Exception: pass

    for h in hwnds:
        try: shell32.DragAcceptFiles(h, True)
        except Exception: pass

    # ── 2. Subclass the HWND to catch WM_DROPFILES natively ────────────
    # This bypasses OLE entirely and works at any integrity level.
    WM_DROPFILES = 0x0233
    GWLP_WNDPROC = -4

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long,
                                  ctypes.wintypes.HWND,
                                  ctypes.c_uint,
                                  ctypes.wintypes.WPARAM,
                                  ctypes.wintypes.LPARAM)

    # Keep a reference so the callback isn't garbage-collected
    if not hasattr(allow_dnd_from_explorer, "_subclasses"):
        allow_dnd_from_explorer._subclasses = {}

    if hwnd in allow_dnd_from_explorer._subclasses:
        return   # already subclassed

    try:
        import tkinter as _tk

        # We need the tkinter widget object so we can generate a virtual event.
        # Walk the global widget table using the HWND.
        def _find_widget(target_hwnd):
            try:
                # tk's internal nametowidget / winfo by id
                import tkinter as tk_
                # Iterate through all known Toplevel windows in the process
                for obj in list(allow_dnd_from_explorer._subclasses.values()):
                    pass  # populated below
            except Exception:
                pass
            return None

        # Store (old_proc, hwnd) so we can look up by hwnd later
        old_proc_ptr = u32.GetWindowLongPtrW(hwnd, GWLP_WNDPROC)

        @WNDPROC
        def _new_wndproc(h, msg, wp, lp):
            if msg == WM_DROPFILES:
                try:
                    hDrop = ctypes.wintypes.HANDLE(wp)
                    # Query number of files
                    DragQueryFileW = shell32.DragQueryFileW
                    DragQueryFileW.restype = ctypes.c_uint
                    n = DragQueryFileW(hDrop, 0xFFFFFFFF, None, 0)
                    paths = []
                    for i in range(n):
                        buf_len = DragQueryFileW(hDrop, i, None, 0) + 1
                        buf = ctypes.create_unicode_buffer(buf_len)
                        DragQueryFileW(hDrop, i, buf, buf_len)
                        paths.append(buf.value)
                    shell32.DragFinish(hDrop)
                    if paths:
                        # Fire a synthetic <<WmDrop>> event on the root so
                        # group_widget._on_wmdrop can pick it up
                        path_str = "{" + " ".join(
                            "{" + p.replace("\\", "/") + "}" for p in paths
                        ) + "}"
                        allow_dnd_from_explorer._pending_drops[hwnd] = paths
                        # Use after(0) via stored root ref to stay thread-safe
                        root = allow_dnd_from_explorer._roots.get(hwnd)
                        if root:
                            root.after(0, lambda ps=paths, h2=hwnd:
                                       _dispatch_drop(h2, ps))
                except Exception:
                    pass
                return 0
            # Call original wndproc
            return u32.CallWindowProcW(old_proc_ptr, h, msg, wp, lp)

        u32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC,
                              ctypes.cast(_new_wndproc, ctypes.c_void_p).value)
        allow_dnd_from_explorer._subclasses[hwnd] = _new_wndproc   # prevent GC

    except Exception:
        pass


def _dispatch_drop(hwnd: int, paths: list) -> None:
    """Called on the main thread to fire the drop callback registered via setup_wmdrop."""
    cb = allow_dnd_from_explorer._drop_callbacks.get(hwnd)
    if cb:
        cb(paths)


def setup_wmdrop(hwnd: int, root, callback) -> None:
    """
    Register a callback(paths: list[str]) that fires when files are dropped
    onto the window identified by hwnd via WM_DROPFILES.
    Must be called AFTER allow_dnd_from_explorer(hwnd).
    """
    if not hasattr(allow_dnd_from_explorer, "_drop_callbacks"):
        allow_dnd_from_explorer._drop_callbacks = {}
    if not hasattr(allow_dnd_from_explorer, "_roots"):
        allow_dnd_from_explorer._roots = {}
    if not hasattr(allow_dnd_from_explorer, "_pending_drops"):
        allow_dnd_from_explorer._pending_drops = {}
    allow_dnd_from_explorer._drop_callbacks[hwnd] = callback
    allow_dnd_from_explorer._roots[hwnd] = root


def create_desktop_shortcut(target_path: str, name: str) -> bool:
    """
    Create a .lnk shortcut on the user's Desktop pointing to target_path.
    Returns True on success. Uses win32com if available, falls back to
    a PowerShell one-liner so it works without pywin32 too.
    """
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    # Also try the shell-known Desktop path (handles OneDrive redirections)
    try:
        import ctypes.wintypes as wt
        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY = 0x0010
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
        if buf.value:
            desktop = buf.value
    except Exception:
        pass

    safe_name = "".join(c for c in name if c not in r'\/:*?"<>|').strip() or "shortcut"
    lnk_path = os.path.join(desktop, safe_name + ".lnk")

    # Try win32com first (cleanest)
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        lnk = shell.CreateShortcut(lnk_path)
        lnk.TargetPath = target_path
        lnk.WorkingDirectory = os.path.dirname(target_path)
        lnk.save()
        return True
    except Exception:
        pass

    # Fallback: PowerShell
    try:
        ps = (
            f'$ws=New-Object -ComObject WScript.Shell;'
            f'$s=$ws.CreateShortcut("{lnk_path}");'
            f'$s.TargetPath="{target_path}";'
            f'$s.WorkingDirectory="{os.path.dirname(target_path)}";'
            f'$s.Save()'
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, timeout=8, creationflags=0x08000000,
        )
        return r.returncode == 0
    except Exception:
        return False

# ── Snapping ───────────────────────────────────────────────
def snap_to_grid(v: int) -> int:
    return round(v / SNAP) * SNAP

def clamp_to_screen(x: int, y: int, w: int, h: int,
                    sw: int, sh: int) -> tuple[int, int]:
    """Keep widget fully within screen with MARGIN gap."""
    x = max(MARGIN, min(x, sw - w - MARGIN))
    y = max(MARGIN, min(y, sh - h - MARGIN))
    return x, y

def magnetic_snap(x: int, y: int, w: int, h: int,
                  others: list[tuple[int,int,int,int]],
                  threshold: int = 16) -> tuple[int, int]:
    """
    Snap x,y to edges and centres of other widgets.

    Priority (closest match wins per axis):
      1. Adjacent placement  — butt up against another widget's edge
      2. Edge alignment      — share a left/right/top/bottom edge
      3. Centre alignment    — centres line up
      4. Grid snap           — fall back to nearest grid point
    """
    sx = snap_to_grid(x)
    sy = snap_to_grid(y)

    best_dx = threshold + 1
    best_dy = threshold + 1

    for ox, oy, ow, oh in others:
        h_snaps = [
            (ox - w - MARGIN,   abs(x - (ox - w - MARGIN))),
            (ox + ow + MARGIN,  abs(x - (ox + ow + MARGIN))),
            (ox,                abs(x - ox)),
            (ox + ow - w,       abs(x - (ox + ow - w))),
            (ox + ow//2 - w//2, abs(x - (ox + ow//2 - w//2))),
        ]
        for snap_x, dist in h_snaps:
            if dist < best_dx:
                best_dx = dist; sx = snap_x

        v_snaps = [
            (oy - h - MARGIN,   abs(y - (oy - h - MARGIN))),
            (oy + oh + MARGIN,  abs(y - (oy + oh + MARGIN))),
            (oy,                abs(y - oy)),
            (oy + oh - h,       abs(y - (oy + oh - h))),
            (oy + oh//2 - h//2, abs(y - (oy + oh//2 - h//2))),
        ]
        for snap_y, dist in v_snaps:
            if dist < best_dy:
                best_dy = dist; sy = snap_y

    return sx, sy

def find_non_overlapping(x: int, y: int, w: int, h: int,
                         others: list[tuple[int,int,int,int]],
                         sw: int, sh: int) -> tuple[int, int]:
    """
    After a drag-drop, keep the dragged widget where the user placed it
    and push any overlapping widgets downward instead. Widgets are clamped
    so nothing goes off the bottom of the screen — if there's not enough
    room, compress gaps to minimum MARGIN spacing.
    """
    x, y = clamp_to_screen(x, y, w, h, sw, sh)
    return x, y


def reflow_push_down(dropped_x, dropped_y, dropped_w, dropped_h,
                     all_widgets, sw, sh):
    """
    After a widget is dropped, push all overlapping widgets away.
    Cascades in the same direction — so pushing widget B down will also
    push widget C down if B lands on C. No direction changes mid-cascade.
    Returns a dict of {widget: (new_x, new_y)}.
    """
    MARGIN = 10

    # Start with current positions
    positions = {}
    for widget in all_widgets:
        rx, ry, rw, rh = widget.rect()
        positions[widget] = [rx, ry, rw, rh]

    def _overlaps(ax, ay, aw, ah, bx, by, bw, bh):
        return (ax < bx + bw + MARGIN and ax + aw + MARGIN > bx and
                ay < by + bh + MARGIN and ay + ah + MARGIN > by)

    def _push_dir(ax, ay, aw, ah, bx, by, bw, bh):
        """Return ('h'|'v', sign) direction to push b away from a."""
        acx = ax + aw // 2; acy = ay + ah // 2
        bcx = bx + bw // 2; bcy = by + bh // 2
        dx = bcx - acx;     dy  = bcy - acy
        ndx = dx / max(aw, bw, 1)
        ndy = dy / max(ah, bh, 1)
        if abs(ndx) >= abs(ndy):
            return 'h', (1 if dx >= 0 else -1)
        else:
            return 'v', (1 if dy >= 0 else -1)

    # Phase 1 — push all direct overlaps with the dropped widget,
    #           record the direction each widget was pushed
    push_dirs = {}   # widget -> ('h'|'v', sign)
    for widget, pos in positions.items():
        bx, by, bw, bh = pos
        if _overlaps(dropped_x, dropped_y, dropped_w, dropped_h, bx, by, bw, bh):
            axis, sign = _push_dir(dropped_x, dropped_y, dropped_w, dropped_h,
                                   bx, by, bw, bh)
            if axis == 'h':
                pos[0] = (dropped_x + dropped_w + MARGIN) if sign > 0 \
                         else (dropped_x - bw - MARGIN)
            else:
                pos[1] = (dropped_y + dropped_h + MARGIN) if sign > 0 \
                         else (dropped_y - bh - MARGIN)
            push_dirs[widget] = (axis, sign)

    # Phase 2 — cascade: if a pushed widget now overlaps another,
    #           push that other in the SAME direction
    changed = True
    while changed:
        changed = False
        for widget, (axis, sign) in list(push_dirs.items()):
            ax, ay, aw, ah = positions[widget]
            for other, opos in positions.items():
                if other is widget: continue
                bx, by, bw, bh = opos
                if not _overlaps(ax, ay, aw, ah, bx, by, bw, bh):
                    continue
                # Push other in same direction as widget was pushed
                if axis == 'h':
                    new_bx = (ax + aw + MARGIN) if sign > 0 else (ax - bw - MARGIN)
                    if new_bx != bx:
                        opos[0] = new_bx
                        push_dirs[other] = (axis, sign)
                        changed = True
                else:
                    new_by = (ay + ah + MARGIN) if sign > 0 else (ay - bh - MARGIN)
                    if new_by != by:
                        opos[1] = new_by
                        push_dirs[other] = (axis, sign)
                        changed = True

    # Clamp everything to screen
    for widget, pos in positions.items():
        bx, by, bw, bh = pos
        pos[0] = max(MARGIN, min(bx, sw - bw - MARGIN))
        pos[1] = max(MARGIN, min(by, sh - bh - MARGIN))

    return {w: (p[0], p[1]) for w, p in positions.items()}

# ── String util ────────────────────────────────────────────
def clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"

# ── Icon extraction ────────────────────────────────────────
_CACHE: dict[tuple, object] = {}

def get_icon(path: str, size: int) -> object | None:
    from config import URL_APPS
    key = (path, size)
    if key not in _CACHE:
        _CACHE[key] = _extract(path, size)
    return _CACHE[key]

def clear_icon_cache(path: str) -> None:
    for k in list(_CACHE):
        if k[0] == path:
            del _CACHE[k]

def _extract(path: str, size: int):
    from config import URL_APPS
    if not PIL_OK:
        return None
    if path in URL_APPS:
        ico = URL_APPS[path].get("icon_path")
        if ico and os.path.exists(ico):
            r = _load_ico(ico, size)
            if r: return r
        return _letter_tile(path, size)
    if WIN32_OK:
        r = _private_icon(path, size)
        if r: return r
        r = _extracticonex(path, size)
        if r: return r
    return _letter_tile(path, size)

def _hicon_to_pil(hicon, draw_size: int, out_size: int):
    try:
        sdc = win32gui.GetDC(0)
        hdc = win32ui.CreateDCFromHandle(sdc)
        mem = hdc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(hdc, draw_size, draw_size)
        mem.SelectObject(bmp)
        mem.FillSolidRect((0, 0, draw_size, draw_size), 0xFFFFFF)
        win32gui.DrawIconEx(mem.GetSafeHdc(), 0, 0, hicon,
                            draw_size, draw_size, 0, None, win32con.DI_NORMAL)
        info = bmp.GetInfo(); data = bmp.GetBitmapBits(True)
        mem.DeleteDC(); win32gui.DeleteObject(bmp.GetHandle())
        win32gui.ReleaseDC(0, sdc)
        img = Image.frombuffer("RGBA", (info["bmWidth"], info["bmHeight"]),
                               data, "raw", "BGRA", 0, 1)
        if out_size != draw_size:
            img = img.resize((out_size, out_size), Image.LANCZOS)
        lo, hi = img.convert("L").getextrema()
        return img if hi - lo >= 8 else None
    except:
        return None

def _private_icon(path: str, size: int):
    try:
        u32 = ctypes.windll.user32
        hi = (ctypes.wintypes.HICON * 1)()
        ids = (ctypes.c_uint * 1)()
        n = u32.PrivateExtractIconsW(path, 0, 256, 256, hi, ids, 1, 0)
        if n < 1 or not hi[0]: return None
        img = _hicon_to_pil(hi[0], 256, size)
        u32.DestroyIcon(hi[0])
        return ImageTk.PhotoImage(img) if img else None
    except:
        return None

def _extracticonex(path: str, size: int):
    try:
        large, small = win32gui.ExtractIconEx(path, 0)
        handles = large if large else small
        if not handles: return None
        img = _hicon_to_pil(handles[0], 64, size)
        for h in (large + small):
            try: win32gui.DestroyIcon(h)
            except: pass
        return ImageTk.PhotoImage(img) if img else None
    except:
        return None

def _load_ico(ico_path: str, size: int):
    try:
        img = Image.open(ico_path)
        best = None
        try:
            for i in range(getattr(img, "n_frames", 1)):
                img.seek(i); f = img.copy().convert("RGBA")
                if best is None or f.size[0] > best.size[0]: best = f
        except EOFError:
            pass
        if best is None: best = img.convert("RGBA")
        r = best.resize((size, size), Image.LANCZOS)
        lo, hi = r.convert("L").getextrema()
        return ImageTk.PhotoImage(r) if hi - lo >= 8 else None
    except:
        return None

def _letter_tile(path: str, size: int):
    if not PIL_OK: return None
    name = os.path.splitext(os.path.basename(path))[0]
    palette = ["#5b7cf8","#e05c6c","#3dbf7f","#d4a017","#9b59b6","#e67e22","#16a085"]
    color = palette[sum(ord(c) for c in name) % len(palette)]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size-1, size-1], radius=max(6, size // 5), fill=color)
    d.text((size//2, size//2), name[0].upper() if name else "?",
           fill="white", anchor="mm")
    return ImageTk.PhotoImage(img)

# ── App launching ──────────────────────────────────────────
def launch_app(path: str) -> None:
    from config import URL_APPS
    if path in URL_APPS:
        try: os.startfile(URL_APPS[path]["launch"])
        except Exception as e:
            tk.messagebox.showerror("Error", str(e))
        return
    if not os.path.exists(path):
        tk.messagebox.showerror("Not found", f"File not found:\n{path}"); return
    try:
        subprocess.Popen([path], cwd=os.path.dirname(path))
    except Exception as e:
        tk.messagebox.showerror("Error", str(e))

# ── Shortcut / URL resolution ──────────────────────────────
def resolve_lnk(lnk_path: str) -> str | None:
    try:
        import win32com.client
        lnk = win32com.client.Dispatch("WScript.Shell").CreateShortCut(lnk_path)
        t = lnk.TargetPath; args = lnk.Arguments or ""
        if t and os.path.exists(t):
            real = _resolve_updater(t, args)
            return real or t
    except: pass
    try:
        ps = (f'$sh=New-Object -ComObject WScript.Shell;'
              f'$lnk=$sh.CreateShortcut("{lnk_path}");Write-Output $lnk.TargetPath')
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=8,
                           creationflags=0x08000000)
        t = r.stdout.strip()
        if t and os.path.exists(t):
            real = _resolve_updater(t)
            return real or t
    except: pass
    return None

def resolve_url(url_path: str) -> str | None:
    from config import URL_APPS
    try:
        with open(url_path, encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        url = ""; ico = ""
        for line in raw.splitlines():
            u = line.strip().upper()
            if u.startswith("URL="): url = line.strip()[4:]
            elif u.startswith("ICONFILE="): ico = line.strip()[9:].strip('"')
        if "," in ico: ico = ico.rsplit(",", 1)[0].strip()
        if ico.lower().endswith(".exe") and os.path.exists(ico): return ico
        if url and "://" in url and not url.lower().startswith("http"):
            URL_APPS[url_path] = {"launch": url,
                                  "icon_path": ico if os.path.exists(ico) else None}
            return url_path
    except Exception as e:
        print(f"[utils] resolve_url: {e}")
    return None

def _resolve_updater(exe_path: str, args: str = "") -> str | None:
    if os.path.basename(exe_path).lower() not in ("update.exe", "squirrel.exe"):
        return None
    import re
    folder = os.path.dirname(exe_path)
    m = re.search(r'--processStart\s+(\S+\.exe)', args, re.I)
    if m:
        app_exe = m.group(1).strip('"\'')
        for entry in sorted(os.listdir(folder), reverse=True):
            c = os.path.join(folder, entry, app_exe)
            if os.path.exists(c): return c
    for entry in sorted(os.listdir(folder), reverse=True):
        sub = os.path.join(folder, entry)
        if os.path.isdir(sub) and entry.startswith("app-"):
            for f in sorted(os.listdir(sub)):
                if f.lower().endswith(".exe") and "update" not in f.lower():
                    return os.path.join(sub, f)
    return None

# ── Autostart (Windows Task Scheduler) ────────────────────
def task_exists() -> bool:
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", "DesktopWidget"],
                           capture_output=True, text=True, creationflags=0x08000000)
        return r.returncode == 0
    except: return False

def create_task(exe_path: str) -> bool:
    try:
        username = os.environ.get("USERNAME", "User")
        xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><Enabled>true</Enabled><UserId>{username}</UserId><Delay>PT3S</Delay></LogonTrigger></Triggers>
  <Principals><Principal><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><ExecutionTimeLimit>PT0S</ExecutionTimeLimit><Priority>7</Priority></Settings>
  <Actions><Exec><Command>{exe_path}</Command></Exec></Actions>
</Task>"""
        xp = os.path.join(os.environ.get("TEMP", ""), "dw_task.xml")
        with open(xp, "w", encoding="utf-16") as f: f.write(xml)
        r = subprocess.run(["schtasks", "/Create", "/TN", "DesktopWidget", "/XML", xp, "/F"],
                           capture_output=True, text=True, creationflags=0x08000000)
        try: os.remove(xp)
        except: pass
        return r.returncode == 0
    except: return False

def remove_task() -> bool:
    try:
        r = subprocess.run(["schtasks", "/Delete", "/TN", "DesktopWidget", "/F"],
                           capture_output=True, text=True, creationflags=0x08000000)
        return r.returncode == 0
    except: return False

# ── Styled dialogs ─────────────────────────────────────────
def ask_string(parent: tk.Misc, title: str, prompt: str,
               initial: str = "", theme: Theme | None = None) -> str | None:
    from theme import Theme
    t = theme or Theme()
    result = [None]
    dlg = tk.Toplevel(parent)
    dlg.title(""); dlg.overrideredirect(True)
    dlg.attributes("-topmost", True); dlg.configure(bg=t.bg)
    dw, dh = 340, 145
    sw = parent.winfo_screenwidth(); sh = parent.winfo_screenheight()
    dlg.geometry(f"{dw}x{dh}+{(sw-dw)//2}+{(sh-dh)//2}")

    tk.Label(dlg, text=title, font=("Segoe UI", 10, "bold"),
             bg=t.hdr, fg=t.txt, pady=8).pack(fill="x")
    tk.Frame(dlg, bg=t.border, height=1).pack(fill="x")
    tk.Label(dlg, text=prompt, font=("Segoe UI", 9),
             bg=t.bg, fg=t.txt2, anchor="w").pack(fill="x", padx=12, pady=(8, 2))

    var = tk.StringVar(value=initial)
    entry = tk.Entry(dlg, textvariable=var, font=("Segoe UI", 10),
                     bg="#0e1118", fg=t.txt, insertbackground=t.txt,
                     relief="flat", bd=0, highlightthickness=1,
                     highlightcolor=t.accent, highlightbackground=t.border)
    entry.pack(fill="x", padx=12, pady=4)
    entry.select_range(0, "end"); entry.focus_set()

    bf = tk.Frame(dlg, bg=t.bg); bf.pack(fill="x", padx=12, pady=8)
    def ok(e=None): result[0] = var.get().strip() or None; dlg.destroy()
    def cancel(e=None): dlg.destroy()
    tk.Button(bf, text="Cancel", font=("Segoe UI", 9), bg=t.btn, fg=t.txt2,
              relief="flat", bd=0, cursor="hand2", command=cancel).pack(side="left")
    tk.Button(bf, text="OK", font=("Segoe UI", 9, "bold"), bg=t.accent, fg="white",
              relief="flat", bd=0, cursor="hand2", command=ok).pack(side="right")
    entry.bind("<Return>", ok); entry.bind("<Escape>", cancel)
    dlg.grab_set(); parent.wait_window(dlg)
    return result[0]

def ask_confirm(parent: tk.Misc, message: str, theme: Theme | None = None) -> bool:
    from theme import Theme
    t = theme or Theme()
    result = [False]
    dlg = tk.Toplevel(parent)
    dlg.title(""); dlg.overrideredirect(True)
    dlg.attributes("-topmost", True); dlg.configure(bg=t.bg)
    dw, dh = 360, 155
    sw = parent.winfo_screenwidth(); sh = parent.winfo_screenheight()
    dlg.geometry(f"{dw}x{dh}+{(sw-dw)//2}+{(sh-dh)//2}")

    tk.Label(dlg, text="Confirm", font=("Segoe UI", 10, "bold"),
             bg=t.hdr, fg=t.txt, pady=8).pack(fill="x")
    tk.Frame(dlg, bg=t.border, height=1).pack(fill="x")
    tk.Label(dlg, text=message, font=("Segoe UI", 9),
             bg=t.bg, fg=t.txt2, justify="center", wraplength=320).pack(pady=14)
    bf = tk.Frame(dlg, bg=t.bg); bf.pack(fill="x", padx=12, pady=8)
    def yes(): result[0] = True; dlg.destroy()
    def no(): dlg.destroy()
    tk.Button(bf, text="Cancel", font=("Segoe UI", 9), bg=t.btn, fg=t.txt2,
              relief="flat", bd=0, cursor="hand2", command=no).pack(side="left")
    tk.Button(bf, text="Confirm", font=("Segoe UI", 9, "bold"), bg="#8b2020", fg="white",
              relief="flat", bd=0, cursor="hand2", command=yes).pack(side="right")
    dlg.bind("<Escape>", lambda e: no())
    dlg.grab_set(); parent.wait_window(dlg)
    return result[0]