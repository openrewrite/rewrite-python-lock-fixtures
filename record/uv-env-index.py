#!/usr/bin/env python3
"""Print the first registry a uv.lock resolves from that is neither pypi.org nor declared in the manifest.

usage: uv-env-index.py <pyproject.toml> <uv.lock>
Such a registry comes from its author's own uv configuration, which a replay elsewhere does not have. Prints
nothing when every registry is accounted for.
"""
import re
import sys

manifest = open(sys.argv[1]).read()
lock = open(sys.argv[2]).read()
declared = {u.rstrip("/") for u in re.findall(r'url\s*=\s*"([^"]+)"', manifest)}
for registry in sorted(set(re.findall(r'source = \{ registry = "([^"]+)" \}', lock))):
    if registry.rstrip("/") != "https://pypi.org/simple" and registry.rstrip("/") not in declared:
        print(registry)
        break
