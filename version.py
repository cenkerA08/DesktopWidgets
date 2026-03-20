"""
version.py — Single source of truth for the app version.
Bump this before every release.
"""

VERSION = "1.0.22"

# Your GitHub repo — change this to your actual username/repo
GITHUB_REPO = "cenkerA08/DesktopWidgets"

# What's new in each version — shown once on first launch after an update.
# Add a new entry here every time you bump VERSION.
CHANGELOG: dict[str, list[str]] = {
    "1.0.0": [
        "Initial release",
        "App folder widgets with drag & drop",
        "Stats+, Notes, Media and Files widgets",
        "25 built-in themes",
        "Auto-updater",
    ],
}
