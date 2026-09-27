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
            _cached = tuple(tuple(win32api.GetMonitorInfo(handle)["Work"])
                            for handle, _, _ in win32api.EnumDisplayMonitors())
        except (ImportError, OSError):
            _cached = ()
        _expires = now + 0.5
    return _cached or ((0, 0, root.winfo_screenwidth(), root.winfo_screenheight()),)


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
