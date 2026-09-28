"""Monitor work areas in Windows virtual-desktop coordinates."""
from __future__ import annotations

import time

_cached = ()
_expires = 0.0


def work_areas(root):
    global _cached, _expires
    now = time.monotonic()
    if now >= _expires:
        try:
            import win32api
            try:
                taskbars = _taskbar_bounds()
            except (ImportError, OSError, AttributeError):
                taskbars = []
            areas = []
            for handle, _, _ in win32api.EnumDisplayMonitors():
                info = win32api.GetMonitorInfo(handle)
                area = tuple(info['Work'])
                for monitor, edge, thickness in taskbars:
                    if tuple(info['Monitor']) == monitor:
                        area = reserve_taskbar(area, monitor, edge, thickness)
                areas.append(area)
            _cached = tuple(areas)
        except (ImportError, OSError):
            _cached = ()
        _expires = now + 0.5
    return _cached or ((0, 0, root.winfo_screenwidth(), root.winfo_screenheight()),)


def reserve_taskbar(area, monitor, edge, thickness):
    """Reserve the shown size even when an auto-hidden taskbar is offscreen."""
    left, top, right, bottom = area
    ml, mt, mr, mb = monitor
    if edge == 0: left = max(left, ml + thickness)
    elif edge == 1: top = max(top, mt + thickness)
    elif edge == 2: right = min(right, mr - thickness)
    elif edge == 3: bottom = min(bottom, mb - thickness)
    return left, top, right, bottom


def _taskbar_bounds():
    # ABM_GETTASKBARPOS returns the shown primary taskbar rectangle, including
    # auto-hide. Secondary taskbar windows retain their full size while hidden.
    # https://learn.microsoft.com/windows/win32/api/shellapi/ns-shellapi-appbardata
    import ctypes
    from ctypes import wintypes as wt
    import win32api
    import win32gui

    class AppBarData(ctypes.Structure):
        _fields_ = [('cbSize', wt.DWORD), ('hWnd', wt.HWND),
                    ('uCallbackMessage', wt.UINT), ('uEdge', wt.UINT),
                    ('rc', wt.RECT), ('lParam', wt.LPARAM)]

    result = []
    def visit(hwnd, _):
        name = win32gui.GetClassName(hwnd)
        if name not in ('Shell_TrayWnd', 'Shell_SecondaryTrayWnd'):
            return
        monitor = tuple(win32api.GetMonitorInfo(win32api.MonitorFromWindow(hwnd))['Monitor'])
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if right <= left or bottom <= top:
            return
        ml, mt, mr, mb = monitor
        edge = ((1 if abs(top-mt) < abs(bottom-mb) else 3) if right-left > bottom-top
                else (0 if abs(left-ml) < abs(right-mr) else 2))
        if name == 'Shell_TrayWnd':
            data = AppBarData()
            data.cbSize = ctypes.sizeof(data)
            query = ctypes.windll.shell32.SHAppBarMessage
            query.argtypes = [wt.DWORD, ctypes.POINTER(AppBarData)]
            query.restype = ctypes.c_size_t
            if query(5, ctypes.byref(data)):
                edge = data.uEdge
                left, top, right, bottom = data.rc.left, data.rc.top, data.rc.right, data.rc.bottom
        thickness = right-left if edge in (0, 2) else bottom-top
        if thickness > 0:
            result.append((monitor, edge, thickness))
    win32gui.EnumWindows(visit, None)
    return result


def select_area(x, y, w, h, areas):
    """Prefer the greatest intersection, then the nearest monitor in gaps."""
    def score(area):
        left, top, right, bottom = area
        overlap = (max(0, min(x + w, right) - max(x, left)) *
                   max(0, min(y + h, bottom) - max(y, top)))
        cx, cy = x + w / 2, y + h / 2
        distance = (max(left - cx, 0, cx - right) ** 2 +
                    max(top - cy, 0, cy - bottom) ** 2)
        return overlap, -distance
    return max(areas, key=score)


def area_for(root, x, y, w=1, h=1):
    return select_area(x, y, w, h, work_areas(root))


def clamp(x, y, w, h, area, margin=10):
    left, top, right, bottom = area
    return (max(left + margin, min(x, right - w - margin)),
            max(top + margin, min(y, bottom - h - margin)))


CORNERS = {"bottom_left": "Bottom left", "top_left": "Top left",
           "bottom_right": "Bottom right", "top_right": "Top right"}


def corner_position(area, w, h, corner, margin=16):
    if corner not in CORNERS:
        corner = "bottom_right"
    left, top, right, bottom = area
    return clamp(left + margin if corner.endswith("left") else right - w - margin,
                 top + margin if corner.startswith("top") else bottom - h - margin,
                 w, h, area, margin)
