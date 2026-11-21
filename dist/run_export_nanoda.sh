#!/bin/bash
# Export the five main theorems of Main.lean together with their full dependency closure
# (lean4export v4.33.0, `--` constant list), then check with nanoda allowing only
# propext / Classical.choice / Quot.sound. Any other axiom actually used => hard error.
# (A whole-environment export would include Lean core's Lean.reduceBool/reduceNat, which rest on
# Lean.trustCompiler even though nothing here uses them.)
W=/tmp/mrubinst_alpoge; T=$W/leanprover--lean4---v4.33.1; R=$W/lean; X=$W/export; B=/u/mrubinst/alpoge_grh
mkdir -p $X
export PATH=$T/bin:/usr/bin:/bin
export LEAN_PATH=$(for p in batteries Qq aesop proofwidgets importGraph LeanSearchClient plausible mathlib; do printf "%s:" $R/.lake/packages/$p/.lake/build/lib/lean; done)$R/.lake/build/lib/lean:$T/lib/lean
cd $R
echo "export start $(date -u)" > $B/nanoda.log
/usr/bin/time -v $B/tools/lean4export/.lake/build/bin/lean4export Main -- riemannHypothesis riemannZeta_eq_zero_re LFunction_ne_zero_of_half_lt_re LFunction_eq_zero_re LFunction_eq_zero_re_of_isPrimitive > $X/main.ndjson 2> $X/export.err
echo "export rc=$? end $(date -u) bytes=$(stat -c %s $X/main.ndjson)" >> $B/nanoda.log
tail -20 $X/export.err >> $B/nanoda.log
sha256sum $X/main.ndjson >> $B/nanoda.log
echo "nanoda start $(date -u)" >> $B/nanoda.log
/usr/bin/time -v $B/tools/nanoda_lib/target/release/nanoda_bin $B/dist/nanoda_config.json >> $B/nanoda.log 2>&1
echo "NANODA_EXIT $? $(date -u)" >> $B/nanoda.log
