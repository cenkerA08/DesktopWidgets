"""Build and optionally release DesktopWidget with PyInstaller."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from safe_io import sha256_file, write_sha256_file
from version import (
    APP_NAME,
    COMPANY_NAME,
    FILE_DESCRIPTION,
    GITHUB_REPO,
    LEGAL_COPYRIGHT,
    PRODUCT_NAME,
    VERSION,
    bump_semver,
    parse_semver,
    write_version,
)

PROJECT_DIR = Path(__file__).resolve().parent
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
SPEC_FILE = PROJECT_DIR / "DesktopWidget.spec"
VERSION_INFO_FILE = BUILD_DIR / "version_info.txt"
EXE_PATH = DIST_DIR / APP_NAME / f"{APP_NAME}.exe"
TIMESTAMP_URL = "http://timestamp.digicert.com"


def _run(cmd: list[str], *, cwd: Path = PROJECT_DIR, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check)


def clean() -> None:
    for path in (DIST_DIR, BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)


def find_tcl_tk() -> tuple[Path | None, Path | None]:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        tcl_dir = Path(root.tk.exprstring("$tcl_library"))
        tk_dir = Path(root.tk.exprstring("$tk_library"))
        root.destroy()
        return tcl_dir if tcl_dir.is_dir() else None, tk_dir if tk_dir.is_dir() else None
    except Exception:
        return None, None


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    major, minor, patch = parse_semver(version)
    return major, minor, patch, 0


def write_version_info(version: str) -> Path:
    major, minor, patch, build = _version_tuple(version)
    text = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', '{COMPANY_NAME}'),
          StringStruct('FileDescription', '{FILE_DESCRIPTION}'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', '{APP_NAME}'),
          StringStruct('LegalCopyright', '{LEGAL_COPYRIGHT}'),
          StringStruct('OriginalFilename', '{APP_NAME}.exe'),
          StringStruct('ProductName', '{PRODUCT_NAME}'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    VERSION_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_INFO_FILE.write_text(text, encoding="utf-8")
    return VERSION_INFO_FILE


def write_spec(tcl_dir: Path | None, tk_dir: Path | None, version: str) -> None:
    data_lines: list[str] = []
    if tcl_dir and tcl_dir.is_dir():
        data_lines.append(f"        (r'{tcl_dir}', '_tcl_data'),")
    if tk_dir and tk_dir.is_dir():
        data_lines.append(f"        (r'{tk_dir}', '_tk_data'),")

    hidden_lines = [
        "        'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageDraw',",
        "        'PIL.ImageFont', 'PIL.ImageFilter',",
        "        'psutil', 'win32gui', 'win32con', 'win32api',",
        "        'wmi', 'comtypes', 'pystray', 'tkinterdnd2',",
    ]
    if importlib.util.find_spec("winsdk"):
        hidden_lines.append("        'winsdk',")

    icon = PROJECT_DIR / "icon.ico"
    icon_line = f"    icon=r'{icon}'," if icon.is_file() else "    icon=None,"
    version_info = write_version_info(version)
    datas = "\n".join(data_lines)
    hidden = "\n".join(hidden_lines)

    text = f"""# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

tk_datas, tk_binaries, tk_hiddenimports = collect_all('tkinter')
try:
    dnd_datas, dnd_binaries, dnd_hiddenimports = collect_all('tkinterdnd2')
except Exception:
    dnd_datas, dnd_binaries, dnd_hiddenimports = [], [], []

