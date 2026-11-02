"""Anonymous usage pings and occasional feedback prompts.

What leaves the machine:
  /ping      install_id (random UUID), app version, Windows version — once a day
  /feedback  install_id, app version, rating 1–5, optional text — only when sent

The server derives the country from the connection (Cloudflare does this) and
never stores the IP address. data["telemetry"]["enabled"] = False turns pings off.
"""
from __future__ import annotations
import os, platform, threading, uuid
from datetime import date, datetime

# Set this to your deployed Worker URL (see backend/README.md); empty disables
# all network calls. DESKTOPWIDGETS_TELEMETRY_URL overrides it for testing.
TELEMETRY_URL = "https://desktopwidgets-api.cenker-dw.workers.dev"

# When to ask for feedback: only after real use, then rarely.
FIRST_ASK_AFTER_DAYS = 14
FIRST_ASK_AFTER_UPDATES = 3
ASK_AGAIN_AFTER_DAYS = 90


def _url() -> str:
    return os.environ.get("DESKTOPWIDGETS_TELEMETRY_URL", TELEMETRY_URL).rstrip("/")


def state(data: dict) -> dict:
    """The persisted telemetry block, created on first use."""
    block = data.setdefault("telemetry", {})
    block.setdefault("enabled", True)
    block.setdefault("install_id", str(uuid.uuid4()))
    block.setdefault("first_run", date.today().isoformat())
    block.setdefault("updates_seen", 0)
    block.setdefault("last_version", "")
    block.setdefault("last_ping", "")
    block.setdefault("feedback_last_asked", "")
    block.setdefault("feedback_never", False)
    return block


def record_version(data: dict, version: str) -> bool:
    """Count updates; returns True when this launch is the first on a new version."""
    block = state(data)
    previous = block["last_version"]
    block["last_version"] = version
    if previous and previous != version:
        block["updates_seen"] += 1
        return True
    return False


def should_ask_feedback(data: dict, today: date | None = None) -> bool:
    block = state(data)
    if block["feedback_never"] or not _url():
        return False
    today = today or date.today()
    first_run = _parse(block["first_run"]) or today
    if (today - first_run).days < FIRST_ASK_AFTER_DAYS:
        return False
    if block["updates_seen"] < FIRST_ASK_AFTER_UPDATES:
        return False
    last = _parse(block["feedback_last_asked"])
    return last is None or (today - last).days >= ASK_AGAIN_AFTER_DAYS


def mark_asked(data: dict, never: bool = False) -> None:
    block = state(data)
    block["feedback_last_asked"] = date.today().isoformat()
    if never:
        block["feedback_never"] = True


def ping(data: dict, version: str) -> None:
    """Daily anonymous ping in the background. Silently does nothing offline."""
    block = state(data)
    today = date.today().isoformat()
    if not block["enabled"] or not _url() or block["last_ping"] == today:
        return
    payload = {"install_id": block["install_id"], "version": version,
               "os": f"Windows {platform.release()}"}

    def run():
        if _post("/ping", payload):
            block["last_ping"] = today
    threading.Thread(target=run, daemon=True, name="telemetry-ping").start()


def send_feedback(data: dict, version: str, rating: int, text: str, on_done=None) -> None:
    """Feedback is sent even with pings off: the user chose to submit it."""
    payload = {"install_id": state(data)["install_id"], "version": version,
               "rating": max(1, min(5, int(rating))), "text": text.strip()[:2000]}

    def run():
        ok = _post("/feedback", payload)
        if on_done:
            on_done(ok)
    threading.Thread(target=run, daemon=True, name="telemetry-feedback").start()


def _post(path: str, payload: dict) -> bool:
    url = _url()
    if not url:
        return False
    try:
        import requests
        response = requests.post(url + path, json=payload, timeout=6,
                                 headers={"User-Agent": "DesktopWidgets"})
        return response.ok
    except Exception:
        return False


def _parse(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
