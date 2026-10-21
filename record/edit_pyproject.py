#!/usr/bin/env python3
"""Produce an edited pyproject.toml for a corpus case (stdout) and describe the edit (stderr).

upgrade: pick the first [project] dependency that is a plain registry requirement (no extras, no marker,
no [tool.uv.sources] entry), whose locked version is not the newest PyPI release admitted by the lock's
requires-python, and pin it with "==<newest>". The replacement is a textual edit of that one array element.
removal: drop the last [project] dependency element (textually) when there are at least two.
Exit 1 when no suitable edit exists.
"""
import json
import re
import sys
import tomllib
import urllib.request


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def locked_versions(lock_text):
    versions = {}
    for block in lock_text.split("\n[[package]]\n")[1:]:
        head = block.split("\n\n")[0]
        n = re.search(r'^name = "([^"]+)"', head, re.M)
        v = re.search(r'^version = "([^"]+)"', head, re.M)
        if n and v:
            versions.setdefault(n.group(1), []).append(v.group(1))
    return versions


def pypi_latest(name):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=30) as r:
        data = json.load(r)
    rel = data["releases"]
    cands = []
    for ver, files in rel.items():
        if not files or all(f.get("yanked") for f in files):
            continue
        if re.search(r"(a|b|rc|dev)\d*$", ver):
            continue
        if not re.match(r"^\d+(\.\d+)*$", ver):
            continue
        rp = next((f.get("requires_python") for f in files if f.get("requires_python")), None)
        cands.append((tuple(int(x) for x in ver.split(".")), ver, rp))
    cands.sort()
    return cands


def admits(requires_python, lower):
    if not requires_python or lower is None:
        return True
    for clause in requires_python.split(","):
        clause = clause.strip().replace(" ", "")
        m = re.match(r"^(>=|>|<=|<|==|!=|~=)(\d+(?:\.\d+)*)(\.\*)?$", clause)
        if not m:
            return True
        op, ver = m.group(1), tuple(int(x) for x in m.group(2).split("."))
        if op == ">=" and lower < ver:
            return False
        if op == ">" and lower <= ver:
            return False
    return True


def main():
    kind, pyproject_path, lock_path = sys.argv[1:4]
    text = open(pyproject_path).read()
    data = tomllib.loads(text)
    deps = data.get("project", {}).get("dependencies", [])
    if not deps:
        print("no [project] dependencies", file=sys.stderr)
        sys.exit(1)
    m = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.M | re.S)
    if not m:
        m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if not m:
        print("cannot locate dependencies array textually", file=sys.stderr)
        sys.exit(1)
    array_text = m.group(0)
    sources = set(canonical(k) for k in data.get("tool", {}).get("uv", {}).get("sources", {}))
    lock_text = open(lock_path).read()
    locked = locked_versions(lock_text)
    rp = re.search(r'^requires-python = "([^"]+)"', lock_text, re.M)
    lower = None
    if rp:
        lm = re.search(r">=\s*(\d+(?:\.\d+)*)", rp.group(1))
        if lm:
            lower = tuple(int(x) for x in lm.group(1).split("."))
    if kind in ("add-leaf", "add-closure"):
        spec = {"add-leaf": "iniconfig>=2.0", "add-closure": "python-dateutil>=2.9"}[kind]
        name = canonical(spec.split(">=")[0])
        if name in locked:
            print(f"{name} already locked", file=sys.stderr)
            sys.exit(1)
        elems = re.findall(r'^(\s*)"[^"]*",?\s*(?:#.*)?$', array_text, re.M)
        if elems:
            indent = elems[-1]
            body = array_text[:array_text.rfind("]")].rstrip()
            if not body.endswith(","):
                body += ","
            new_array = body + f'\n{indent}"{spec}",\n]'
        else:
            inner = array_text[array_text.index("[") + 1:array_text.rfind("]")].strip()
            new_array = "[" + (inner + ", " if inner else "") + f'"{spec}"]'
        print(text.replace(array_text, new_array), end="")
        print(f"added {spec}", file=sys.stderr)
        return
    if kind == "transitive":
        direct = set()
        for dep in deps:
            dm = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", dep)
            if dm:
                direct.add(canonical(dm.group(1)))
        uv_table = data.get("tool", {}).get("uv", {})
        if "constraint-dependencies" in uv_table:
            print("constraint-dependencies already declared", file=sys.stderr)
            sys.exit(1)
        for name in sorted(locked):
            if name in direct or name in sources or len(locked[name]) != 1:
                continue
            try:
                cands = pypi_latest(name)
            except Exception as e:  # noqa: BLE001
                continue
            cands = [c for c in cands if admits(c[2], lower)]
            if not cands or cands[-1][1] == locked[name][0]:
                continue
            newest = cands[-1][1]
            line = f'constraint-dependencies = ["{name}>={newest}"]'
            hm = re.search(r"^\[tool\.uv\]\s*$", text, re.M)
            if hm:
                out = text[:hm.end()] + "\n" + line + text[hm.end():]
            else:
                out = text.rstrip("\n") + "\n\n[tool.uv]\n" + line + "\n"
            print(out, end="")
            print(f"transitive {name} {locked[name][0]} -> >={newest}", file=sys.stderr)
            return
        print("no upgradable transitive package", file=sys.stderr)
        sys.exit(1)
    if kind == "removal":
        elems = re.findall(r'^\s*"[^"]*",?\s*(?:#.*)?$', array_text, re.M)
        if len(elems) < 2:
            print("fewer than two dependency lines", file=sys.stderr)
            sys.exit(1)
        last = elems[-1]
        idx = array_text.rfind(last)
        new_array = array_text[:idx] + array_text[idx + len(last):].lstrip("\n")
        new_array = new_array.rstrip()
        print(text.replace(array_text, new_array if new_array.endswith("]") else new_array + "\n]"), end="")
        print(f"removed {last.strip()}", file=sys.stderr)
        return
    for dep in deps:
        dm = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([^;]*?)\s*(;.*)?$", dep)
        if not dm or dm.group(2) or dm.group(4):
            continue
        name = canonical(dm.group(1))
        if name in sources or name not in locked or len(locked[name]) != 1:
            continue
        try:
            cands = pypi_latest(name)
        except Exception as e:  # noqa: BLE001
            print(f"pypi lookup failed for {name}: {e}", file=sys.stderr)
            continue
        cands = [c for c in cands if admits(c[2], lower)]
        if not cands:
            continue
        newest = cands[-1][1]
        if newest == locked[name][0]:
            continue
        quoted = '"' + dep + '"'
        if quoted not in array_text:
            continue
        new_array = array_text.replace(quoted, f'"{dm.group(1)}=={newest}"', 1)
        print(text.replace(array_text, new_array), end="")
        print(f"{name} {locked[name][0]} -> =={newest} (was '{dep}')", file=sys.stderr)
        return
    print("no upgradable plain registry dependency", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
