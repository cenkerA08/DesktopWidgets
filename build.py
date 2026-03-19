"""
build.py — One-click PyInstaller build + optional GitHub release upload.

Usage:
  python build.py              # just build the exe
  python build.py --release    # build, bump version, zip, upload to GitHub

Requirements for --release:
  pip install requests
  Set GITHUB_TOKEN env var:  set GITHUB_TOKEN=ghp_your_token_here
"""
import os, sys, shutil, subprocess, textwrap, glob, zipfile, json, re

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR    = os.path.join(PROJECT_DIR, "dist", "DesktopWidget")
BUILD_DIR   = os.path.join(PROJECT_DIR, "build")
SPEC_FILE   = os.path.join(PROJECT_DIR, "DesktopWidget.spec")

SOURCE_FILES = [
    "main.py", "manager.py", "config.py", "theme.py", "utils.py",
    "version.py", "updater.py",
    "base_widget.py", "group_widget.py",
    "statsplus_widget.py", "notes_widget.py", "docs_widget.py",
    "media_widget.py", "color_picker.py",
    "focus_overlay.py", "settings_screen.py", "tray_bar.py",
]


# ── Version helpers ────────────────────────────────────────────────────────

def read_version() -> str:
    vf = os.path.join(PROJECT_DIR, "version.py")
    m  = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', open(vf).read())
    return m.group(1) if m else "1.0.0"


def bump_version(v: str, part: str = "patch") -> str:
    major, minor, patch = (int(x) for x in v.split("."))
    if part == "major":   major += 1; minor = 0; patch = 0
    elif part == "minor": minor += 1; patch = 0
    else:                 patch += 1
    return f"{major}.{minor}.{patch}"


def write_version(v: str) -> None:
    vf  = os.path.join(PROJECT_DIR, "version.py")
    src = open(vf).read()
    src = re.sub(r'VERSION\s*=\s*["\'][^"\']+["\']', f'VERSION = "{v}"', src)
    open(vf, "w").write(src)
    print(f"  version.py → {v}")


# ── Tcl/Tk discovery ──────────────────────────────────────────────────────

def find_tcl_tk():
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        tcl_dir = root.tk.exprstring("$tcl_library")
        tk_dir  = root.tk.exprstring("$tk_library")
        root.destroy()
        return tcl_dir, tk_dir
    except Exception:
        return None, None


# ── PyInstaller spec ──────────────────────────────────────────────────────

def write_spec(tcl_dir, tk_dir) -> None:
    data_lines = []
    if tcl_dir and os.path.isdir(tcl_dir):
        data_lines.append(f"    (r'{tcl_dir}', 'tcl'),")
    if tk_dir and os.path.isdir(tk_dir):
        data_lines.append(f"    (r'{tk_dir}', 'tk'),")
    datas   = "\n".join(data_lines)
    hidden  = "    'winsdk'," if __import__('importlib').util.find_spec('winsdk') else ""
    main_py = os.path.join(PROJECT_DIR, "main.py")
    icon    = os.path.join(PROJECT_DIR, "icon.ico")
    icon_line = f"icon=r'{icon}'," if os.path.isfile(icon) else "icon=None,"

    lines = [
        "# -*- mode: python ; coding: utf-8 -*-",
        "from PyInstaller.utils.hooks import collect_all",
        "",
        "tk_datas, tk_binaries, tk_hiddenimports = collect_all('tkinter')",
        "",
        "a = Analysis(",
        f"    [r'{main_py}'],",
        f"    pathex=[r'{PROJECT_DIR}'],",
        "    binaries=tk_binaries,",
        "    datas=tk_datas + [",
        datas,
        "    ],",
        "    hiddenimports=tk_hiddenimports + [",
        "        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw',",
        "        'PIL.ImageFont', 'PIL.ImageFilter',",
        "        'psutil', 'win32gui', 'win32con', 'win32api',",
        "        'wmi', 'comtypes',",
        hidden,
        "    ],",
        "    hookspath=[],",
        "    runtime_hooks=[],",
        "    excludes=['matplotlib','numpy','scipy','pandas','pytest'],",
        "    noarchive=False,",
        ")",
        "",
        "pyz = PYZ(a.pure)",
        "",
        "exe = EXE(",
        "    pyz, a.scripts, [],",
        "    exclude_binaries=True,",
        "    name='DesktopWidget',",
        "    debug=False,",
        "    bootloader_ignore_signals=False,",
        "    strip=False,",
        "    upx=True,",
        "    console=False,",
        f"    {icon_line}",
        ")",
        "",
        "coll = COLLECT(",
        "    exe, a.binaries, a.datas,",
        "    strip=False,",
        "    upx=True,",
        "    upx_exclude=[],",
        "    name='DesktopWidget',",
        ")",
    ]
    with open(SPEC_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("  spec written")


# ── Build ─────────────────────────────────────────────────────────────────

def build() -> None:
    print("\n── Build ─────────────────────────────")
    for d in [DIST_DIR, BUILD_DIR]:
        shutil.rmtree(d, ignore_errors=True)

    print("  finding Tcl/Tk...")
    tcl_dir, tk_dir = find_tcl_tk()
    write_spec(tcl_dir, tk_dir)

    print("  running PyInstaller...")
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", SPEC_FILE],
        cwd=PROJECT_DIR
    )
    if r.returncode != 0:
        print("PyInstaller failed"); sys.exit(1)
    print(f"  built → {DIST_DIR}")


