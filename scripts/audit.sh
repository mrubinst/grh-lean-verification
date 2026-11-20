#!/usr/bin/env bash
# Static source audit of the Alpöge/Claude Lean development.
# Usage: scripts/audit.sh <path-to-unpacked lean/ directory>
# Counts files containing constructs that can introduce unchecked assumptions or bypass the kernel.
set -u
ROOT="${1:?path to lean/ dir}"
SRC="$ROOT/src"
echo "files: $(find "$SRC" -name '*.lean' | wc -l | tr -d ' ')"
echo "lines: $(find "$SRC" -name '*.lean' -print0 | xargs -0 cat | wc -l | tr -d ' ')"
echo
echo "== Constructs that add unproved assumptions or bypass the kernel (expect 0) =="
for pat in '^\s*axiom\b' '\bsorry\b' '\bsorryAx\b' '^\s*(by\s+)?admit\b|\badmit\s*$' 'native_decide' \
           'ofReduceBool' 'trustCompiler' 'implemented_by' '@\[extern' '\bunsafe\b' '^\s*opaque\b' \
           'addDeclWithoutChecking|addDeclCore|Kernel\.Environment\.add' 'set_option\s+debug\.'; do
  n=$(grep -rlE --include='*.lean' "$pat" "$SRC" | wc -l | tr -d ' ')
  printf '%-75s %s files\n' "$pat" "$n"
done
echo
echo "== Metaprogramming present (inspect by hand; kernel still checks results) =="
for pat in '^\s*elab\b|\belab "' 'run_cmd' '\baddDecl\b' 'modifyEnv|setEnv' '^import Lean'; do
  printf '%-75s %s files\n' "$pat" "$(grep -rlE --include='*.lean' "$pat" "$SRC" | wc -l | tr -d ' ')"
done
grep -rlE --include='*.lean' '^\s*elab\b|\belab "|run_cmd|\baddDecl\b|modifyEnv|setEnv' "$SRC" | sed "s#$SRC/#  #" | sort
