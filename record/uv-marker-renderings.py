#!/usr/bin/env python3
"""Record how a uv release renders PEP 508 markers.

usage: uv-marker-renderings.py <markers.txt> <out.tsv> [uv-release]

Each line of markers.txt is one marker. Every marker is declared as `leaf ; <marker>` in its own dependency group of
one probe project, locked against a one-package local index, and read back from the group's entry in
`[package.metadata.requires-dev]`. Each output line is `<marker>\t<uv's rendering>`, with `true` where uv drops the
marker. A marker uv rejects fails the lock, so check uv's output when it exits non-zero.
"""
import json
import pathlib
import re
import socket
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def main():
    markers_file, out_file = sys.argv[1], sys.argv[2]
    release = sys.argv[3] if len(sys.argv) > 3 else "0.13.4"
    markers = [line.rstrip("\n") for line in open(markers_file) if line.strip()]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "spec.json").write_text(json.dumps({"packages": [{"name": "leaf", "version": "1.0"}]}))
        subprocess.run([sys.executable, str(HERE / "mkindex.py"), str(tmp / "spec.json"), str(tmp / "idx")],
                       check=True, stdout=subprocess.DEVNULL)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                                  cwd=tmp / "idx", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            work = tmp / "work"
            work.mkdir()
            groups = "\n".join(f'g{i} = ["leaf ; {m}"]' for i, m in enumerate(markers))
            (work / "pyproject.toml").write_text(f"""[project]
name = "probe"
version = "0.1"
requires-python = ">=3.8"

[dependency-groups]
{groups}

[[tool.uv.index]]
url = "http://127.0.0.1:{port}/simple/"
default = true
""")
            subprocess.run(["uvx", f"uv@{release}", "lock", "--no-progress", "-q", "--no-cache"], cwd=work, check=True)
            lock = (work / "uv.lock").read_text()
        finally:
            server.terminate()
    rendered = {}
    for group, entry in re.findall(r'^(g\d+) = \[(\{[^\n]*\})\]$', lock, re.M):
        marker = re.search(r'marker = "([^"]*)"', entry)
        rendered[group] = marker.group(1) if marker else "true"
    with open(out_file, "w") as out:
        for i, m in enumerate(markers):
            out.write(f"{m}\t{rendered[f'g{i}']}\n")


if __name__ == "__main__":
    main()
