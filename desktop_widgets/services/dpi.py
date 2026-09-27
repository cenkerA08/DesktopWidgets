"""Opt out of Windows bitmap stretching before creating any Tk windows."""
import ctypes
import sys


def enable_dpi_awareness():
    if sys.platform != 'win32':
        return
    try:
        setter = ctypes.windll.user32.SetProcessDpiAwarenessContext
        setter.argtypes = [ctypes.c_void_p]
        setter.restype = ctypes.c_bool
        setter(ctypes.c_void_p(-4))  # Per-monitor v2; an existing manifest takes priority.
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
