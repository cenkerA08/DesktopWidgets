"""
main.py - Entry point for Desktop Widget v8.
Run: python main.py
"""
import sys, os


def _fix_tcltk():
    """
    Set TCL_LIBRARY and TK_LIBRARY before tkinter loads.
    Only runs inside a PyInstaller bundle (sys.frozen is set).
    During normal development / venv runs this is a no-op — Python's own
    Tcl/Tk installation is already on the path and doesn't need help.
    """
    # Skip entirely when running from source — Python's own install handles this.
    # Running this outside a bundle is what causes the "poisoned TCL_LIBRARY"
    # bug where a stale env var from a previous build breaks the venv run.
    if not getattr(sys, "frozen", False):
        return

    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    # Inside the bundle: _MEIPASS is where PyInstaller unpacked everything.
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    # Search for init.tcl under the bundle directory
    for root_dir, dirs, files in os.walk(base):
        if "init.tcl" in files:
            os.environ.setdefault("TCL_LIBRARY", root_dir)
            break

    # Search for tk.tcl for TK_LIBRARY
    for root_dir, dirs, files in os.walk(base):
        if "tk.tcl" in files:
            os.environ.setdefault("TK_LIBRARY", root_dir)
            break


_fix_tcltk()

# ── Auto-updater ────────────────────────────────────────────
# Runs before the UI starts — checks GitHub for a newer release
# and silently installs it. No-op when running from source.
try:
    from updater import check_and_apply
    check_and_apply()
except Exception:
    pass   # never crash on updater failure

import tkinter as tk
from tkinter import messagebox


def check_deps() -> list[str]:
    missing = []
    try:
        from PIL import Image
    except ImportError:
        missing.append("pillow")
    try:
        import win32gui
    except ImportError:
        missing.append("pywin32")
    return missing


def main() -> None:
    missing = check_deps()
    if missing:
        r = tk.Tk(); r.withdraw()
        messagebox.showwarning(
            "Missing packages",
            f"Install required packages:\n\n  pip install {' '.join(missing)}\n\n"
            "Then restart the widget.")
        r.destroy()
        sys.exit(1)

    try:
        from manager import Manager
        app = Manager()
        app.run()
    except Exception:
        import traceback
        err = traceback.format_exc()
        print(err)
        try:
            r = tk.Tk(); r.withdraw()
            messagebox.showerror("Startup error",
                f"Desktop Widget failed to start:\n\n{err}")
            r.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()