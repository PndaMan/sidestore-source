#!/usr/bin/env python3
"""Fetch latest releases from app repos and update apps.json."""

import json
import plistlib
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPOS = {
    "xyz.aetherlab.tukacopic": {
        "repo": "PndaMan/TukacoPic",
        "asset_pattern": "TukacoPic.ipa",
    },
    "com.aidanmcconnon.currents": {
        "repo": "PndaMan/Currents",
        "asset_pattern": "Currents.ipa",
        # List the app's own version and build (1.3.0, 306) instead of the tag.
        "version_from_ipa": True,
    },
}


def gh_api(endpoint):
    """Call GitHub API via gh CLI."""
    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  gh api {endpoint} failed: {result.stderr.strip()}")
        return None
    return json.loads(result.stdout)


def ipa_version(repo, tag, asset_name):
    """CFBundleShortVersionString and CFBundleVersion of the app inside a release IPA."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            ["gh", "release", "download", tag, "-R", repo, "-p", asset_name, "-D", tmp],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  Download of {asset_name} failed: {result.stderr.strip()}")
            return None
        with zipfile.ZipFile(Path(tmp) / asset_name) as ipa:
            name = next((n for n in ipa.namelist()
                         if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", n)), None)
            if not name:
                print(f"  No app Info.plist in {asset_name}")
                return None
            plist = plistlib.loads(ipa.read(name))
    return plist.get("CFBundleShortVersionString"), plist.get("CFBundleVersion")


def get_latest_release(repo, asset_pattern, version_from_ipa=False):
    """Get the latest release info for a repo."""
    release = gh_api(f"repos/{repo}/releases/latest")
    if not release:
        return None

    asset = next(
        (a for a in release.get("assets", []) if a["name"] == asset_pattern),
        None,
    )
    if not asset:
        print(f"  No asset matching '{asset_pattern}' in latest release")
        return None

    info = {
        "version": release["tag_name"],
        "date": release["published_at"][:10],
        "downloadURL": asset["browser_download_url"],
        "size": asset["size"],
    }
    if version_from_ipa:
        found = ipa_version(repo, release["tag_name"], asset_pattern)
        if not found or not found[0]:
            return None
        info["version"] = found[0]
        if found[1]:
            info["buildVersion"] = str(found[1])
    return info


def main():
    with open("apps.json") as f:
        source = json.load(f)

    changed = False
    for app in source["apps"]:
        bid = app["bundleIdentifier"]
        if bid not in REPOS:
            continue

        config = REPOS[bid]
        print(f"Checking {app['name']} ({config['repo']})...")
        info = get_latest_release(config["repo"], config["asset_pattern"],
                                  config.get("version_from_ipa", False))

        if not info:
            print(f"  No release found, skipping")
            continue

        # Each release has its own download URL; versions from the IPA can repeat
        # across builds, so match on the URL.
        existing_urls = [v["downloadURL"] for v in app.get("versions", [])]
        if info["downloadURL"] in existing_urls:
            print(f"  {info['downloadURL']} already in source, skipping")
            continue

        print(f"  Adding version {info['version']}")
        # Prepend new version (latest first)
        app.setdefault("versions", []).insert(0, info)
        # Keep only last 10 versions
        app["versions"] = app["versions"][:10]
        changed = True

    if changed:
        with open("apps.json", "w") as f:
            json.dump(source, f, indent=2)
            f.write("\n")
        print("apps.json updated")
    else:
        print("No changes needed")

    return 0 if changed else 0  # Always succeed


if __name__ == "__main__":
    sys.exit(main())
