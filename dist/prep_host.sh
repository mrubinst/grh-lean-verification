#!/bin/bash
# Stage a local replica (toolchain, dependency .oleans, sources) on this host's /tmp, same paths on every host.
set -e
W=/tmp/mrubinst_alpoge; N=/u/mrubinst/alpoge_grh/lean
mkdir -p $W/lean/.lake/packages; chmod 700 $W
[ -x $W/leanprover--lean4---v4.33.1/bin/lean ] || tar cf - -C /u/mrubinst/.elan/toolchains leanprover--lean4---v4.33.1 | tar xf - -C $W
for p in batteries Qq aesop proofwidgets importGraph LeanSearchClient plausible mathlib; do
  [ -d $W/lean/.lake/packages/$p/.lake/build/lib/lean ] && continue
  mkdir -p $W/lean/.lake/packages/$p/.lake/build/lib
  tar cf - -C $N/.lake/packages/$p/.lake/build/lib lean | tar xf - -C $W/lean/.lake/packages/$p/.lake/build/lib
done
[ -f $W/lean/src/Main.lean ] || tar cf - -C $N src | tar xf - -C $W/lean
echo "PREP_OK $(hostname -s) $(du -sh $W | cut -f1)"
