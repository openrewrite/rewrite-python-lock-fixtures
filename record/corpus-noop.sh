#!/bin/zsh
HERE=${0:A:h}
# Usage: run_noop.sh <cases-root> <results-dir>; runs every corpus case through its engine with an identical manifest
set -u
root=$1; res=$2; mkdir -p $res
cp="$HERE/out:$(cat ${PYLOCK_CP_FILE:-$HERE/classpath.txt})"
for mgr in uv pipenv poetry pdm; do
  [ -d $root/$mgr ] || continue
  case $mgr in uv) lock=uv.lock; man=pyproject.toml;; pipenv) lock=Pipfile.lock; man=Pipfile;; poetry) lock=poetry.lock; man=pyproject.toml;; pdm) lock=pdm.lock; man=pyproject.toml;; esac
  for d in $root/$mgr/*/; do
    name=$(basename $d); o=$res/$mgr/$name; mkdir -p $o
    java -cp "$cp" Harness $mgr $d/$man $d/$man $d/$lock $o/$lock.noop > $o/noop.out 2>&1
    st=$(grep '^STATUS' $o/noop.out | cut -d' ' -f2)
    if [ "$st" = success ]; then
      if cmp -s $o/$lock.noop $d/$lock; then verdict=identical; else verdict=DIFFERS; diff $d/$lock $o/$lock.noop > $o/noop.diff; fi
    else verdict=$st; fi
    echo "$mgr\t$name\t$verdict\t$(grep -E '^(REASON|DETAIL|CRASH)' $o/noop.out | head -2 | tr '\n' ' ' | cut -c1-200)"
  done
done
