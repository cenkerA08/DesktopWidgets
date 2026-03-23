"""
updater.py — Auto-updater for DesktopWidget.
Checks GitHub for a newer release, downloads and installs it, then restarts.
Only active inside a PyInstaller frozen build.
"""
from __future__ import annotations
import os, sys, json, shutil, tempfile, zipfile, subprocess
import urllib.request

try:
    from version import VERSION, GITHUB_REPO
except ImportError:
    VERSION = "0.0.0"
    GITHUB_REPO = ""

API_URL     = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
TIMEOUT     = 8
UPDATE_FLAG = "--updated"


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.lstrip("v").strip().split("."))
    except Exception:
        return (0,)


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


def _download(url: str, dest: str) -> bool:
    """
    Download a file from a URL to dest.
    Uses proper headers so GitHub registers the download in its counter.
    urllib.request.urlretrieve does not send the right headers through
    GitHub's redirect, causing downloads to show as 0 in release stats.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "DesktopWidget-Updater",
                "Accept": "application/octet-stream",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return os.path.isfile(dest) and os.path.getsize(dest) > 0
    except Exception:
        return False


def _extract_and_replace(zip_path: str, install_dir: str) -> list[str]:
    """
    Extract zip and copy files over current install.
    Returns list of files that need swapping after restart (locked exes).
    """
    SKIP     = {"data.json"}
    pending  = []   # files that couldn't be replaced (locked)

    tmp = tempfile.mkdtemp(prefix="dw_upd_")
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)

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


def check_and_apply() -> None:
    """Call from main.py before the UI starts."""
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
    if _parse_version(tag) <= _parse_version(VERSION):
        return   # already up to date

    url, fname = _find_zip(release)
    if not url:
        return   # no zip asset

    install_dir = os.path.dirname(sys.executable)
    exe_path    = sys.executable
    tmp_zip     = os.path.join(tempfile.gettempdir(), fname)

    if not _download(url, tmp_zip):
        return

    pending = _extract_and_replace(tmp_zip, install_dir)

    try: os.remove(tmp_zip)
    except Exception: pass

    if pending:
        # Some files were locked — use swap bat to finish after exit
        bat = _write_swap_bat(install_dir, pending, exe_path)
        subprocess.Popen(["cmd", "/c", bat],
                         creationflags=0x08000000, close_fds=True)
    else:
        # All files replaced — just restart
        subprocess.Popen([exe_path, UPDATE_FLAG], close_fds=True)

    sys.exit(0)