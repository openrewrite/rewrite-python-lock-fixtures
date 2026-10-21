#!/usr/bin/env python3
"""Download (manifest, lock) pairs listed in a candidates file into a corpus directory.

candidates.txt lines: "<owner>/<repo>\t<path-to-lock>"; the manifest is looked up next to the lock.
Each case lands in <corpus>/<manager>/<owner>__<repo>__<dir-slug>/ with the two files plus META.json
recording the repository, commit SHA and paths, so a case is reproducible.
Only exact lock file names are accepted (uv.lock, Pipfile.lock, poetry.lock, pdm.lock).
"""
import base64
import json
import os
import subprocess
import sys
import time

MANIFEST = {"uv.lock": "pyproject.toml", "Pipfile.lock": "Pipfile", "poetry.lock": "pyproject.toml", "pdm.lock": "pyproject.toml"}
MANAGER = {"uv.lock": "uv", "Pipfile.lock": "pipenv", "poetry.lock": "poetry", "pdm.lock": "pdm"}


def gh(args):
    for attempt in range(3):
        r = subprocess.run(["gh", "api"] + args, capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
        if "rate limit" in r.stderr.lower():
            time.sleep(30)
            continue
        return None
    return None


def main(candidates, corpus, limit_per_manager):
    seen = set()
    counts = {}
    for line in open(candidates):
        line = line.rstrip("\n")
        if not line or "\t" not in line:
            continue
        repo, path = line.split("\t", 1)
        lock_name = os.path.basename(path)
        if lock_name not in MANIFEST:
            continue
        manager = MANAGER[lock_name]
        if counts.get(manager, 0) >= limit_per_manager:
            continue
        d = os.path.dirname(path)
        key = (repo, d)
        if key in seen:
            continue
        seen.add(key)
        info = gh([f"repos/{repo}"])
        if not info:
            continue
        info = json.loads(info)
        branch = info["default_branch"]
        ref = gh([f"repos/{repo}/commits/{branch}", "--jq", ".sha"])
        if not ref:
            continue
        sha = ref.strip()
        slug = (repo.replace("/", "__") + ("__" + d.replace("/", "_") if d else ""))
        out = os.path.join(corpus, manager, slug)
        files = {}
        for name in (lock_name, MANIFEST[lock_name]):
            p = (d + "/" if d else "") + name
            content = gh([f"repos/{repo}/contents/{p}?ref={sha}", "--jq", ".content"])
            if not content:
                files = None
                break
            files[name] = base64.b64decode(content.strip().replace("\n", ""))
        if not files:
            print(f"skip {repo} {d}: missing manifest or lock", file=sys.stderr)
            continue
        os.makedirs(out, exist_ok=True)
        for name, data in files.items():
            with open(os.path.join(out, name), "wb") as f:
                f.write(data)
        with open(os.path.join(out, "META.json"), "w") as f:
            json.dump({"repo": repo, "sha": sha, "dir": d, "lock": lock_name}, f)
        counts[manager] = counts.get(manager, 0) + 1
        print(f"{manager}\t{repo}\t{d}\t{sha[:10]}")
    print(counts, file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 60)
