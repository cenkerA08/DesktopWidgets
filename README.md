# DesktopWidgets

DesktopWidgets is a lightweight Windows desktop utility built with Python and Tkinter. It provides desktop widgets for app folders, files, notes, media, and system stats while staying directly runnable from source during development.

## Requirements

- Windows 10 or newer is recommended.
- Python 3.12 is recommended for the current development environment.
- Tkinter is provided by the normal Windows Python installer; do not install a separate `tkinter` pip package.

## Development Setup

Create and activate a virtual environment from PyCharm's terminal or any Windows terminal:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run from source:

```bat
python main.py
```

In PyCharm, set the project interpreter to `.venv\Scripts\python.exe`. Normal development does not require building the EXE.

## Project layout

```text
desktop_widgets/
  app.py, manager.py       # Startup and application coordination
  config.py, theme.py      # Saved preferences and theme palettes
  version.py, utils.py     # Version metadata and shared helpers
  widgets/                # BaseWidget, app folders, files, notes, media, stats
  ui/                     # Settings, focus view, menus, welcome and changelog
  services/               # Updates, monitor work areas, release notes, safe I/O
tests/                    # Unit and real-Tk regression checks
main.py                   # Source / PyInstaller entry point
build.py, release.bat      # Build and release tooling
```

`python main.py` and `python -m desktop_widgets` both launch the application.

## Appearance and displays

Settings → Appearance offers Graphite, Aurora, Rose Quartz, Ocean Mist and
Porcelain, with adjustable card corners. Existing palettes remain available.
The **+ and settings position** selector places the floating controls in any of
the four corners. Widgets reserve space for the Windows taskbar even with
auto-hide enabled. Large app and file folders scroll with the mouse wheel.
Settings pages are reused when switching tabs, and the Windows auto-start check
runs in the background.

Use a folder's **+** button to search installed desktop and Microsoft Store apps,
or **Browse files** to select executables and shortcuts. Game `.lnk` and `.url`
shortcuts retain their launch arguments and launcher behavior; dropped shortcuts
are kept in their original location. For games such as Call of Duty, use the
shortcut created by Steam, Battle.net or Xbox if the game's executable requires
its launcher. The picker prefers Start menu shortcuts so game icons are retained.
Right-click an app tile and choose **Change icon** to select an `.ico`, `.png`,
`.jpg`, `.webp`, or executable icon. Existing entries imported as raw executables
can be removed and added again using the original shortcut.

Focus view uses a stable rounded card: previous/next buttons or arrow keys switch
folders. The mouse wheel switches folders when all items fit; for larger folders
it scrolls the contents. Shift + wheel always switches folders.

Widgets can be dragged across displays, including displays left of or above the
primary monitor. Snapping and reflow use each monitor's work area, excluding its
taskbar. Saved negative positions survive restart; disconnected displays trigger
widget recovery to an available monitor. Mixed-DPI layouts still need testing on
physical hardware.

## Building the executable

Build the PyInstaller app:

```bat
python build.py
```

The expected executable is:

```text
dist\DesktopWidget\DesktopWidget.exe
```

The build disables UPX, bundles the app resources, writes Windows version metadata, and generates a SHA-256 checksum file.

## Versioning

The installed application needs a version identity; it is stored in
`desktop_widgets/version.py` as `VERSION`. The release command increments it
automatically. You do not need to edit that file or add changelog entries.

Default patch bump:

```bat
python -m desktop_widgets.version bump
```

Optional explicit bumps:

```bat
python -m desktop_widgets.version bump patch
python -m desktop_widgets.version bump minor
python -m desktop_widgets.version bump major
```

Patch bumps are numeric SemVer bumps, for example `1.0.9 -> 1.0.10`.

`release.bat` continues to call `build.py --release`. That release path bumps PATCH exactly once before building. If the build step fails, `build.py` restores the previous version so retrying the release does not accidentally bump twice for one failed build.

## Optional Code Signing

Unsigned builds work without any signing setup. To sign a build, configure one of these new signing-specific options before running `python build.py`:

```bat
set SIGN_CERTIFICATE=C:\path\to\certificate.pfx
set SIGN_CERTIFICATE_PASSWORD=certificate-password
```

Or use a certificate thumbprint available to Windows:

```bat
set SIGN_CERTIFICATE_THUMBPRINT=thumbprint
```

The build locates `signtool.exe` from common Windows SDK paths or `PATH`, signs with SHA-256, timestamps with RFC3161 timestamping, and verifies the signature. If signing is configured but fails, the build fails clearly. Certificate passwords are never hardcoded.

Windows Smart App Control and reputation systems may still warn on unsigned or newly signed builds until the publisher and binary establish reputation.

## Checksums and Updates

Builds generate `DesktopWidget.sha256` in this format:

```text
<sha256>  <filename>
```

Release ZIPs use the same format. The updater downloads the release ZIP to a staging directory, downloads the checksum asset, verifies the SHA-256 with `hashlib.sha256`, and installs only when the hashes match. Older releases without checksum assets are refused for automatic installation.

Release checks run in the background after startup. Nothing downloads or installs
until you accept the update prompt; declining keeps the current version running.
The update screen shows release notes, download progress, verification and
installation status without blocking the UI, and offers retry after failure.
Release builds bundle your versioned patch notes, and updates use the same notes
from the GitHub release description for the post-update changelog. Ordinary
development builds can fall back to Git commit subjects.

## Release Workflow

Normal release flow:

```bat
python build.py --prepare-release
```

This creates `release_notes/next.md` with an explicit heading, for example
`# DesktopWidget 1.0.47` when the current version is `1.0.46`. Edit the notes below
that heading. Preparing a draft does **not** change the app version, and running
prepare again never overwrites existing notes.

When ready, set `GITHUB_TOKEN` in your environment and run:

```bat
release.bat
```

The command checks that the heading matches the next version before building.
Those exact notes go into the executable and GitHub release, and the draft moves
to `release_notes/1.0.47.md` after publishing. The next prepare command then creates
a draft for `1.0.48`. There is no need to edit the Python version constant or its
legacy changelog dictionary.

For a minor release, use `python build.py --prepare-release --minor` followed by
`release.bat --minor`; similarly use `--major` for a major release. A mismatched
draft version stops the release. Failed uploads leave an unpublished GitHub draft;
rerunning the same release command retries that version without another bump.
The release becomes public only after its ZIP and checksum are uploaded.
Credentials must never be placed in the script.

## Validation

Useful checks during development:

```bat
python -m compileall desktop_widgets main.py build.py
python -m unittest discover -s tests -v
python -m pip check
python build.py
```
