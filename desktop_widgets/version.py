"""
version.py — Single source of truth for the app version.
The release command bumps this automatically before building.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from desktop_widgets.services.safe_io import atomic_write_text

VERSION = "1.0.46"

# Your GitHub repo — change this to your actual username/repo
GITHUB_REPO = "cenkerA08/DesktopWidgets"

APP_NAME = "DesktopWidget"
PRODUCT_NAME = "DesktopWidget"
FILE_DESCRIPTION = "Desktop Widgets"
COMPANY_NAME = "DesktopWidget"
LEGAL_COPYRIGHT = "Copyright (c) DesktopWidget contributors"

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {value!r}")
    return tuple(int(part) for part in match.groups())


def normalize_version(value: str) -> str:
    major, minor, patch = parse_semver(value)
    return f"{major}.{minor}.{patch}"


def bump_semver(value: str, part: str = "patch") -> str:
    major, minor, patch = parse_semver(value)
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError("Version bump part must be patch, minor, or major.")
    return f"{major}.{minor}.{patch}"


def compare_versions(left: str, right: str) -> int:
    l_ver = parse_semver(left)
    r_ver = parse_semver(right)
    return (l_ver > r_ver) - (l_ver < r_ver)


def write_version(new_version: str, path: str | Path | None = None) -> None:
    normalized = normalize_version(new_version)
    target = Path(path) if path else Path(__file__)
    text = target.read_text(encoding="utf-8")
    updated = re.sub(
        r'VERSION\s*=\s*["\'][^"\']+["\']',
        f'VERSION = "{normalized}"',
        text,
        count=1,
    )
    if not re.search(r'^VERSION\s*=', text, re.MULTILINE):
        raise RuntimeError("Could not find VERSION assignment.")
    atomic_write_text(target, updated, encoding="utf-8")


def bump(part: str = "patch") -> str:
    new_version = bump_semver(VERSION, part)
    write_version(new_version)
    return new_version


def _main(argv: list[str]) -> int:
    if not argv:
        print(VERSION)
        return 0
    command = argv[0].lower()
    if command != "bump":
        print("Usage: python version.py bump [patch|minor|major]")
        return 2
    part = argv[1].lower() if len(argv) > 1 else "patch"
    old_version = VERSION
    new_version = bump_semver(old_version, part)
    write_version(new_version)
    print(f"Old version: {old_version}")
    print(f"New version: {new_version}")
    return 0

# What's new in each version — shown once on first launch after an update.
# Legacy notes only. New release notes are generated from Git/GitHub automatically.
CHANGELOG: dict[str, list[str]] = {
    "1.0.23": [
        "Welcome screen for new users",
        "Changelog screen after updates",
        "Updated looks",
    ],
    "1.0.24": [
        "New Abyss theme — black background with red accents",
    ],
    "1.0.25": [
        "Themed right-click context menus",
        "Complete theme overhaul — more distinct and vibrant themes",
        "New themes: Ember, Void, Forest, Ocean, Rust, Mono, Parchment, Silver",
    ],
    "1.0.26": [
        "Hotfix: fixed broken widgets",
        "fixed: wrong buttons to add widgets"
    ],
    "1.0.27": [
        "fixed: Discord mishandling"
    ],
    "1.0.28": [
        "Media: Support multi language"
    ],
    "1.0.29": [
        "Add/Change widget name screen updated",
        "Updated updater"
    ],
    "1.0.30": [
        "hotfix: Updated updater"
    ],
    "1.0.31": [
        "bugfix"
    ],
    "1.0.35": [
        "added rgb theme",
        "added theme cycle",
        "optimization"
    ],
    "1.0.38": [
        "added rgb theme",
        "added theme cycle",
        "fix rgb theme",
        "bug fix",
        "optimization"
    ],
    "1.0.39": [
        "added rgb theme",
        "added theme cycle",
        "fixed rgb bug",
        "changed cycle choose design",
        "fixed right click settings to go to widget directly",
    ],
    "1.0.40": [
        "screen centre snap when moving widgets",
        "reduced RAM usage",
    ],
    "1.0.42": [
        "removed RGB and theme cycle for lighter performance",
        "reduced CPU and RAM usage",
    ],
    "1.0.43": [
        "removed RGB and theme cycle for lighter performance",
        "reduced CPU and RAM usage",
        "new themes: Launch, Crimson",
    ],
    "1.0.45": [
        "Updated collapse logic, so it no longer pushes widgets from across the screen",
        "Added logic to focus widgets so u can switch between widgets in focus screen"
    ],






}


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