a = Analysis(
    [r'{PROJECT_DIR / "main.py"}'],
    pathex=[r'{PROJECT_DIR}'],
    binaries=tk_binaries + dnd_binaries,
    datas=tk_datas + dnd_datas + [
{datas}
    ],
    hiddenimports=tk_hiddenimports + dnd_hiddenimports + [
{hidden}
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'pandas', 'pytest'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
{icon_line}
    version=r'{version_info}',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='{APP_NAME}',
)
"""
    SPEC_FILE.write_text(text, encoding="utf-8")
    print("Spec written")


def _find_signtool() -> Path | None:
    candidates: list[Path] = []
    for root_name in ("ProgramFiles(x86)", "ProgramFiles"):
        root = os.environ.get(root_name)
        if not root:
            continue
        kits = Path(root) / "Windows Kits" / "10" / "bin"
        if kits.is_dir():
            candidates.extend(sorted(kits.glob(r"*\x64\signtool.exe"), reverse=True))
            candidates.extend(sorted(kits.glob(r"*\x86\signtool.exe"), reverse=True))
    path_ext = ".exe" if os.name == "nt" else ""
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(folder) / f"signtool{path_ext}"
        if candidate.is_file():
            candidates.append(candidate)
    return candidates[0] if candidates else None


def sign_executable(exe_path: Path) -> bool:
    certificate = os.environ.get("SIGN_CERTIFICATE")
    cert_password = os.environ.get("SIGN_CERTIFICATE_PASSWORD")
    thumbprint = os.environ.get("SIGN_CERTIFICATE_THUMBPRINT")

    if not certificate and not thumbprint:
        print("Signing not configured; leaving executable unsigned.")
        return False

    signtool = _find_signtool()
    if not signtool:
        raise RuntimeError("Signing was configured, but signtool.exe was not found.")

    cmd = [str(signtool), "sign", "/fd", "SHA256", "/td", "SHA256", "/tr", TIMESTAMP_URL]
    if thumbprint:
        cmd.extend(["/sha1", thumbprint])
    else:
        cert_path = Path(certificate)
        if not cert_path.is_file():
            raise RuntimeError("SIGN_CERTIFICATE does not point to a certificate file.")
        cmd.extend(["/f", str(cert_path)])
        if cert_password:
            cmd.extend(["/p", cert_password])
    cmd.append(str(exe_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"signtool sign failed: {result.stderr or result.stdout}")

    verify = subprocess.run(
        [str(signtool), "verify", "/pa", "/v", str(exe_path)],
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        raise RuntimeError(f"signtool verify failed: {verify.stderr or verify.stdout}")
    return True


def build(version: str = VERSION) -> tuple[Path, bool, str]:
    print("Build")
    clean()
    tcl_dir, tk_dir = find_tcl_tk()
    write_spec(tcl_dir, tk_dir, version)
    _run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC_FILE)])
    if not EXE_PATH.is_file():
        raise RuntimeError(f"Expected executable was not produced: {EXE_PATH}")
    signed = sign_executable(EXE_PATH)
    digest = sha256_file(EXE_PATH)
    checksum_file = write_sha256_file(EXE_PATH)
    print(f"Checksum written: {checksum_file}")
    print_summary(version, EXE_PATH, digest, signed)
    return EXE_PATH, signed, digest


def print_summary(version: str, executable: Path, digest: str, signed: bool) -> None:
    print()
    print("Build complete")
    print(f"Version: {version}")
    print(f"Executable: {executable}")
    print(f"SHA-256: {digest}")
    print(f"Signed: {'yes' if signed else 'no'}")


def make_zip(version: str) -> Path:
    zip_path = DIST_DIR / f"{APP_NAME}_v{version}.zip"
    app_dir = DIST_DIR / APP_NAME
    print(f"Zipping: {zip_path.name}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in app_dir.rglob("*"):
            if path.is_file():
                z.write(path, path.relative_to(app_dir.parent))
    write_sha256_file(zip_path)
    print(f"Release ZIP SHA-256: {sha256_file(zip_path)}")
    return zip_path


def github_release(version: str, zip_path: Path) -> None:
    try:
        import requests
    except ImportError:
        print("Install requests to upload: pip install requests")
        return

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("Set GITHUB_TOKEN env var to upload to GitHub.")
        return

    repo = GITHUB_REPO
    if not repo or repo.startswith("YOUR_"):
        print("Set GITHUB_REPO in version.py first.")
        return

    tag = f"v{version}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    print(f"GitHub release {tag} -> {repo}")

    release_response = requests.post(
        f"https://api.github.com/repos/{repo}/releases",
        headers=headers,
        json={
            "tag_name": tag,
            "name": f"{APP_NAME} {tag}",
            "body": f"{APP_NAME} {tag}",
            "draft": False,
            "prerelease": False,
            "generate_release_notes": True,
        },
        timeout=(8, 30),
    )
    if release_response.status_code not in (200, 201):
        print(f"Create release failed: {release_response.status_code} {release_response.text[:200]}")
        return

    upload_url = release_response.json()["upload_url"].split("{")[0]
    assets = [zip_path, zip_path.with_name("DesktopWidget.sha256")]
    for asset in assets:
        content_type = "application/zip" if asset.suffix.lower() == ".zip" else "text/plain"
        with open(asset, "rb") as f:
            upload_response = requests.post(
                upload_url,
                headers={**headers, "Content-Type": content_type},
                params={"name": asset.name},
                data=f,
                timeout=(8, 120),
            )
        if upload_response.status_code in (200, 201):
            print(f"Uploaded {asset.name}")
        else:
            print(f"Upload failed for {asset.name}: {upload_response.status_code} {upload_response.text[:200]}")

    print(f"https://github.com/{repo}/releases/tag/{tag}")


def release(part: str = "patch") -> None:
    old_version = VERSION
    new_version = bump_semver(old_version, part)
    print(f"Bumping version {old_version} -> {new_version}")
    write_version(new_version)
    try:
        build(new_version)
    except Exception:
        write_version(old_version)
        raise
    zip_path = make_zip(new_version)
    github_release(new_version, zip_path)
    print(f"Release workflow finished for {new_version}")


def _part_from_args(args: list[str]) -> str:
    if "--major" in args:
        return "major"
    if "--minor" in args:
        return "minor"
    return "patch"


if __name__ == "__main__":
    if "--release" in sys.argv:
        release(_part_from_args(sys.argv))
    else:
        print(f"Building version {VERSION} (no release)")
        build(VERSION)
