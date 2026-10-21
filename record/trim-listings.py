#!/usr/bin/env python3
"""Trim a uv repository scenario's recorded listings to the versions a replay can reach.

usage: trim-listings.py <scenario-dir>...

A package locked at the same versions before and after the edit keeps only those versions' files, which are all a
replay reads of it. Any other package keeps the versions at or above the lowest one either lock holds, and a package
neither lock holds keeps every version. uv chose none of the dropped versions, so a replay that reaches for one fails
on the missing version rather than passing.
"""
import json
import pathlib
import re
import sys

from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename
from packaging.version import InvalidVersion, Version


def locked_versions(scenario):
    versions = {}
    for name in ("before", "after"):
        lock = scenario / name
        found = {}
        if lock.exists():
            for pkg, version in re.findall(r'^name = "([^"]+)"\nversion = "([^"]+)"', lock.read_text(), re.M):
                try:
                    found.setdefault(canonicalize_name(pkg), set()).add(Version(version))
                except InvalidVersion:
                    continue
        versions[name] = found
    return versions


def file_version(filename):
    try:
        if filename.endswith(".whl"):
            return parse_wheel_filename(filename)[1]
        return parse_sdist_filename(filename)[1]
    except Exception:
        return None


def trim(scenario):
    locked = locked_versions(scenario)
    for listing in sorted((scenario / "http").glob("*-listing-json")):
        name = canonicalize_name(listing.name[:-len("-listing-json")])
        before = locked["before"].get(name, set())
        after = locked["after"].get(name, set())
        if not before and not after:
            continue
        data = json.loads(listing.read_bytes())
        if before == after:
            keep = lambda v: v is None or v in before
        else:
            floor = min(before | after)
            keep = lambda v: v is None or v >= floor
        kept = [f for f in data.get("files", []) if keep(file_version(f["filename"]))]
        if len(kept) == len(data.get("files", [])):
            continue
        data["files"] = kept
        if "versions" in data:
            data["versions"] = [v for v in data["versions"] if keep(_version(v))]
        listing.write_text(json.dumps(data, separators=(",", ":")))


def _version(text):
    try:
        return Version(text)
    except InvalidVersion:
        return None


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        trim(pathlib.Path(arg))
