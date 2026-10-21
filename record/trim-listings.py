#!/usr/bin/env python3
"""Trim a uv repository scenario's recorded listings to the versions a replay can reach.

usage: trim-listings.py <scenario-dir>...

A listing keeps the files of every version at or above the lowest version of that package in the scenario's before
or after lock, and every version of a package neither lock holds. uv chose none of the dropped versions, so a replay
that reaches for one fails on the missing version rather than passing.
"""
import json
import pathlib
import re
import sys

from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename
from packaging.version import InvalidVersion, Version


def locked_versions(scenario):
    lowest = {}
    for name in ("before", "after"):
        lock = scenario / name
        if not lock.exists():
            continue
        for pkg, version in re.findall(r'^name = "([^"]+)"\nversion = "([^"]+)"', lock.read_text(), re.M):
            try:
                v = Version(version)
            except InvalidVersion:
                continue
            key = canonicalize_name(pkg)
            lowest[key] = min(lowest.get(key, v), v)
    return lowest


def file_version(filename):
    try:
        if filename.endswith(".whl"):
            return parse_wheel_filename(filename)[1]
        return parse_sdist_filename(filename)[1]
    except Exception:
        return None


def trim(scenario):
    lowest = locked_versions(scenario)
    for listing in sorted((scenario / "http").glob("*-listing-json")):
        name = canonicalize_name(listing.name[:-len("-listing-json")])
        floor = lowest.get(name)
        if floor is None:
            continue
        data = json.loads(listing.read_bytes())
        kept = [f for f in data.get("files", []) if (file_version(f["filename"]) or floor) >= floor]
        if len(kept) == len(data.get("files", [])):
            continue
        data["files"] = kept
        if "versions" in data:
            data["versions"] = [v for v in data["versions"] if _ge(v, floor)]
        listing.write_text(json.dumps(data, separators=(",", ":")))


def _ge(version, floor):
    try:
        return Version(version) >= floor
    except InvalidVersion:
        return True


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        trim(pathlib.Path(arg))
