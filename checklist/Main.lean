/-
Kernel replay over an explicit list of modules.

`replayFromImports` below is copied VERBATIM from Lean's own `leanchecker`
(src/LeanChecker.lean, tag v4.33.1, Copyright (c) 2023 Kim Morrison, Apache 2.0).
Only the driver differs: stock `leanchecker` resolves each command-line target by walking
every .olean on the search path, which is quadratic for 175,187 modules; here the module
names are read from a file instead. The kernel check performed is identical.
-/
import Lean.CoreM
import Lean.Replay

open Lean

unsafe def replayFromImports (module : Name) : IO Unit := do
  let mFile ← findOLean module
  unless (← mFile.pathExists) do
    throw <| IO.userError s!"object file '{mFile}' of module {module} does not exist"
  -- Load all module data parts (exported, server, private)
  let mut fnames := #[mFile]
  let sFile := OLeanLevel.server.adjustFileName mFile
  if (← sFile.pathExists) then
    fnames := fnames.push sFile
    let pFile := OLeanLevel.private.adjustFileName mFile
    if (← pFile.pathExists) then
      fnames := fnames.push pFile
  let parts ← readModuleDataParts fnames
  if h : parts.size = 0 then throw <| IO.userError "failed to read module data" else
  let (mod, _) := parts[0]
  let (_, s) ← importModulesCore mod.imports |>.run
  let env ← finalizeImport s mod.imports {} 0 false false (isModule := true)
  let mut newConstants := {}
  -- Collect constants from last ("most private") part, which subsumes all prior ones
  for name in parts[parts.size-1].1.constNames, ci in parts[parts.size-1].1.constants do
    newConstants := newConstants.insert name ci
  let env' ← env.replay newConstants
  env'.freeRegions

unsafe def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  let some file := args.head? | throw <| IO.userError "usage: checklist <file with one module name per line>"
  let mods := ((← IO.FS.readFile file).splitOn "\n").filterMap fun s =>
    let s := s.trim; if s.isEmpty then none else some s.toName
  let mut tasks := #[]
  for m in mods do
    tasks := tasks.push (m, ← IO.asTask (replayFromImports m))
  let mut bad := 0
  for (m, t) in tasks do
    match t.get with
    | .ok _ => IO.println s!"OK {m}"
    | .error e => bad := bad + 1; IO.println s!"FAIL {m}: {e}"
    (← IO.getStdout).flush
  IO.println s!"SUMMARY checked={mods.length} failed={bad}"
  return if bad == 0 then 0 else 1
