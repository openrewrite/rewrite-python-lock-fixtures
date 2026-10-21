#!/bin/zsh
# Usage: pipenv-install-oracle.sh <dir>
# Checks the Pipfile.lock in <dir> the way a pipenv user's CI does, in a clean Linux container with the Pipfile's
# Python: `pipenv verify` (the lock's _meta.hash matches the Pipfile) and `pipenv sync` (every entry installs from its
# hashes). Prints "verify=<exit> sync=<exit>". A Python pipenv 2026.6.1 does not install on gets its newest release
# that does. Needs podman or docker.
set -u
dir=${1:A}
runtime=$(command -v podman || command -v docker)
python=$(python3 - $dir/Pipfile <<'PY'
import sys, tomllib
requires = tomllib.load(open(sys.argv[1], "rb")).get("requires", {})
print(requires.get("python_full_version") or requires.get("python_version") or "3.12")
PY
)
out=$(mktemp -d)
cp $dir/Pipfile $dir/Pipfile.lock $out/
$runtime run --rm -v $out:/w -w /w -e PIPENV_VENV_IN_PROJECT=1 -e PIPENV_YES=1 -e PIPENV_NOSPIN=1 \
  python:$python-slim sh -c 'pip install -q pipenv==2026.6.1 >/dev/null 2>&1 || pip install -q pipenv >/dev/null 2>&1; pipenv verify >/w/verify.log 2>&1; echo $? >/w/verify.rc; pipenv sync >/w/sync.log 2>&1; echo $? >/w/sync.rc' >/dev/null 2>&1
echo "verify=$(cat $out/verify.rc 2>/dev/null || echo none) sync=$(cat $out/sync.rc 2>/dev/null || echo none)"
[ "$(cat $out/sync.rc 2>/dev/null)" = 0 ] || tail -5 $out/sync.log 2>/dev/null | sed 's/^/  /'
rm -rf $out
