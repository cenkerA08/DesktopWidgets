"""A system-wide keyboard shortcut (RegisterHotKey) on its own thread.

WM_HOTKEY is a thread message, which Tk's event loop would drop, so a small
thread owns the registration and its message loop. Presses are handed to Tk
through a queue that the Tk thread polls; Tk is never touched from here.
"""
from __future__ import annotations

import ctypes
import queue
import threading
from ctypes import wintypes

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
VK_SPACE = 0x20

# Choices offered in Settings: label -> (modifiers, key)
SHORTCUTS = {
    "Ctrl+Alt+Space":   (MOD_CONTROL | MOD_ALT, VK_SPACE),
    "Win+Alt+Space":    (MOD_WIN | MOD_ALT, VK_SPACE),
    "Ctrl+Shift+Space": (MOD_CONTROL | MOD_SHIFT, VK_SPACE),
    "Alt+Space":        (MOD_ALT, VK_SPACE),
}
DEFAULT = "Ctrl+Alt+Space"


class Hotkey:
    """Calls `callback` on the Tk thread whenever the shortcut is pressed."""

    def __init__(self, root, callback):
        self.root, self.callback = root, callback
        self.label: str | None = None
        self.ok = False              # True when Windows accepted the shortcut
        self._thread_id = None
        self._thread = None
        self._presses: queue.SimpleQueue = queue.SimpleQueue()
        self._poll()

    def set(self, label: str | None) -> bool:
        """Switch to another shortcut (None or 'Off' turns it off).
        Returns whether Windows accepted it (another app may own it)."""
        self.stop()
        self.label = label
        if not label or label not in SHORTCUTS:
            return False
        modifiers, key = SHORTCUTS[label]
        ready, result = threading.Event(), {}
        def run():
            user32 = ctypes.windll.user32
            result["ok"] = bool(user32.RegisterHotKey(None, 1, modifiers | MOD_NOREPEAT, key))
            result["tid"] = ctypes.windll.kernel32.GetCurrentThreadId()
            ready.set()
            if not result["ok"]:
                return
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self._presses.put(True)
            user32.UnregisterHotKey(None, 1)
        self._thread = threading.Thread(target=run, name="hotkey", daemon=True)
        self._thread.start()
        ready.wait(2)
        self.ok = result.get("ok", False)
        self._thread_id = result.get("tid") if self.ok else None
        return self.ok

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            if self._thread:
                self._thread.join(1)
        self._thread_id, self._thread, self.ok = None, None, False

    def _poll(self) -> None:
        pressed = False
        while not self._presses.empty():
            self._presses.get()
            pressed = True
        if pressed:
            try:
                self.callback()
            except Exception as exc:
                print(f"[hotkey] {exc}")
        try:
            self.root.after(120, self._poll)
        except Exception:
            pass
