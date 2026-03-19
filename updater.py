"""
updater.py — Silent auto-updater for DesktopWidget.

Flow:
  1. Check GitHub releases API for latest version tag
  2. If newer than current VERSION, download the zip asset
  3. Extract into a temp folder
  4. Replace current install files with new ones
  5. Restart the app

Called from main.py before the UI starts.
Only runs inside a PyInstaller bundle (sys.frozen=True).
"""
from __future__ import annotations
import os, sys, json, shutil, tempfile, zipfile, subprocess, time
import urllib.request, urllib.error

try:
    from version import VERSION, GITHUB_REPO
except ImportError:
    VERSION = "0.0.0"
    GITHUB_REPO = ""

API_URL     = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
TIMEOUT     = 8    # seconds for HTTP requests
UPDATE_FLAG = "--updated"   # argv flag set after a successful update


def _parse_version(v: str) -> tuple[int, ...]:
    """'v1.2.3' or '1.2.3' → (1, 2, 3)"""
    v = v.lstrip("v").strip()
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def _is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


def _fetch_latest() -> dict | None:
    """Return the latest release JSON from GitHub, or None on error."""
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


def _find_zip_asset(release: dict) -> tuple[str, str] | None:
    """Return (download_url, filename) for the first .zip asset, or None."""
    for asset in release.get("assets", []):
        if asset.get("name", "").lower().endswith(".zip"):
            return asset["browser_download_url"], asset["name"]
    return None


def _download(url: str, dest: str) -> bool:
    """Download url to dest file, return True on success."""
    try:
        def _progress(count, block, total):
            pass  # silent
        urllib.request.urlretrieve(url, dest, _progress)
        return os.path.isfile(dest) and os.path.getsize(dest) > 0
    except Exception:
        return False


def _replace_files(zip_path: str, install_dir: str) -> bool:
    """
    Extract zip into a temp dir, then copy all files over the current install.
    Skips data.json so user settings are preserved.
    Returns True on success.
    """
    try:
        tmp = tempfile.mkdtemp(prefix="dw_update_")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)

        # The zip may have a single top-level folder — find actual content
        entries = os.listdir(tmp)
        src_dir = tmp
        if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
            src_dir = os.path.join(tmp, entries[0])

        SKIP = {"data.json"}   # preserve user data

        for root, dirs, files in os.walk(src_dir):
            rel = os.path.relpath(root, src_dir)
            dst_root = os.path.join(install_dir, rel) if rel != "." else install_dir
            os.makedirs(dst_root, exist_ok=True)
            for fname in files:
                if fname in SKIP:
                    continue
                src_f = os.path.join(root, fname)
                dst_f = os.path.join(dst_root, fname)
                # On Windows, can't overwrite a running exe — rename it first
                if os.path.isfile(dst_f):
                    try:
                        os.replace(src_f, dst_f)
                    except PermissionError:
                        # File is locked (running exe) — write a .new file
                        # and a batch helper will swap it on next boot
                        shutil.copy2(src_f, dst_f + ".new")
                else:
                    shutil.copy2(src_f, dst_f)

        shutil.rmtree(tmp, ignore_errors=True)
        return True
    except Exception as e:
        print(f"[updater] replace error: {e}")
        return False


def _write_swap_batch(install_dir: str, exe_name: str) -> None:
    """
    Write a .bat that swaps any .new files into place and re-launches the exe.
    Runs after the main process exits so the exe is no longer locked.
    """
    bat = os.path.join(install_dir, "_dw_swap.bat")
    exe = os.path.join(install_dir, exe_name)
    lines = [
        "@echo off",
        "timeout /t 2 /nobreak >nul",
        # Swap all .new files
        f'for /r "{install_dir}" %%f in (*.new) do (',
        '    set "dst=%%~dpnf"',
        '    move /y "%%f" "!dst!" >nul 2>&1',
        ')',
        f'start "" "{exe}" {UPDATE_FLAG}',
        f'del "%~f0"',   # self-delete
    ]
    with open(bat, "w") as f:
        f.write("\r\n".join(lines))


def _restart(install_dir: str, swap_needed: bool) -> None:
    """Restart the app, optionally via the swap batch first."""
    exe = os.path.basename(sys.executable)
    if swap_needed:
        bat = os.path.join(install_dir, "_dw_swap.bat")
        if os.path.isfile(bat):
            subprocess.Popen(
                ["cmd", "/c", bat],
                creationflags=0x08000000,   # CREATE_NO_WINDOW
                close_fds=True
            )
    else:
        subprocess.Popen(
            [sys.executable, UPDATE_FLAG],
            close_fds=True
        )
    sys.exit(0)


def check_and_apply(silent: bool = True) -> None:
    """
    Main entry point. Call this from main.py before starting the UI.
    Does nothing when running from source (only active in frozen builds).
    """
    # Only run in frozen (PyInstaller) builds
    if not getattr(sys, "frozen", False):
        return

    # Don't check again immediately after a successful update
    if UPDATE_FLAG in sys.argv:
        return

    if not GITHUB_REPO or GITHUB_REPO.startswith("YOUR_"):
        return   # not configured

    release = _fetch_latest()
    if not release:
        return

    tag = release.get("tag_name", "")
    if not _is_newer(tag, VERSION):
        return   # already up to date

    asset = _find_zip_asset(release)
    if not asset:
        return   # no zip in this release

    url, fname = asset
    install_dir = os.path.dirname(sys.executable)
    tmp_zip     = os.path.join(tempfile.gettempdir(), fname)

    ok = _download(url, tmp_zip)
    if not ok:
        return

    swap_needed = _replace_files(tmp_zip, install_dir)

    try:
        os.remove(tmp_zip)
    except Exception:
        pass

    if swap_needed:
        exe_name = os.path.basename(sys.executable)
        _write_swap_batch(install_dir, exe_name)
        _restart(install_dir, swap_needed=True)
    else:
        _restart(install_dir, swap_needed=False)