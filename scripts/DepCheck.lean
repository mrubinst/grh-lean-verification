import Main
/-!
Which declarations does `riemannHypothesis` actually depend on?
We compute the set of all constants reachable from `riemannHypothesis` through types and values
(the same closure `#print axioms` walks), and report, for a list of name suffixes, the constants in the
environment with that suffix and whether each one lies in the closure.
-/
open Lean Elab Command

def suffixes : List String :=
  ["landau_window", "WindowHypU", "zeroFreeAll_of_topG", "supplyChi", "pairEx", "PairEx", "PairGood", "ZeroBox", "WinPair", "BoxCountHyp", "BoxTailHyp", "MeanSquareHyp", "MeanSquareHypW", "ZeroFreeBox", "pair_exists", "kappa4", "ThinScales", "NodeSizes", "ThickPartTranslateMean", "GrowthInequalityForm", "GrowthInequalityExplicit", "GrowthInequalityHypotheses", "GrowthSizeBound", "SizeWindows", "proposition_size_bound", "ThinH", "VWinAt", "VWin", "VAt", "VVle", "PageN", "IsChiField", "AskMainBalance", "ASK", "MAIN", "askP", "askD", "IsInert", "InPhi", "partner", "IsThickAt", "thickPl", "topPl", "ch_top", "core_gm", "ch_balance", "ch_core", "level_gm_le_on_family_scales", "windowInequality_of_artinInputs", "ChebyshevInequalityOnWindows", "ChebyshevInequalityAtWindowScale", "zeroFreeOn_of_tiedWin_cyc", "level_of_tiedWin", "zeroFree_of_rpow_window", "zero_free_of_Chebyshev_growth", "ChebyshevGrowthImpliesZeroFree", "Gz", "Gm", "gChi", "everyCharacter", "EveryCharacter", "rh_of_every", "critLine", "imprimitive", "plugWin", "plugAll", "zero_free_all_of_green_v_win", "every_character_of_literature_of_vWin", "vwin_of_row", "galoisLocalGlobalStrong_recParameter", "Row0b", "htMap", "opNormAt", "muDef", "fockSq", "jet", "fockIP", "Hq", "dens", "KerAt", "hookF", "hookR", "phF", "chowla_selberg_period", "CountIdentity", "ChainInt", "ChainIntM", "key_minor_dvd", "key_pow_dvd", "HasseDerivProdVanish", "StarArith", "BCore", "FactorialLg", "frameJet", "jetPairPoly", "thetaZ", "ThmSFree", "FrameLA", "LayerCake", "FrameLast", "CorankShare", "slopeInequality_of", "glueLat", "BesselId", "Interlace", "BehrendFree", "BehrendBound", "SpaceFree", "SelectTops", "thetaLift", "latLift", "latIp", "LatSeeSaw", "LinkG_at", "LinkN_at", "LinkS", "DIV", "sizeBudget", "budgetNc", "Ranks", "sigW", "RealBox", "ZetaQuarterPowerCorollary", "DetGain", "OCCMEstimate", "OCCMToZeta", "OCStep", "OCAvg", "RiemannHypothesisOfLowerBounds", "poi", "ppCls", "shaLen", "qzTw", "mellinRamp", "poleData"]

elab "#depcheck" : command => do
  let env ← getEnv
  let mut seen : NameHashSet := {}
  let mut stack : Array Name := #[`riemannHypothesis]
  while !stack.isEmpty do
    let n := stack.back!
    stack := stack.pop
    if seen.contains n then continue
    seen := seen.insert n
    if let some ci := env.find? n then
      for c in ci.type.getUsedConstantsAsSet do
        if !seen.contains c then stack := stack.push c
      if let some v := ci.value? (allowOpaque := true) then
        for c in v.getUsedConstantsAsSet do
          if !seen.contains c then stack := stack.push c
  logInfo m!"closure of riemannHypothesis: {seen.size} constants"
  for s in suffixes do
    let mut hits : Array (Name × Bool) := #[]
    for (n, _) in env.constants.toList do
      match n with
      | .str _ last => if last == s then hits := hits.push (n, seen.contains n)
      | _ => pure ()
    logInfo m!"{s}: {hits.toList.map fun (n, b) => m!"{n} used={b}"}"

#depcheck
