"""Validate pre-signed APKs using Android's official verifier; never hold a signing key."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

REPOSITORY = "Amnomnommer/Lantern-Releases"
PACKAGE = "org.projectlantern.mobile.debug"
FIELDS = {"format_version", "channel", "version_code", "version_name", "application_id",
          "apk_sha256", "apk_bytes", "certificate_sha256", "source_revision", "notes"}
HEX = re.compile(r"[0-9a-f]{64}")


def no_duplicates(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate JSON field")
        data[key] = value
    return data


def read_metadata(path):
    if path.is_symlink() or path.stat().st_size > 8192:
        raise ValueError("invalid metadata file")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise ValueError("unexpected metadata fields")
    if data["format_version"] != 1 or type(data["format_version"]) is not int:
        raise ValueError("invalid format")
    if data["channel"] != "mobile-debug" or data["application_id"] != PACKAGE:
        raise ValueError("invalid release channel/package")
    if type(data["version_code"]) is not int or not 1 <= data["version_code"] < 1_000_000_000:
        raise ValueError("invalid version code")
    if type(data["apk_bytes"]) is not int or not 1 <= data["apk_bytes"] <= 20_000_000:
        raise ValueError("invalid artifact size")
    for key in ("apk_sha256", "certificate_sha256"):
        if not isinstance(data[key], str) or not HEX.fullmatch(data[key]):
            raise ValueError("invalid digest")
    if not isinstance(data["source_revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", data["source_revision"]):
        raise ValueError("invalid source revision")
    if not isinstance(data["version_name"], str) or not re.fullmatch(r"[A-Za-z0-9.+_-]{1,80}", data["version_name"]):
        raise ValueError("invalid version name")
    if not isinstance(data["notes"], str) or not 1 <= len(data["notes"]) <= 2000:
        raise ValueError("invalid release notes")
    return data


def select_version(root, requested=""):
    if requested:
        if not re.fullmatch(r"[1-9][0-9]{0,8}", requested):
            raise ValueError("invalid requested version")
        return int(requested)
    versions = []
    for path in (root / "incoming").glob("mobile-debug-v*/release.json"):
        match = re.fullmatch(r"mobile-debug-v([1-9][0-9]{0,8})", path.parent.name)
        if match:
            versions.append(int(match[1]))
    return max(versions) if versions else None


def validate_bytes(path, metadata):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != metadata["apk_bytes"]:
        raise ValueError("artifact size/file mismatch")
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["apk_sha256"]:
        raise ValueError("artifact hash mismatch")


def verify(root, version, sdk):
    directory = root / "incoming" / f"mobile-debug-v{version}"
    if directory.is_symlink():
        raise ValueError("symlink release directory")
    metadata = read_metadata(directory / "release.json")
    if metadata["version_code"] != version:
        raise ValueError("version directory mismatch")
    pin = (root / "channels/mobile-signing-certificate-sha256.txt").read_text().strip()
    if not HEX.fullmatch(pin) or pin != metadata["certificate_sha256"]:
        raise ValueError("unrecognized signing certificate")
    apk = directory / "Lantern-mobile-debug.apk"
    validate_bytes(apk, metadata)
    signer = sdk / "build-tools/35.0.0/apksigner"
    result = subprocess.run([str(signer), "verify", "--verbose", "--print-certs", str(apk)],
                            capture_output=True, text=True, timeout=60, check=True)
    certificates = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})$", result.stdout, re.MULTILINE)
    if certificates != [pin] or "Verified using v2 scheme (APK Signature Scheme v2): true" not in result.stdout:
        raise ValueError("APK signature identity/v2 verification failed")
    analyzer = sdk / "cmdline-tools/latest/bin/apkanalyzer"
    manifest = subprocess.run([str(analyzer), "manifest", "print", str(apk)],
                              capture_output=True, text=True, timeout=60, check=True).stdout
    xml = ET.fromstring(manifest)
    a = "{http://schemas.android.com/apk/res/android}"
    if (xml.get("package") != PACKAGE or xml.get(a + "versionCode") != str(version)
            or xml.get(a + "versionName") != metadata["version_name"]):
        raise ValueError("packaged version/package mismatch")
    permissions = [node.get(a + "name") for node in xml if node.tag.startswith("uses-permission")]
    if sorted(permissions) != sorted(["android.permission.INTERNET", "android.permission.REQUEST_INSTALL_PACKAGES"]):
        raise ValueError("unexpected Android permission")
    app = xml.find("application")
    if app is None or app.get(a + "allowBackup") != "false" or app.get(a + "usesCleartextTraffic") != "false" or app.findall("service"):
        raise ValueError("unexpected app boundary")
    receivers = app.findall("receiver")
    if len(receivers) != 1 or receivers[0].get(a + "exported") != "false":
        raise ValueError("unexpected installer callback exposure")
    output = root / "validation" / f"mobile-debug-v{version}"
    output.mkdir(parents=True, exist_ok=True)
    report = {"passed": True, "version_code": version, "apk_sha256": metadata["apk_sha256"],
              "certificate_sha256": pin, "official_signature_verifier": True,
              "same_signing_identity_required_for_future_updates": True,
              "android_confirmation_required": True, "phone_update_accepted": False,
              "requested_permissions": permissions, "remote_workstation_enabled": False}
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "SHA256SUMS").write_text(metadata["apk_sha256"] + "  Lantern-mobile-debug.apk\n")
    (output / "signature-verification.txt").write_text(result.stdout)
    (output / "packaged-manifest.xml").write_text(manifest)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--version", default="")
    args = parser.parse_args()
    version = select_version(args.root, args.version)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as stream:
            stream.write(f"has_release={'true' if version else 'false'}\nversion={version or ''}\n")
    if version is None:
        print("No incoming mobile APK; infrastructure validation only.")
        return
    print(json.dumps(verify(args.root, version, Path(os.environ["ANDROID_HOME"])), indent=2))


if __name__ == "__main__":
    main()
