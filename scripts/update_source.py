#!/usr/bin/env python3
"""Fetch latest releases from app repos and update apps.json."""

import json
import subprocess
import sys
from datetime import datetime, timezone

REPOS = {
    "xyz.aetherlab.tukacopic": {
        "repo": "PndaMan/TukacoPic",
        "asset_pattern": "TukacoPic.ipa",
    },
    "com.currents.app": {
        "repo": "PndaMan/Currents",
        "asset_pattern": "Currents.ipa",
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


def get_latest_release(repo, asset_pattern):
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

    return {
        "version": release["tag_name"],
        "date": release["published_at"][:10],
        "downloadURL": asset["browser_download_url"],
        "size": asset["size"],
    }


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
        info = get_latest_release(config["repo"], config["asset_pattern"])

        if not info:
            print(f"  No release found, skipping")
            continue

        # Check if this version already exists
        existing_versions = [v["version"] for v in app.get("versions", [])]
        if info["version"] in existing_versions:
            print(f"  Version {info['version']} already in source, skipping")
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
