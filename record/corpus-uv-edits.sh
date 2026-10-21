#!/bin/zsh
HERE=${0:A:h}
# Usage: run_uv_edits.sh <cases-root/uv> <results-dir> [uv-version]
# For every uv corpus case whose no-op round trip is identical: pin the first registry direct dependency
# that has a newer version on PyPI to that newer version, run the engine and real uv over the same edit,
# and diff byte for byte. Also runs a removal edit (drop the last [project] dependency) the same way.
set -u
root=$1; res=$2; uvv=${3:-0.10.11}; mkdir -p $res
cp="$HERE/out:$(cat ${PYLOCK_CP_FILE:-$HERE/classpath.txt})"
export UV_CACHE_DIR=$(mktemp -d) XDG_CONFIG_HOME=$(mktemp -d)
export PYLOCK_UV_VERSION=$uvv
for d in $root/*/; do
  name=$(basename $d)
  grep -q "^uv	$name	identical" ${NOOP_TSV:?set NOOP_TSV to a corpus-noop.sh result} || continue
  for kind in ${=EDIT_KINDS:-upgrade removal add-leaf add-closure transitive}; do
    o=$res/$name/$kind; rm -rf $o; mkdir -p $o/work
    cp $d/pyproject.toml $o/pyproject.before.toml; cp $d/uv.lock $o/uv.lock.before
    python3 $HERE/edit_pyproject.py $kind $o/pyproject.before.toml $o/uv.lock.before > $o/pyproject.after.toml 2> $o/edit.log
    if [ $? -ne 0 ]; then echo "uv\t$name\t$kind\tno-edit\t$(tail -1 $o/edit.log)"; rm -rf $o; continue; fi
    # uv gets the lock's [options] as flags, and shares the engine's "now"
    now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    flags=(${(f)"$(python3 $HERE/uv-lock-options.py $o/uv.lock.before)"})
    PYLOCK_CURRENT_TIME=$now java -cp "$cp" Harness uv $o/pyproject.before.toml $o/pyproject.after.toml $o/uv.lock.before $o/uv.lock.engine > $o/engine.out 2>&1
    st=$(grep '^STATUS' $o/engine.out | cut -d' ' -f2)
    cp $o/pyproject.after.toml $o/work/pyproject.toml; cp $o/uv.lock.before $o/work/uv.lock
    (cd $o/work && UV_INTERNAL__TEST_CURRENT_TIMESTAMP=$now timeout 300 uvx uv@$uvv lock "${flags[@]}" --no-progress -q > ../uv.out 2>&1); uvrc=$?
    if [ $uvrc -ne 0 ]; then uvres="uv-failed"; else uvres="uv-ok"; fi
    if [ "$st" = success ]; then
      if [ $uvrc -eq 0 ]; then
        if cmp -s $o/uv.lock.engine $o/work/uv.lock; then verdict=IDENTICAL; else verdict=WRONG_LOCK; diff $o/uv.lock.engine $o/work/uv.lock > $o/engine-vs-uv.diff; fi
      else verdict=ENGINE_OK_UV_FAILED; fi
    else
      verdict="$st:$(grep '^REASON' $o/engine.out | cut -d' ' -f2):$uvres"
    fi
    echo "uv\t$name\t$kind\t$verdict\t$(cat $o/edit.log | tail -1)\t$(grep '^DETAIL' $o/engine.out | head -1 | cut -c1-140)"
  done
done
