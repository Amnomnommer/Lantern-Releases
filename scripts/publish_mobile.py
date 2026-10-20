"""Publish verified, pre-signed bytes. Never sign, overwrite a release or run unreviewed code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
from verify_mobile import REPOSITORY, read_metadata, validate_bytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[1-9][0-9]{0,8}", args.version):
        raise ValueError("invalid version")
    version = int(args.version)
    tag = f"mobile-debug-v{version}"
    directory = Path("incoming") / tag
    metadata = read_metadata(directory / "release.json")
    apk = directory / "Lantern-mobile-debug.apk"
    validate_bytes(apk, metadata)
    report_path = Path("validation") / tag / "validation.json"
    report = json.loads(report_path.read_text())
    if report.get("passed") is not True or report.get("apk_sha256") != metadata["apk_sha256"]:
        raise ValueError("missing matching verification receipt")
    token = os.environ["GITHUB_TOKEN"]
    base = "https://api.github.com/repos/" + REPOSITORY

    def request(url, method="GET", data=None, content_type="application/json"):
        headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                   "Content-Type": content_type, "X-GitHub-Api-Version": "2022-11-28"}
        payload = json.dumps(data).encode() if isinstance(data, dict) else data
        req = urllib.request.Request(url, data=payload, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)

    try:
        existing = request(base + "/releases/tags/" + tag)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        existing = None
    if existing:
        assets = [a for a in existing.get("assets", []) if a.get("name") == apk.name]
        if existing.get("draft") is False and len(assets) == 1 and assets[0].get("digest") == "sha256:" + metadata["apk_sha256"]:
            print("Identical release already published; no write needed.")
            return
        raise ValueError("release exists; refusing overwrite or incomplete-draft reuse")
    release = request(base + "/releases", "POST", {
        "tag_name": tag, "target_commitish": os.environ["GITHUB_SHA"],
        "name": "Lantern Mobile " + metadata["version_name"], "draft": True,
        "prerelease": True, "body": metadata["notes"] + "\n\nAPK SHA-256: `" + metadata["apk_sha256"] + "`\nSigning certificate SHA-256: `" + metadata["certificate_sha256"] + "`\n\nCandidate app. Android requires owner confirmation for every installation. Workstation transport remains disabled."})
    release_id = int(release["id"])
    assets = [apk, directory / "release.json", report_path,
              report_path.parent / "SHA256SUMS", report_path.parent / "signature-verification.txt"]
    for path in assets:
        content = path.read_bytes()
        url = f"https://uploads.github.com/repos/{REPOSITORY}/releases/{release_id}/assets?name=" + urllib.parse.quote(path.name)
        asset = request(url, "POST", content, "application/vnd.android.package-archive" if path.suffix == ".apk" else "application/octet-stream")
        if asset.get("size") != len(content) or asset.get("digest") != "sha256:" + hashlib.sha256(content).hexdigest():
            raise ValueError("uploaded bytes do not match; release remains draft")
    request(base + "/releases/" + str(release_id), "PATCH", {"draft": False})
    print("Published https://github.com/" + REPOSITORY + "/releases/tag/" + tag)


if __name__ == "__main__":
    main()
