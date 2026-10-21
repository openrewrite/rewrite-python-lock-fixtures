#!/bin/zsh
HERE=${0:A:h}
# Usage: record-uv-scenario.sh <scenario-dir>. Serves the scenario's index.json as a local PEP 503 index and writes
# uv.lock.before and uv.lock.after with real uv (UV_RELEASE, default 0.13.4) from pyproject.before.toml and pyproject.after.toml.
set -u
d=$1
port=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
rm -rf $d/index $d/work && python3 $HERE/mkindex.py $d/index.json $d/index
(cd $d/index && python3 -m http.server $port --bind 127.0.0.1 >/dev/null 2>&1 &) ; sleep 0.7
echo $port > $d/port
mkdir -p $d/work
sed "s/__PORT__/$port/" $d/pyproject.before.toml > $d/work/pyproject.toml
export UV_CACHE_DIR=$(mktemp -d) XDG_CONFIG_HOME=$(mktemp -d) UV_PYTHON=3.12
(cd $d/work && uvx uv@${UV_RELEASE:-0.13.4} lock --no-progress -q) ; cp $d/work/uv.lock $d/uv.lock.before
sed "s/__PORT__/$port/" $d/pyproject.after.toml > $d/work/pyproject.toml
(cd $d/work && uvx uv@${UV_RELEASE:-0.13.4} lock --no-progress -q) ; cp $d/work/uv.lock $d/uv.lock.after
pkill -f "http.server $port" ; rm -rf $UV_CACHE_DIR
echo "== $d"; diff $d/uv.lock.before $d/uv.lock.after | head -60
