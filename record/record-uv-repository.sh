#!/bin/zsh
# Usage: record-uv-repository.sh <edit-dir> <case-dir> <scenario-dir> [uv-release]
# Turns one corpus edit (corpus-uv-edits.sh output: pyproject.before.toml, pyproject.after.toml, uv.lock.before,
# edit.log) of a corpus case (META.json) into a lock/repository/uv scenario. uv locks the edit from an empty cache,
# then the engine replays it with every index response recorded into http/. Exits 1, writing nothing, when uv fails.
set -u
HERE=${0:A:h}
edit=$1; case_dir=$2; out=$3; uvv=${4:-0.13.4}
cp="$HERE/out:$(cat ${PYLOCK_CP_FILE:-$HERE/classpath.txt})"
work=$(mktemp -d); cache=$(mktemp -d)
cp $edit/pyproject.after.toml $work/pyproject.toml; cp $edit/uv.lock.before $work/uv.lock
# the lock's [options] stand for settings its author may have made outside the manifest, so uv gets them as flags
flags=(${(f)"$(python3 $HERE/uv-lock-options.py $edit/uv.lock.before)"})
(cd $work && UV_CACHE_DIR=$cache XDG_CONFIG_HOME=$cache timeout 300 uvx uv@$uvv lock "${flags[@]}" --no-progress -q) > /dev/null 2>&1 || { rm -rf $work $cache; exit 1; }
rm -rf $out; mkdir -p $out/tree-before $out/tree
cp $edit/pyproject.before.toml $out/tree-before/pyproject.toml
cp $edit/pyproject.after.toml $out/tree/pyproject.toml
cp $edit/uv.lock.before $out/before
cp $work/uv.lock $out/after
echo "uv $uvv" > $out/recorded-with
python3 - $case_dir/META.json "$(tail -1 $edit/edit.log)" > $out/about <<'PY'
import json, sys
meta = json.load(open(sys.argv[1]))
print(f"https://github.com/{meta['repo']}/blob/{meta['sha']}/{meta['dir'] + '/' if meta['dir'] else ''}{meta['lock']}")
print(sys.argv[2])
PY
PYLOCK_RECORD_HTTP=$out/http PYLOCK_UV_VERSION=$uvv java -cp "$cp" Harness uv $out/tree-before/pyproject.toml \
  $out/tree/pyproject.toml $out/before $work/uv.lock.engine > $work/engine.out 2>&1
if grep -q '^STATUS success' $work/engine.out && cmp -s $work/uv.lock.engine $out/after; then
  echo exact
else
  grep -E '^(STATUS|REASON)' $work/engine.out | cut -d' ' -f2 | paste -sd' ' -
fi
rm -rf $work $cache
