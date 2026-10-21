#!/bin/zsh
HERE=${0:A:h}
# Usage: run_engine_scenario.sh <scenario-dir> -> uv.lock.engine (or failure text), diffed against uv.lock.after
set -u
d=$1; port=$(cat $d/port)
(cd $d/index && python3 -m http.server $port --bind 127.0.0.1 >/dev/null 2>&1 &) ; sleep 0.7
sed "s/__PORT__/$port/" $d/pyproject.before.toml > $d/work/pyproject.before.toml
sed "s/__PORT__/$port/" $d/pyproject.after.toml > $d/work/pyproject.after.toml
rm -f $d/uv.lock.engine
java -cp "$HERE/out:$(cat ${PYLOCK_CP_FILE:-$HERE/classpath.txt})" Harness uv $d/work/pyproject.before.toml $d/work/pyproject.after.toml $d/uv.lock.before $d/uv.lock.engine > $d/engine.out 2>&1
pkill -f "http.server $port"
echo "== $d"; grep -v MILLIS $d/engine.out | head -8
if [ -f $d/uv.lock.engine ]; then
  if cmp -s $d/uv.lock.engine $d/uv.lock.after; then echo "IDENTICAL to real uv"; else echo "DIFF engine vs real uv:"; diff $d/uv.lock.engine $d/uv.lock.after | head -40; fi
fi
