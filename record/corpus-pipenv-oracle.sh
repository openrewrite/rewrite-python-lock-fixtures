#!/bin/zsh
# Usage: run_pipenv_oracle.sh <cases-root/pipenv> <results-dir>
# Applies edit_pipfile.py's upgrade to each case, runs the engine, and checks a lock it writes with
# pipenv-install-oracle.sh: install-correct means verify=0 and sync=0.
set -u
root=$1; res=$2; mkdir -p $res
cp="/tmp/pylock-harness/out:$(cat ${PYLOCK_CP_FILE:-/tmp/pylock-harness/classpath.txt})"
for d in $root/*/; do
 name=$(basename $d)
 for kind in ${=EDIT_KINDS:-upgrade removal add-leaf}; do
  o=$res/$name/$kind; rm -rf $o; mkdir -p $o
  python3 /tmp/pylock-harness/edit_pipfile.py $d/Pipfile $d/Pipfile.lock $kind > $o/Pipfile.after 2> $o/edit.log || { echo "pipenv\t$name\t$kind\tno-edit\t$(tail -1 $o/edit.log)"; rm -rf $o; continue; }
  java -cp "$cp" Harness pipenv $d/Pipfile $o/Pipfile.after $d/Pipfile.lock $o/Pipfile.lock.engine > $o/engine.out 2>&1
  st=$(grep '^STATUS' $o/engine.out | cut -d' ' -f2)
  if [ "$st" != success ]; then echo "pipenv\t$name\t$kind\t$st:$(grep '^REASON' $o/engine.out | cut -d' ' -f2)\t$(cat $o/edit.log)\t$(grep '^DETAIL' $o/engine.out | cut -c8-140)"; continue; fi
  mkdir -p $o/check && cp $o/Pipfile.after $o/check/Pipfile && cp $o/Pipfile.lock.engine $o/check/Pipfile.lock
  verdict=$(zsh /tmp/pylock-harness/pipenv-install-oracle.sh $o/check | head -1)
  if [ "$verdict" = "verify=0 sync=0" ]; then v=INSTALL_CORRECT
  else
    # the original lock failing the same way makes the environment, not the engine, the cause
    baseline=$(zsh /tmp/pylock-harness/pipenv-install-oracle.sh $d | head -1)
    [ "$baseline" = "verify=0 sync=0" ] && v="INSTALL_FAILED($verdict)" || v="ENVIRONMENT($verdict, original $baseline)"
  fi
  echo "pipenv\t$name\t$kind\t$v\t$(cat $o/edit.log)"
 done
done
