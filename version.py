"""
version.py — Single source of truth for the app version.
Bump this before every release.
"""

VERSION = "1.0.23"

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
    ]
}
