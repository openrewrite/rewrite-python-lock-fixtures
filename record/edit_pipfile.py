#!/usr/bin/env python3
import json, re, sys, tomllib, urllib.request, hashlib
pipfile, lock = sys.argv[1], sys.argv[2]
kind = sys.argv[3] if len(sys.argv) > 3 else "upgrade"
text = open(pipfile).read(); pf = tomllib.loads(text); lk = json.load(open(lock))
NON = {"source", "requires", "scripts", "pipfile", "pipenv"}
canon = lambda n: re.sub(r"[-_.]+", "-", n).lower()
def h(canonical):
    sources = pf.get("source") or lk["_meta"].get("sources") or [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True}]
    data = {"_meta": {"sources": sources, "requires": pf.get("requires", {})}, "default": pf.get("packages", {}), "develop": pf.get("dev-packages", {})}
    for k, v in pf.items():
        if k not in NON and k not in ("packages", "dev-packages"): data[k] = v
    if canonical:
        for k in list(data):
            if k != "_meta": data[k] = {canon(a): b for a, b in data[k].items()}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
rec = lk["_meta"]["hash"]["sha256"]
if rec not in (h(False), h(True)):
    print("stale lock", file=sys.stderr); sys.exit(1)
if pf.get("source") and any("pypi.org" not in s.get("url", "") for s in pf["source"]):
    print("non-pypi source", file=sys.stderr); sys.exit(1)
default = lk.get("default", {})
if kind == "removal":
    names = [n for n, v in pf.get("packages", {}).items() if isinstance(v, str)]
    if len(names) < 2:
        print("nothing removable", file=sys.stderr); sys.exit(1)
    name = names[-1]
    pattern = re.compile(r'^' + re.escape(name) + r'\s*=\s*"[^"]*"\s*\n', re.M)
    if not pattern.search(text):
        print("nothing removable", file=sys.stderr); sys.exit(1)
    sys.stdout.write(pattern.sub("", text, count=1))
    print(f"removed {canon(name)}", file=sys.stderr); sys.exit(0)
if kind == "add-leaf":
    locked_names = {canon(k) for cat in lk if cat != "_meta" for k in lk[cat]}
    leaf = next((n for n in ("six", "idna", "certifi", "iniconfig") if n not in locked_names and n not in {canon(k) for k in pf.get("packages", {})}), None)
    m = re.search(r'^\[packages\]\s*\n', text, re.M)
    if leaf is None or m is None:
        print("no leaf to add", file=sys.stderr); sys.exit(1)
    sys.stdout.write(text[:m.end()] + f'{leaf} = "*"\n' + text[m.end():])
    print(f"added {leaf}", file=sys.stderr); sys.exit(0)
for name, spec in pf.get("packages", {}).items():
    if not isinstance(spec, str): continue
    key = next((k for k in default if canon(k) == canon(name)), None)
    if key is None or "version" not in default[key]: continue
    locked = default[key]["version"].lstrip("=")
    try:
        data = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{canon(name)}/json", timeout=30))
    except Exception as e:
        continue
    py = (pf.get("requires", {}) or {}).get("python_version")
    lower = tuple(int(x) for x in py.split(".")) if py else None
    cands = []
    for ver, files in data["releases"].items():
        if not files or all(f.get("yanked") for f in files) or not re.match(r"^\d+(\.\d+)*$", ver): continue
        rp = next((f.get("requires_python") for f in files if f.get("requires_python")), None)
        ok = True
        if rp and lower:
            for clause in rp.split(","):
                m = re.match(r"^\s*(>=|>)\s*(\d+(?:\.\d+)*)\s*$", clause)
                if m and lower < tuple(int(x) for x in m.group(2).split(".")): ok = False
        if ok: cands.append((tuple(int(x) for x in ver.split(".")), ver))
    cands.sort()
    if not cands or cands[-1][1] == locked: continue
    newest = cands[-1][1]
    pattern = re.compile(r'^(' + re.escape(name) + r'\s*=\s*)"[^"]*"', re.M)
    if not pattern.search(text): continue
    sys.stdout.write(pattern.sub(lambda m: m.group(1) + f'"=={newest}"', text, count=1))
    print(f"{canon(name)} {locked} -> =={newest}", file=sys.stderr); sys.exit(0)
print("no upgradable entry", file=sys.stderr); sys.exit(1)
