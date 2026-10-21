#!/usr/bin/env python3
"""Print the `uv lock` flags that reproduce a lock's [options], one argument per line.

usage: uv-lock-options.py <uv.lock>
"""
import re
import sys

text = open(sys.argv[1]).read()
m = re.search(r"^\[options\]\n((?:[^\[\n].*\n)*)", text, re.M)
options = dict(re.findall(r'^([a-z-]+) = "([^"]*)"', m.group(1), re.M)) if m else {}
span = re.fullmatch(r"P(\d+)([DW])", options.get("exclude-newer-span", ""))
args = []
if span:
    args += ["--exclude-newer", span.group(1) + (" days" if span.group(2) == "D" else " weeks")]
elif "exclude-newer" in options:
    args += ["--exclude-newer", options["exclude-newer"]]
for option, flag in (("resolution-mode", "--resolution"), ("prerelease-mode", "--prerelease"),
                     ("fork-strategy", "--fork-strategy")):
    if option in options:
        args += [flag, options[option]]
pkg = re.search(r"^\[options\.exclude-newer-package\]\n((?:[^\[\n].*\n)*)", text, re.M)
for name, value in re.findall(r'^([A-Za-z0-9._-]+) = (.+)$', pkg.group(1), re.M) if pkg else []:
    inline = re.search(r'span = "P(\d+)([DW])"', value)
    if value == "false":
        args += ["--exclude-newer-package", f"{name}=false"]
    elif inline:
        args += ["--exclude-newer-package", f"{name}={inline.group(1)} {'days' if inline.group(2) == 'D' else 'weeks'}"]
    else:
        args += ["--exclude-newer-package", f"{name}={value.strip(chr(34))}"]
print("\n".join(args))