# ── Zip ───────────────────────────────────────────────────────────────────

def make_zip(version: str) -> str:
    zip_name = f"DesktopWidget_v{version}.zip"
    zip_path = os.path.join(PROJECT_DIR, "dist", zip_name)
    print(f"\n── Zipping → {zip_name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(DIST_DIR):
            for fname in files:
                fpath  = os.path.join(root, fname)
                arcname = os.path.join(
                    "DesktopWidget",
                    os.path.relpath(fpath, DIST_DIR)
                )
                z.write(fpath, arcname)
    size_mb = os.path.getsize(zip_path) / 1_048_576
    print(f"  {zip_path}  ({size_mb:.1f} MB)")
    return zip_path


# ── GitHub release ────────────────────────────────────────────────────────

def github_release(version: str, zip_path: str) -> None:
    try:
        import requests
    except ImportError:
        print("\nInstall requests to upload:  pip install requests")
        return

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("\nSet GITHUB_TOKEN env var to upload to GitHub.")
        print("  Windows:  set GITHUB_TOKEN=ghp_xxxx")
        return

    vf    = os.path.join(PROJECT_DIR, "version.py")
    m     = re.search(r'GITHUB_REPO\s*=\s*["\']([^"\']+)["\']', open(vf).read())
    repo  = m.group(1) if m else ""
    if not repo or repo.startswith("YOUR_"):
        print("\nSet GITHUB_REPO in version.py first.")
        return

    tag   = f"v{version}"
    hdrs  = {"Authorization": f"token {token}",
             "Accept": "application/vnd.github+json"}

    print(f"\n── GitHub release {tag} → {repo}")

    # Create release
    r = requests.post(
        f"https://api.github.com/repos/{repo}/releases",
        headers=hdrs,
        json={
            "tag_name":         tag,
            "name":             f"DesktopWidget {tag}",
            "body":             f"DesktopWidget {tag}",
            "draft":            False,
            "prerelease":       False,
            "generate_release_notes": True,
        }
    )
    if r.status_code not in (200, 201):
        print(f"  create release failed: {r.status_code} {r.text[:200]}")
        return

    upload_url = r.json()["upload_url"].split("{")[0]
    print(f"  release created: {upload_url}")

    # Upload zip asset
    fname = os.path.basename(zip_path)
    with open(zip_path, "rb") as f:
        data = f.read()
    r2 = requests.post(
        upload_url,
        headers={**hdrs, "Content-Type": "application/zip"},
        params={"name": fname},
        data=data
    )
    if r2.status_code in (200, 201):
        print(f"  uploaded {fname} ✓")
        print(f"  → https://github.com/{repo}/releases/tag/{tag}")
    else:
        print(f"  upload failed: {r2.status_code} {r2.text[:200]}")


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    do_release = "--release" in sys.argv
    part       = "patch"
    if "--minor" in sys.argv: part = "minor"
    if "--major" in sys.argv: part = "major"

    if do_release:
        old_v = read_version()
        new_v = bump_version(old_v, part)
        print(f"Bumping version {old_v} → {new_v}")
        write_version(new_v)
        version = new_v
    else:
        version = read_version()
        print(f"Building version {version} (no release)")

    build()

    if do_release:
        zip_path = make_zip(version)
        github_release(version, zip_path)
        print("\n── Done ──────────────────────────────")
        print(f"  Friends can now download and run DesktopWidget_v{version}.zip")
        print(f"  Future updates will install silently on startup.")
    else:
        print(f"\n── Done ──────────────────────────────")
        print(f"  Exe → {DIST_DIR}\\DesktopWidget.exe")
        print(f"  Run with --release to publish to GitHub.")