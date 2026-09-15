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

## Building

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

The canonical application version is stored in `version.py` as `VERSION`.

Default patch bump:

```bat
python version.py bump
```

Optional explicit bumps:

```bat
python version.py bump patch
python version.py bump minor
python version.py bump major
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

## Release Workflow

Normal release flow:

```bat
release.bat
```

The existing release authentication behavior is preserved. Do not commit or print credentials. The build/release script uploads the release ZIP and checksum asset using the existing GitHub token environment used by the current workflow.

## Validation

Useful checks during development:

```bat
python -m compileall .
python -m unittest discover
python -m pip check
python build.py
```
