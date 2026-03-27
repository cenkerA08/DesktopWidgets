"""
version.py — Single source of truth for the app version.
Bump this before every release.
"""

VERSION = "1.0.31"

# Your GitHub repo — change this to your actual username/repo
GITHUB_REPO = "cenkerA08/DesktopWidgets"

# What's new in each version — shown once on first launch after an update.
# Add a new entry here every time you bump VERSION.
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
    ]





}
