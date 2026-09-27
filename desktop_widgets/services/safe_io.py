"""Small, reusable helpers for safe file and archive operations."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text through a same-directory temporary file and os.replace()."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding=encoding,
            dir=target.parent,
            delete=False,
            newline="",
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, target)
        tmp_name = None
    finally:
        if tmp_name:
            try:
                os.remove(tmp_name)
            except OSError:
                pass


def atomic_write_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    text = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
    atomic_write_text(path, text, encoding="utf-8")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_sha256_file(artifact: str | Path, checksum_path: str | Path | None = None) -> Path:
    artifact_path = Path(artifact)
    target = Path(checksum_path) if checksum_path else artifact_path.with_name("DesktopWidget.sha256")
    digest = sha256_file(artifact_path)
    atomic_write_text(target, f"{digest}  {artifact_path.name}\n", encoding="utf-8")
    return target


def parse_sha256_text(text: str, expected_filename: str | None = None) -> str:
    """Parse '<sha256>  <filename>' checksum text and return the digest."""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 1:
            continue
        digest = parts[0].lower()
        filename = parts[-1] if len(parts) > 1 else ""
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid SHA-256 checksum format.")
        if expected_filename and filename and Path(filename).name != expected_filename:
            continue
        return digest
    raise ValueError("No matching SHA-256 checksum found.")


def verify_sha256(path: str | Path, expected_sha256: str) -> str:
    actual = sha256_file(path)
    if actual.lower() != expected_sha256.lower():
        raise ValueError(f"Checksum mismatch: expected {expected_sha256}, got {actual}.")
    return actual


def _safe_zip_target(root: Path, member_name: str) -> Path:
    if not member_name or member_name.endswith(":"):
        raise ValueError(f"Unsafe ZIP entry: {member_name!r}")
    raw = Path(member_name)
    if raw.is_absolute() or raw.drive:
        raise ValueError(f"Unsafe ZIP entry: {member_name!r}")
    target = (root / raw).resolve()
    root_resolved = root.resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ValueError(f"Unsafe ZIP entry: {member_name!r}")
    return target


def safe_extract_zip(zip_path: str | Path, destination: str | Path) -> None:
    """Extract a ZIP after rejecting entries that escape destination."""
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            target = _safe_zip_target(dest, info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info, "r") as src, open(target, "wb") as out:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    out.write(chunk)
