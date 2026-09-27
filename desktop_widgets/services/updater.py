"""
updater.py — Auto-updater for DesktopWidget.
Checks GitHub for a newer release, downloads and installs it, then restarts.
Only active inside a PyInstaller frozen build.
"""
from __future__ import annotations
import os, sys, json, shutil, tempfile, subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from desktop_widgets.services.safe_io import parse_sha256_text, safe_extract_zip, verify_sha256

try:
    from desktop_widgets.version import VERSION, GITHUB_REPO, compare_versions
except ImportError:
    VERSION = "0.0.0"
    GITHUB_REPO = ""
    def compare_versions(left: str, right: str) -> int:
        return 0

API_URL     = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
TIMEOUT     = 8
UPDATE_FLAG = "--updated"


def _fetch_latest() -> dict | None:
    try:
        req = urllib.request.Request(
            API_URL,
            headers={"User-Agent": "DesktopWidget-Updater",
                     "Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _find_zip(release: dict):
    for asset in release.get("assets", []):
        if asset.get("name", "").lower().endswith(".zip"):
            return asset["browser_download_url"], asset["name"]
    return None, None


def _find_checksum(release: dict, zip_name: str):
    wanted = {f"{zip_name}.sha256".lower(), "desktopwidget.sha256"}
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.lower() in wanted or name.lower().endswith(".sha256"):
            return asset.get("browser_download_url"), name
    return None, None


def _download(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "DesktopWidget-Updater"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response, open(dest, "wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    if not os.path.isfile(dest) or os.path.getsize(dest) <= 0:
        raise RuntimeError("Downloaded update is empty.")


def _download_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "DesktopWidget-Updater"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.read(64 * 1024).decode("utf-8", errors="replace")


def _extract_and_replace(zip_path: str, install_dir: str) -> list[str]:
    """
    Extract zip and copy files over current install.
    Returns list of files that need swapping after restart (locked exes).
    """
    SKIP     = {"data.json"}
    pending  = []   # files that couldn't be replaced (locked)

    tmp = tempfile.mkdtemp(prefix="dw_upd_")
    try:
        safe_extract_zip(zip_path, tmp)

        # Handle single top-level folder in zip
        entries = os.listdir(tmp)
        src_dir = tmp
        if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
            src_dir = os.path.join(tmp, entries[0])

        for root, dirs, files in os.walk(src_dir):
            rel      = os.path.relpath(root, src_dir)
            dst_root = os.path.join(install_dir, rel) if rel != "." else install_dir
            os.makedirs(dst_root, exist_ok=True)

            for fname in files:
                if fname in SKIP:
                    continue
                src_f = os.path.join(root, fname)
                dst_f = os.path.join(dst_root, fname)
                try:
                    if os.path.isfile(dst_f):
                        os.replace(src_f, dst_f)
                    else:
                        shutil.copy2(src_f, dst_f)
                except PermissionError:
                    # File is locked (running exe) — stage it as .new
                    new_f = dst_f + ".new"
                    shutil.copy2(src_f, new_f)
                    pending.append((new_f, dst_f))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return pending


def _write_swap_bat(install_dir: str, pending: list, exe_path: str) -> str:
    """Write a batch file that swaps .new files and restarts the exe."""
    bat = os.path.join(install_dir, "_dw_swap.bat")
    lines = ["@echo off", "setlocal enabledelayedexpansion", "timeout /t 2 /nobreak >nul"]
    for new_f, dst_f in pending:
        lines.append(f'move /y "{new_f}" "{dst_f}" >nul 2>&1')
    lines += [
        f'start "" "{exe_path}" {UPDATE_FLAG}',
        'del "%~f0"',
    ]
    with open(bat, "w") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return bat


def _log_update_error(message: str) -> None:
    try:
        print(f"[updater] {message}")
    except Exception:
        pass


def check_for_update() -> dict | None:
    """Read release metadata only; never download or install an update."""
    if not getattr(sys, "frozen", False):
        return   # source run — skip
    if UPDATE_FLAG in sys.argv:
        return   # just updated — skip
    if not GITHUB_REPO or GITHUB_REPO.startswith("YOUR_"):
        return   # not configured

    release = _fetch_latest()
    if not release:
        return

    tag = release.get("tag_name", "")
    try:
        if compare_versions(tag, VERSION) <= 0:
            return   # already up to date
    except Exception:
        return   # already up to date

    url, fname = _find_zip(release)
    if not url:
        return   # no zip asset
    checksum_url, checksum_name = _find_checksum(release, fname)
    if not checksum_url:
        _log_update_error("Release has no SHA-256 checksum asset; refusing automatic update.")
        return

    return release


def start_update_check(root, before_install=lambda: None) -> None:
    """Check off-thread; ask on the Tk thread before any download or install."""
    from tkinter import messagebox
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="update-check")
    future = pool.submit(check_for_update)
    pool.shutdown(wait=False)

    def poll():
        if not future.done():
            root.after(150, poll)
            return
        try:
            release = future.result()
        except Exception as exc:
            _log_update_error(str(exc))
            return
        if not release:
            return
        # Avoid stealing an active welcome/settings dialog's grab.
        if root.grab_current():
            root.after(1000, poll)
            return
        if messagebox.askyesno(
                "Update available",
                f"DesktopWidget {release['tag_name']} is available (installed: {VERSION}).\n\n"
                "Download and install it now? The app will restart.\n"
                "Choose No to keep using this version.", parent=root):
            before_install()
            if not apply_update(release):
                messagebox.showerror("Update failed", "The update could not be installed. "
                                     "Please try again next time you start the app.", parent=root)
    root.after(150, poll)


def apply_update(release: dict) -> bool:
    """Install an update only after the UI has obtained consent."""
    url, fname = _find_zip(release)
    checksum_url, _ = _find_checksum(release, fname or "")
    if not url or not checksum_url or not fname or os.path.basename(fname) != fname:
        return False

    install_dir = os.path.dirname(sys.executable)
    exe_path    = sys.executable

    with tempfile.TemporaryDirectory(prefix="dw_upd_") as staging:
        tmp_zip = os.path.join(staging, fname)
        try:
            checksum_text = _download_text(checksum_url)
            expected_sha = parse_sha256_text(checksum_text, expected_filename=fname)
            _download(url, tmp_zip)
            actual_sha = verify_sha256(tmp_zip, expected_sha)
            _log_update_error(f"Verified update SHA-256: {actual_sha}")
        except Exception as e:
            try:
                os.remove(tmp_zip)
            except Exception:
                pass
            _log_update_error(f"Update verification failed: {e}")
            return False

        try:
            pending = _extract_and_replace(tmp_zip, install_dir)
        except Exception as e:
            _log_update_error(f"Update extraction failed: {e}")
            return False

    try:
        from desktop_widgets.config import DATA_DIR
        from desktop_widgets.services.safe_io import atomic_write_json
        atomic_write_json(os.path.join(DATA_DIR, "release_notes.json"),
                          {"version": release["tag_name"].lstrip("v"),
                           "body": release.get("body") or ""})
    except Exception as exc:
        _log_update_error(f"Could not save release notes: {exc}")

    if pending:
        # Some files were locked — use swap bat to finish after exit
        bat = _write_swap_bat(install_dir, pending, exe_path)
        subprocess.Popen(["cmd", "/c", bat],
                         creationflags=0x08000000, close_fds=True)
    else:
        # All files replaced — just restart
        subprocess.Popen([exe_path, UPDATE_FLAG], close_fds=True)

    sys.exit(0)
