"""
main.py - Entry point for Desktop Widget v8.
Run: python main.py
"""
import sys, os
from pathlib import Path
from desktop_widgets.services.dpi import enable_dpi_awareness

enable_dpi_awareness()


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

    bases = [
        Path(getattr(sys, "_MEIPASS", "")),
        Path(sys.executable).resolve().parent,
        Path(sys.executable).resolve().parent / "_internal",
    ]
    candidates = []
    for base in bases:
        if base:
            candidates.extend([
                (base / "_tcl_data", base / "_tk_data"),
                (base / "tcl", base / "tk"),
                (base / "_internal" / "_tcl_data", base / "_internal" / "_tk_data"),
            ])

    for tcl_dir, tk_dir in candidates:
        if not os.environ.get("TCL_LIBRARY") and (tcl_dir / "init.tcl").is_file():
            os.environ["TCL_LIBRARY"] = str(tcl_dir)
        if not os.environ.get("TK_LIBRARY") and (tk_dir / "tk.tcl").is_file():
            os.environ["TK_LIBRARY"] = str(tk_dir)
        if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
            return

    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    for root_dir, dirs, files in os.walk(base):
        if not os.environ.get("TCL_LIBRARY") and "init.tcl" in files:
            os.environ["TCL_LIBRARY"] = root_dir
        if not os.environ.get("TK_LIBRARY") and "tk.tcl" in files:
            os.environ["TK_LIBRARY"] = root_dir
        if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
            break


_fix_tcltk()

# ── First-run desktop shortcut ──────────────────────────────
# On first launch from a new install location, create a desktop
# shortcut so the user never needs to find the .exe again.
def _maybe_create_shortcut() -> None:
    # Only in a frozen (PyInstaller) build, not during dev
    if not getattr(sys, "frozen", False):
        return
    try:
        import json, ctypes
        from desktop_widgets.services.safe_io import atomic_write_json
        # Use AppData to track whether we've made a shortcut for this install path
        appdata  = os.environ.get("APPDATA", os.path.expanduser("~"))
        flag_dir = os.path.join(appdata, "DesktopWidget")
        os.makedirs(flag_dir, exist_ok=True)
        flag_file = os.path.join(flag_dir, "shortcut_created.json")

        exe_path = sys.executable
        # Load existing flag
        created_for = ""
        if os.path.exists(flag_file):
            try:
                created_for = json.load(open(flag_file)).get("exe_path", "")
            except Exception:
                pass

        if created_for == exe_path:
            return  # shortcut already exists for this install path

        # Create the shortcut
        from desktop_widgets.utils import create_desktop_shortcut
        ok = create_desktop_shortcut(exe_path, "DesktopWidget")
        if ok:
            atomic_write_json(flag_file, {"exe_path": exe_path})
    except Exception:
        pass  # never crash on shortcut failure

_maybe_create_shortcut()

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
        from desktop_widgets.manager import Manager
        app = Manager()

        import json
        from desktop_widgets.services.safe_io import atomic_write_json
        appdata   = os.environ.get("APPDATA", os.path.expanduser("~"))
        os.makedirs(os.path.join(appdata, "DesktopWidget"), exist_ok=True)

        # ── Changelog (update) ────────────────────────────
        from desktop_widgets.version import VERSION
        ver_flag  = os.path.join(appdata, "DesktopWidget", "last_seen_version.json")
        last_seen = ""
        if os.path.exists(ver_flag):
            try: last_seen = json.load(open(ver_flag)).get("version", "")
            except: pass
        if last_seen != VERSION:
            atomic_write_json(ver_flag, {"version": VERSION})
            import desktop_widgets.config as config
            from desktop_widgets.services.release_notes import load_notes
            notes = load_notes(VERSION, config.DATA_DIR)
            if notes and last_seen:  # only show changelog if this is an UPDATE not first run
                from desktop_widgets.ui.changelog_screen import ChangelogScreen
                ChangelogScreen(app, VERSION, notes)

        # ── Welcome (first ever launch) ───────────────────
        wel_flag = os.path.join(appdata, "DesktopWidget", "welcomed.json")
        if not os.path.exists(wel_flag):
            atomic_write_json(wel_flag, {"welcomed": True})
            from desktop_widgets.ui.welcome_screen import WelcomeScreen
            WelcomeScreen(app, on_done=lambda: None)

        from desktop_widgets.services.updater import start_update_check
        import desktop_widgets.config as config
        start_update_check(app.root, before_install=lambda: config.save(app.data),
                           theme=config.get_theme(app.data))
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
