#!/bin/zsh
HERE=${0:A:h}
# Copies every worktree build directory on classpath.txt into snapshot/ and writes classpath.snapshot.txt,
# so a corpus run keeps using one engine build while the worktree recompiles.
set -u
rm -rf $HERE/snapshot; mkdir -p $HERE/snapshot
out=""; i=0
for p in $(tr ':' '\n' < $HERE/classpath.txt); do
  if [[ $p == */.worktrees/* && -d $p ]]; then
    i=$((i+1)); dst=$HERE/snapshot/$i; cp -R $p $dst; p=$dst
  fi
  out="$out${out:+:}$p"
done
echo $out > $HERE/classpath.snapshot.txt
echo "snapshot: $i directories"
