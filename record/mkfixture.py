#!/usr/bin/env python3
"""Turn a recorded local-index scenario into an offline test fixture directory.

Rewrites the throwaway http://127.0.0.1:PORT host to https://index.example in the manifest and both locks,
copies the simple-index pages and .metadata sidecars the engine fetched into http/, and prints the
RoutedHttp.route(...) lines for the test.
"""
import os, re, shutil, sys

scen, out, fixture_name = sys.argv[1], sys.argv[2], sys.argv[3]
port = open(os.path.join(scen, "port")).read().strip()
host = f"http://127.0.0.1:{port}"
os.makedirs(os.path.join(out, "http"), exist_ok=True)

def sub(src, dst):
    text = open(src).read().replace(host, "https://index.example")
    open(dst, "w").write(text)

sub(os.path.join(scen, "work", "pyproject.after.toml"), os.path.join(out, "pyproject.toml"))
sub(os.path.join(scen, "uv.lock.before"), os.path.join(out, "uv.lock.before"))
sub(os.path.join(scen, "uv.lock.after"), os.path.join(out, "uv.lock.after"))
routes = []
simple = os.path.join(scen, "index", "simple")
for pkg in sorted(os.listdir(simple)):
    pdir = os.path.join(simple, pkg)
    if not os.path.isdir(pdir):
        continue
    shutil.copy(os.path.join(pdir, "index.html"), os.path.join(out, "http", f"{pkg}-listing-html"))
    routes.append(f'http.route("https://index.example/simple/{pkg}/", "{fixture_name}/http/{pkg}-listing-html");')
    for f in sorted(os.listdir(pdir)):
        if f.endswith(".metadata"):
            shutil.copy(os.path.join(pdir, f), os.path.join(out, "http", f))
            routes.append(f'http.route("https://index.example/simple/{pkg}/{f}", "{fixture_name}/http/{f}");')
print("\n".join(routes))
