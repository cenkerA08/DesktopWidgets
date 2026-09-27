@echo off
setlocal
cd /d "%~dp0"
if not defined GITHUB_TOKEN (
    echo Set GITHUB_TOKEN in your environment before releasing.
    exit /b 1
)
".venv\Scripts\python.exe" build.py --release %*
exit /b %errorlevel%
