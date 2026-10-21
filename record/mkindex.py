#!/usr/bin/env python3
"""Build a tiny PEP 503 simple index of pure-python wheels from a JSON spec, with PEP 658 sidecars.

spec: {"packages": [{"name": "foo", "version": "1.0", "requires_dist": ["bar>=1"], "requires_python": ">=3.8",
                     "provides_extra": ["x"], "yanked": false}, ...]}
Serves nothing itself: point `python -m http.server` at the output directory; the index root is /simple/.
Both uv (via [[tool.uv.index]] url = "http://127.0.0.1:PORT/simple/" default = true) and the native engine
(via the same declared index) then see identical listings, hashes and metadata.
"""
import base64
import hashlib
import html
import io
import json
import os
import re
import sys
import zipfile


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def dist_name(name):
    return re.sub(r"[-_.]+", "_", name)


def build_wheel(pkg, tag="py3-none-any"):
    name = pkg["name"]
    version = pkg["version"]
    dn = dist_name(name)
    metadata = [f"Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}", f"Summary: synthetic {name}"]
    if pkg.get("requires_python"):
        metadata.append(f"Requires-Python: {pkg['requires_python']}")
    for extra in pkg.get("provides_extra", []):
        metadata.append(f"Provides-Extra: {extra}")
    for req in pkg.get("requires_dist", []):
        metadata.append(f"Requires-Dist: {req}")
    metadata_text = "\n".join(metadata) + "\n"
    wheel_text = f"Wheel-Version: 1.0\nGenerator: mkindex\nRoot-Is-Purelib: true\nTag: {tag}\n"
    module = f"{dn}/__init__.py"
    module_text = f"__version__ = {version!r}\n"
    files = {module: module_text, f"{dn}-{version}.dist-info/METADATA": metadata_text,
             f"{dn}-{version}.dist-info/WHEEL": wheel_text}
    record_lines = []
    for path, text in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(text.encode()).digest()).rstrip(b"=").decode()
        record_lines.append(f"{path},sha256={digest},{len(text.encode())}")
    record_lines.append(f"{dn}-{version}.dist-info/RECORD,,")
    files[f"{dn}-{version}.dist-info/RECORD"] = "\n".join(record_lines) + "\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, text in files.items():
            info = zipfile.ZipInfo(path, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text)
    return f"{dn}-{version}-{tag}.whl", buf.getvalue(), metadata_text.encode()


def main(spec_path, out):
    spec = json.load(open(spec_path))
    by_name = {}
    for pkg in spec["packages"]:
        by_name.setdefault(canonical(pkg["name"]), []).append(pkg)
    simple = os.path.join(out, "simple")
    os.makedirs(simple, exist_ok=True)
    root_links = []
    for cname, pkgs in sorted(by_name.items()):
        pdir = os.path.join(simple, cname)
        os.makedirs(pdir, exist_ok=True)
        anchors = []
        for pkg in sorted(pkgs, key=lambda p: p["version"]):
          for tag in pkg.get("wheel_tags", ["py3-none-any"]):
            filename, wheel, metadata = build_wheel(pkg, tag)
            with open(os.path.join(pdir, filename), "wb") as f:
                f.write(wheel)
            with open(os.path.join(pdir, filename + ".metadata"), "wb") as f:
                f.write(metadata)
            sha = hashlib.sha256(wheel).hexdigest()
            msha = hashlib.sha256(metadata).hexdigest()
            attrs = f' data-core-metadata="sha256={msha}" data-dist-info-metadata="sha256={msha}"'
            if pkg.get("requires_python"):
                attrs += f' data-requires-python="{html.escape(pkg["requires_python"], quote=True)}"'
            if pkg.get("yanked"):
                attrs += ' data-yanked=""'
            anchors.append(f'<a href="{filename}#sha256={sha}"{attrs}>{filename}</a><br/>')
        with open(os.path.join(pdir, "index.html"), "w") as f:
            f.write("<!DOCTYPE html><html><head><meta name=\"pypi:repository-version\" content=\"1.0\">"
                    f"<title>Links for {cname}</title></head><body><h1>Links for {cname}</h1>\n" +
                    "\n".join(anchors) + "\n</body></html>\n")
        root_links.append(f'<a href="{cname}/">{cname}</a><br/>')
    with open(os.path.join(simple, "index.html"), "w") as f:
        f.write("<!DOCTYPE html><html><head><meta name=\"pypi:repository-version\" content=\"1.0\">"
                "<title>Simple index</title></head><body>\n" + "\n".join(root_links) + "\n</body></html>\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
