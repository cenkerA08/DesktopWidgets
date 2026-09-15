from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from safe_io import (
    atomic_write_json,
    parse_sha256_text,
    safe_extract_zip,
    sha256_file,
    verify_sha256,
)
from version import bump_semver, compare_versions


class VersionTests(unittest.TestCase):
    def test_patch_bumps_are_numeric(self) -> None:
        self.assertEqual(bump_semver("1.0.0"), "1.0.1")
        self.assertEqual(bump_semver("1.0.9"), "1.0.10")
        self.assertEqual(bump_semver("1.9.9"), "1.9.10")
        self.assertEqual(bump_semver("9.9.99"), "9.9.100")

    def test_version_comparison_is_numeric(self) -> None:
        self.assertGreater(compare_versions("1.0.10", "1.0.9"), 0)
        self.assertGreater(compare_versions("2.0.0", "1.99.99"), 0)


class SafetyTests(unittest.TestCase):
    def test_checksum_format_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "DesktopWidget_v1.0.1.zip"
            payload.write_bytes(b"payload")
            digest = sha256_file(payload)
            text = f"{digest}  {payload.name}\n"
            self.assertEqual(parse_sha256_text(text, payload.name), digest)
            self.assertEqual(verify_sha256(payload, digest), digest)

    def test_safe_zip_extract_accepts_normal_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "ok.zip"
            dest = root / "out"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("DesktopWidget/file.txt", "ok")
            safe_extract_zip(archive, dest)
            self.assertEqual((dest / "DesktopWidget" / "file.txt").read_text(), "ok")

    def test_safe_zip_extract_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../evil.exe", "bad")
            with self.assertRaises(ValueError):
                safe_extract_zip(archive, root / "out")

    def test_atomic_json_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            atomic_write_json(path, {"version": 1, "items": ["a"]})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["items"], ["a"])


if __name__ == "__main__":
    unittest.main()
