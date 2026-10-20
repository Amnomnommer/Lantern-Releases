import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from verify_mobile import read_metadata, select_version, validate_bytes


class ReleaseContractTests(unittest.TestCase):
    def metadata(self):
        return {"format_version": 1, "channel": "mobile-debug", "version_code": 3,
                "version_name": "0.1.2-public", "application_id": "org.projectlantern.mobile.debug",
                "apk_sha256": hashlib.sha256(b"fixture").hexdigest(), "apk_bytes": 7,
                "certificate_sha256": "a" * 64, "source_revision": "b" * 40,
                "notes": "Synthetic release metadata, no APK or private material."}

    def test_valid_metadata_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "release.json"
            path.write_text(json.dumps(self.metadata()))
            self.assertEqual(read_metadata(path), self.metadata())

    def test_unknown_fields_wrong_identity_and_boolean_counts_refuse(self):
        for edits in ({"command": "run"}, {"version_code": True}, {"apk_bytes": True},
                      {"channel": "workstation"}, {"application_id": "other.app"},
                      {"apk_sha256": "wrong"}, {"source_revision": "not-a-sha"}):
            with self.subTest(edits=edits), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "release.json"
                path.write_text(json.dumps(self.metadata() | edits))
                with self.assertRaises(ValueError):
                    read_metadata(path)

    def test_duplicate_fields_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "release.json"
            path.write_text('{"version_code":3,"version_code":4}')
            with self.assertRaises(ValueError):
                read_metadata(path)

    def test_changed_bytes_refuse_even_when_length_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.apk"
            path.write_bytes(b"fixture")
            validate_bytes(path, self.metadata())
            path.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                validate_bytes(path, self.metadata())

    def test_missing_empty_and_symlink_artifact_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.apk"
            path.write_bytes(b"")
            with self.assertRaises(ValueError):
                validate_bytes(path, self.metadata())
            link = Path(tmp) / "link.apk"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                validate_bytes(link, self.metadata())

    def test_version_selector_rejects_shell_path_or_leading_zero_input(self):
        for value in ("../3", "3;pwd", "03", "-1", "true", "1000000000"):
            with self.assertRaises(ValueError):
                select_version(Path("."), value)

    def test_empty_incoming_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(select_version(Path(tmp)))


if __name__ == "__main__":
    unittest.main()
