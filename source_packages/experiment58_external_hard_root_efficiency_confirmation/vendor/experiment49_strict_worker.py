"""Live-TacticInfo worker with Exp48-text and strict structural endpoints.

The exact source file is elaborated unchanged.  The authored syntax and all
23 frozen alternatives are executed as independent branches from
``ContextInfo + TacticInfo.mctxBefore + TacticInfo.goalsBefore``.  Exp49 adds
a deterministic structural encoding of the ordered post-goal state; it does
not compare proof terms, messages, timing, or internal tactic traces.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from experiment49_protocol import (
    ALTERNATIVE_BUDGET,
    MECHANICAL_FIX_ID,
    RAID_DATA_ROOT,
    STRICT_ENDPOINT_SCHEMA,
    atomic_json_dump,
    file_sha256,
    json_sha256,
    normalize_goal_text,
    read_json,
    tactic_family,
    tactic_head,
)

WORKER_VERSION = "experiment49-live-tacticinfo-strict-worker-v1-fix1"
LEAN_FILE_NAME = "Experiment49StrictEndpointWorker.lean"


def _raw_pos(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("boolean is not a raw position")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if isinstance(value, dict):
        for key in ("byteIdx", "raw", "byte", "offset", "value", "pos"):
            if key in value:
                return _raw_pos(value[key])
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return _raw_pos(value[0])
    raise TypeError(f"unsupported raw position representation: {value!r}")


def _field(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def _source_slice_raw(source: str, start: int, end: int) -> str:
    data = source.encode("utf-8")
    if not (0 <= start <= end <= len(data)):
        raise ValueError(f"raw source span outside UTF-8 buffer: {start}:{end}/{len(data)}")
    return data[start:end].decode("utf-8")


def _locate_ast_json(checkout: Path, file_path: str) -> Path:
    rel = Path(file_path).with_suffix(".ast.json")
    for p in (checkout / ".lake/build/ir" / rel, checkout / "build/ir" / rel):
        if p.is_file():
            return p.resolve()
    raise FileNotFoundError(f"no ast.json for {file_path} under {checkout}")


def _metadata_traced_checkout(raid_root: Path, slug: str, commit: str) -> Path | None:
    metadata = raid_root / f"{slug.rsplit('/', 1)[-1]}_{commit}" / "metadata.json"
    if not metadata.is_file():
        return None
    value = read_json(metadata)
    candidates: list[Any] = []
    if isinstance(value, dict):
        from_repo = value.get("from_repo")
        if isinstance(from_repo, dict):
            candidates += [from_repo.get("url"), from_repo.get("path")]
        for key in ("repo", "repository"):
            obj = value.get(key)
            if isinstance(obj, dict):
                candidates += [obj.get("url"), obj.get("path")]
    for raw in candidates:
        if isinstance(raw, str) and raw.startswith("/") and Path(raw).is_dir():
            return Path(raw).resolve()
    return None


def resolve_ast_source(project: Path, raid_root: Path, slug: str, commit: str,
                       file_path: str, expected_sha: str) -> tuple[Path, Path]:
    roots = [project]
    traced = _metadata_traced_checkout(raid_root, slug, commit)
    if traced is not None and traced not in roots:
        roots.append(traced)
    errors = []
    for root in roots:
        try:
            ast = _locate_ast_json(root, file_path)
            source = (root / file_path).resolve()
            if not source.is_file() or file_sha256(source) != expected_sha:
                raise ValueError("source SHA mismatch")
            return ast, source
        except Exception as exc:
            errors.append(f"{root}: {type(exc).__name__}: {exc}")
    raise FileNotFoundError(" | ".join(errors))


def resolve_target_from_ast(ast_path: Path, source_path: Path,
                            frozen_trace_root: str, authored_tactic: str) -> dict[str, Any]:
    ast = read_json(ast_path)
    tactics = ast.get("tactics") if isinstance(ast, dict) else None
    if not isinstance(tactics, list):
        raise ValueError(f"{ast_path}: missing tactics array")
    source = source_path.read_text(encoding="utf-8")
    target_norm = normalize_goal_text(frozen_trace_root)
    state_matches = []
    exact_matches = []
    for idx, row in enumerate(tactics):
        if not isinstance(row, dict) or normalize_goal_text(
                _field(row, "stateBefore", "state_before")) != target_norm:
            continue
        pos = _raw_pos(_field(row, "pos", "startPos", "start_pos"))
        end = _raw_pos(_field(row, "endPos", "end_pos", "tailPos"))
        tactic_text = _source_slice_raw(source, pos, end)
        item = {
            "record_index": idx, "pos": pos, "end_pos": end,
            "state_before": str(_field(row, "stateBefore", "state_before")),
            "state_after": str(_field(row, "stateAfter", "state_after")),
            "source_tactic_text": tactic_text,
        }
        state_matches.append(item)
        if re.sub(r"\s+", " ", tactic_text.strip()) == re.sub(r"\s+", " ", authored_tactic.strip()):
            exact_matches.append(item)
    pool = exact_matches or state_matches
    if len(pool) != 1:
        raise ValueError(f"expected one frozen root edge; state_matches={len(state_matches)} "
                         f"authored_text_matches={len(exact_matches)}")
    ans = dict(pool[0])
    ans["state_match_count"] = len(state_matches)
    ans["authored_text_match_count"] = len(exact_matches)
    return ans


LEAN_SOURCE = r'''
import Lean
import Lake

open Lean Elab System

set_option maxHeartbeats 2000000

instance : ToJson String.Pos.Raw where
  toJson n := toJson n.1

namespace Exp49LiveBranch

namespace Pp

private def addLine (s : String) : String :=
  if s.isEmpty then s else s ++ "\n"

private def ppGoal (mvarId : MVarId) : MetaM String := do
  let mctx ← getMCtx
  match mctx.findDecl? mvarId with
  | none => return "unknown goal"
  | some mvarDecl =>
    let indent := 2
    let lctx := mvarDecl.lctx
    let lctx := lctx.sanitizeNames.run' { options := (← getOptions) }
    Meta.withLCtx lctx mvarDecl.localInstances do
      let rec pushPending (ids : List Name) (type? : Option Expr) (s : String) : MetaM String := do
        if ids.isEmpty then
          return s
        else
          let s := addLine s
          match type? with
          | none => return s
          | some type =>
            let typeFmt ← Meta.ppExpr type
            return (s ++ (Format.joinSep ids.reverse (format " ") ++ " :" ++
              Format.nest indent (Format.line ++ typeFmt)).group).pretty
      let rec ppVars (varNames : List Name) (prevType? : Option Expr) (s : String)
          (localDecl : LocalDecl) : MetaM (List Name × Option Expr × String) := do
        match localDecl with
        | .cdecl _ _ varName type _ _ =>
          let varName := varName.simpMacroScopes
          let type ← instantiateMVars type
          if prevType? == none || prevType? == some type then
            return (varName :: varNames, some type, s)
          else
            let s ← pushPending varNames prevType? s
            return ([varName], some type, s)
        | .ldecl _ _ varName type val _ _ =>
          let varName := varName.simpMacroScopes
          let s ← pushPending varNames prevType? s
          let s := addLine s
          let type ← instantiateMVars type
          let typeFmt ← Meta.ppExpr type
          let mut fmtElem := format varName ++ " : " ++ typeFmt
          let val ← instantiateMVars val
          let valFmt ← Meta.ppExpr val
          fmtElem := fmtElem ++ " :=" ++ Format.nest indent (Format.line ++ valFmt)
          let s := s ++ fmtElem.group.pretty
          return ([], none, s)
      let (varNames, type?, s) ← lctx.foldlM
        (init := ([], none, ""))
        fun (varNames, prevType?, s) (localDecl : LocalDecl) =>
          if localDecl.isAuxDecl || localDecl.isImplementationDetail then
            return (varNames, prevType?, s)
          else
            ppVars varNames prevType? s localDecl
      let s ← pushPending varNames type? s
      let goalTypeFmt ← Meta.ppExpr (← instantiateMVars mvarDecl.type)
      let goalFmt := Meta.getGoalPrefix mvarDecl ++ Format.nest indent goalTypeFmt
      let s := s ++ "\n" ++ goalFmt.pretty
      match mvarDecl.userName with
      | Name.anonymous => return s
      | name => return "case " ++ name.eraseMacroScopes.toString ++ "\n" ++ s

def ppGoalsM (goals : List MVarId) : MetaM String := do
  if goals.isEmpty then
    return "no goals"
  let parts ← goals.mapM ppGoal
  return (String.intercalate "\n\n" parts).trimAscii.toString

def ppGoals (ctx : ContextInfo) (goals : List MVarId) : IO String :=
  if goals.isEmpty then return "no goals" else ctx.runMetaM {} (ppGoalsM goals)

end Pp

namespace Strict

structure CanonState where
  exprMVars : List MVarId := []
  levelMVars : List LMVarId := []
  levelParams : List Name := []
  extraFVars : List FVarId := []
deriving Inhabited

abbrev CanonM := StateT CanonState MetaM

private def listIndex? [BEq α] (needle : α) : List α → Option Nat
  | [] => none
  | x :: xs => if x == needle then some 0 else (listIndex? needle xs).map Nat.succ

private def binderKey : BinderInfo → String
  | .default => "explicit"
  | .implicit => "implicit"
  | .strictImplicit => "strictImplicit"
  | .instImplicit => "instImplicit"

private def localKindKey : LocalDeclKind → String
  | .default => "default"
  | .implDetail => "implDetail"
  | .auxDecl => "auxDecl"

private def mvarKindKey : MetavarKind → String
| .natural => "natural"
| .synthetic => "synthetic"
| .syntheticOpaque => "syntheticOpaque"

private def quoted (s : String) : String := reprStr s
private def node (tag : String) (parts : List String) : String :=
  "(" ++ tag ++ (if parts.isEmpty then "" else " " ++ String.intercalate " " parts) ++ ")"

private def internLevelMVar (id : LMVarId) : CanonM Nat := do
  let st ← get
  match listIndex? id st.levelMVars with
  | some i => pure i
  | none =>
    let i := st.levelMVars.length
    set { st with levelMVars := st.levelMVars ++ [id] }
    pure i

private def internLevelParam (n : Name) : CanonM Nat := do
  let st ← get
  match listIndex? n st.levelParams with
  | some i => pure i
  | none =>
    let i := st.levelParams.length
    set { st with levelParams := st.levelParams ++ [n] }
    pure i

private partial def levelKey : Level → CanonM String
  | .zero => pure "L0"
  | .succ l => return node "LS" [← levelKey l]
  | .max a b => return node "LMAX" [← levelKey a, ← levelKey b]
  | .imax a b => return node "LIMAX" [← levelKey a, ← levelKey b]
  | .param n => return node "LP" [toString (← internLevelParam n)]
  | .mvar id => do
    let assignment? ← getLevelMVarAssignment? id
    match assignment? with
    | some l => levelKey l
    | none => return node "LM" [toString (← internLevelMVar id)]

private def fvarKey (fvars : List FVarId) (id : FVarId) : CanonM String := do
  match listIndex? id fvars with
  | some i => return "L" ++ toString i
  | none =>
    let st ← get
    match listIndex? id st.extraFVars with
    | some i => return "X" ++ toString i
    | none =>
      let i := st.extraFVars.length
      set { st with extraFVars := st.extraFVars ++ [id] }
      return "X" ++ toString i

private partial def exprKey (fvars : List FVarId) (e : Expr) : CanonM String := do
  match e with
  | .bvar i => return node "B" [toString i]
  | .fvar id => return node "F" [← fvarKey fvars id]
  | .mvar id =>
    let assignment? ← getExprMVarAssignment? id
    match assignment? with
    | some value => exprKey fvars value
    | none =>
      let st ← get
      match listIndex? id st.exprMVars with
      | some i => return node "MREF" [toString i]
      | none =>
        let i := st.exprMVars.length
        set { st with exprMVars := st.exprMVars ++ [id] }
        let mctx ← getMCtx
        match mctx.findDecl? id with
        | none => return node "M" [toString i, "missing"]
        | some decl =>
          let contextKeys ← decl.lctx.getFVarIds.toList.mapM (fvarKey fvars)
          let instanceKeys ← decl.localInstances.toList.mapM fun inst => do
            return node "INSTANCE" [quoted inst.className.toString, ← exprKey fvars inst.fvar]
          let ty ← exprKey fvars decl.type
          return node "M" [toString i, mvarKindKey decl.kind,
            toString decl.lctx.size, toString decl.numScopeArgs,
            node "MCTX" contextKeys, node "MINST" instanceKeys, ty]
  | .sort l => return node "SORT" [← levelKey l]
  | .const n ls => return node "CONST" [quoted n.toString, node "LEVELS" (← ls.mapM levelKey)]
  | .app f a => return node "APP" [← exprKey fvars f, ← exprKey fvars a]
  | .lam _ ty body bi => return node "LAM" [binderKey bi, ← exprKey fvars ty, ← exprKey fvars body]
  | .forallE _ ty body bi => return node "FORALL" [binderKey bi, ← exprKey fvars ty, ← exprKey fvars body]
  | .letE _ ty value body nondep => return node "LET" [toString nondep,
      ← exprKey fvars ty, ← exprKey fvars value, ← exprKey fvars body]
  | .lit lit => return node "LIT" [quoted (reprStr lit)]
  | .mdata _ body => exprKey fvars body
  | .proj n i body => return node "PROJ" [quoted n.toString, toString i, ← exprKey fvars body]

private def isLocalInstance (decl : MetavarDecl) (id : FVarId) : Bool :=
  decl.localInstances.any fun inst =>
    match inst.fvar with
    | .fvar fvarId => fvarId == id
    | _ => false

private def localDeclKey (goalDecl : MetavarDecl) (fvars : List FVarId)
    (decl : LocalDecl) : CanonM String := do
  match decl with
  | .cdecl _ id _ ty bi kind =>
    return node "LOCAL" ["cdecl", ← fvarKey fvars id, binderKey bi,
      localKindKey kind, toString (isLocalInstance goalDecl id), ← exprKey fvars ty]
  | .ldecl _ id _ ty value nondep kind =>
    return node "LOCAL" ["ldecl", ← fvarKey fvars id, localKindKey kind,
      toString nondep, toString (isLocalInstance goalDecl id),
      ← exprKey fvars ty, ← exprKey fvars value]

private def goalKey (id : MVarId) : CanonM String := do
  let mctx ← getMCtx
  match mctx.findDecl? id with
  | none => return node "GOAL" ["missing"]
  | some decl =>
    let fvars := decl.lctx.getFVarIds.toList
    let locals ← decl.lctx.foldlM (init := ([] : List String)) fun acc localDecl => do
      return acc ++ [← localDeclKey decl fvars localDecl]
    let instances ← decl.localInstances.toList.mapM fun inst => do
      return node "INSTANCE" [quoted inst.className.toString, ← exprKey fvars inst.fvar]
    let target ← exprKey fvars decl.type
    return node "GOAL" [mvarKindKey decl.kind, toString decl.numScopeArgs,
      node "INSTANCES" instances, node "LOCALS" locals, node "TARGET" [target]]

def goalsKeyM (goals : List MVarId) : MetaM String := do
  let action : CanonM (List String) := goals.mapM goalKey
  let pair ← action.run {}
  return node "STATE" [node "GOALS" pair.1]

def goalsKey (ctx : ContextInfo) (goals : List MVarId) : IO String :=
  ctx.runMetaM {} (goalsKeyM goals)

end Strict

structure BranchResult where
  tactic : String
  executable : Bool
  preState : String
  strictPreState : String
  stateAfter : Option String := none
  strictStateAfter : Option String := none
  goalCount : Option Nat := none
  terminal : Option Bool := none
  error : Option String := none
deriving ToJson

structure WorkerResult where
  targetFound : Bool
  pos : Nat
  endPos : Nat
  preGoalCount : Option Nat := none
  stateBefore : Option String := none
  strictStateBefore : Option String := none
  originalStateAfter : Option String := none
  originalStrictStateAfter : Option String := none
  originalGoalCount : Option Nat := none
  authored : Option BranchResult := none
  alternatives : Array BranchResult := #[]
deriving ToJson

def executeSyntax (ctx : ContextInfo) (ti : TacticInfo) (label : String) (stx : Syntax) : IO BranchResult := do
  let ctxBefore := { ctx with mctx := ti.mctxBefore }
  let pre ← Pp.ppGoals ctxBefore ti.goalsBefore
  let strictPre ← Strict.goalsKey ctxBefore ti.goalsBefore
  try
    let triple ← ctxBefore.runMetaM {} do
      let [mvarId] := ti.goalsBefore
        | throwError "Exp49 live branch requires exactly one pre-state goal"
      let termAction : Term.TermElabM (List MVarId) :=
        Tactic.run mvarId (Tactic.evalTactic stx)
      let (goalsAfter, _) ← liftM (m := MetaM) <|
        Term.TermElabM.run termAction ({} : Term.Context) ({} : Term.State)
      let after ← Pp.ppGoalsM goalsAfter
      let strictAfter ← Strict.goalsKeyM goalsAfter
      pure (after, strictAfter, goalsAfter.length)
    return {
      tactic := label
      executable := true
      preState := pre
      strictPreState := strictPre
      stateAfter := some triple.1
      strictStateAfter := some triple.2.1
      goalCount := some triple.2.2
      terminal := some (triple.2.2 == 0)
    }
  catch ex =>
    return {
      tactic := label
      executable := false
      preState := pre
      strictPreState := strictPre
      error := some (toString ex)
    }

def executeText (ctx : ContextInfo) (ti : TacticInfo) (text : String) : IO BranchResult := do
  match Parser.runParserCategory ctx.env `tactic text with
  | .error err =>
    let ctxBefore := { ctx with mctx := ti.mctxBefore }
    let pre ← Pp.ppGoals ctxBefore ti.goalsBefore
    let strictPre ← Strict.goalsKey ctxBefore ti.goalsBefore
    return {
      tactic := text
      executable := false
      preState := pre
      strictPreState := strictPre
      error := some ("parse: " ++ err)
    }
  | .ok stx => executeSyntax ctx ti text stx

private partial def executeTexts (ctx : ContextInfo) (ti : TacticInfo)
    (texts : List String) (acc : Array BranchResult) : IO (Array BranchResult) := do
  match texts with
  | [] => pure acc
  | text :: rest =>
    let result ← executeText ctx ti text
    executeTexts ctx ti rest (acc.push result)

abbrev ProbeM := StateT (Array WorkerResult) IO

private def visitTacticInfo (ctx : ContextInfo) (ti : TacticInfo) (parent : InfoTree)
    (targetPos targetEndPos : Nat) (candidateTexts : List String) : ProbeM Unit := do
  match parent with
  | .node (Info.ofTacticInfo i) _ =>
    match i.stx.getKind with
    | ``Lean.Parser.Tactic.tacticSeq1Indented
    | ``Lean.Parser.Tactic.tacticSeqBracketed
    | ``Lean.Parser.Tactic.rewriteSeq =>
      let some posBefore := ti.stx.getPos? true | pure ()
      let some posAfter := ti.stx.getTailPos? true | pure ()
      if posBefore.1 != targetPos || posAfter.1 != targetEndPos then
        pure ()
      else
        let ctxBefore := { ctx with mctx := ti.mctxBefore }
        let ctxAfter := { ctx with mctx := ti.mctxAfter }
        let stateBefore ← Pp.ppGoals ctxBefore ti.goalsBefore
        let strictBefore ← Strict.goalsKey ctxBefore ti.goalsBefore
        let stateAfter ← Pp.ppGoals ctxAfter ti.goalsAfter
        let strictAfter ← Strict.goalsKey ctxAfter ti.goalsAfter
        let authored ← executeSyntax ctx ti "<authored>" ti.stx
        let alternatives ← executeTexts ctx ti candidateTexts #[]
        modify fun rows => rows.push {
          targetFound := true
          pos := targetPos
          endPos := targetEndPos
          preGoalCount := some ti.goalsBefore.length
          stateBefore := some stateBefore
          strictStateBefore := some strictBefore
          originalStateAfter := some stateAfter
          originalStrictStateAfter := some strictAfter
          originalGoalCount := some ti.goalsAfter.length
          authored := some authored
          alternatives := alternatives
        }
    | _ => pure ()
  | _ => pure ()

mutual
  private partial def traverseTree (ctx : ContextInfo) (tree : InfoTree) (parent : InfoTree)
      (targetPos targetEndPos : Nat) (candidateTexts : List String) : ProbeM Unit := do
    match tree with
    | .context ctx' t =>
      match ctx'.mergeIntoOuter? ctx with
      | some ctx' => traverseTree ctx' t tree targetPos targetEndPos candidateTexts
      | none => throw <| IO.userError "failed to synthesize ContextInfo while traversing InfoTree"
    | .node i children =>
      match i with
      | .ofTacticInfo ti => visitTacticInfo ctx ti parent targetPos targetEndPos candidateTexts
      | _ => pure ()
      traverseChildren ctx children.toList tree targetPos targetEndPos candidateTexts
    | _ => pure ()

  private partial def traverseChildren (ctx : ContextInfo) (children : List InfoTree) (parent : InfoTree)
      (targetPos targetEndPos : Nat) (candidateTexts : List String) : ProbeM Unit := do
    match children with
    | [] => pure ()
    | child :: rest =>
      traverseTree ctx child parent targetPos targetEndPos candidateTexts
      traverseChildren ctx rest parent targetPos targetEndPos candidateTexts
end

private def traverseTopLevel (tree : InfoTree) (targetPos targetEndPos : Nat)
    (candidateTexts : List String) : ProbeM Unit := do
  match tree with
  | .context ctx t =>
    match ctx.mergeIntoOuter? none with
    | some ctx => traverseTree ctx t tree targetPos targetEndPos candidateTexts
    | none => throw <| IO.userError "failed to synthesize top-level ContextInfo"
  | _ => pure ()

private partial def traverseTopLevels (trees : List InfoTree) (targetPos targetEndPos : Nat)
    (candidateTexts : List String) : ProbeM Unit := do
  match trees with
  | [] => pure ()
  | tree :: rest =>
    traverseTopLevel tree targetPos targetEndPos candidateTexts
    traverseTopLevels rest targetPos targetEndPos candidateTexts

unsafe def processFile (path : FilePath) (targetPos targetEndPos : Nat) (output : FilePath)
    (candidateTexts : List String) : IO Unit := do
  let input ← IO.FS.readFile path
  enableInitializersExecution
  let inputCtx := Parser.mkInputContext input path.toString
  let (header, parserState, messages) ← Parser.parseHeader inputCtx
  let (env, messages) ← processHeader header {} messages inputCtx
  if messages.hasErrors then throw <| IO.userError "source import/header elaboration failed"
  let env := env.setMainModule (← moduleNameOfFileName path none)
  let commandState := { Command.mkState env messages {} with infoState.enabled := true }
  let s ← IO.processCommands inputCtx parserState commandState
  let trees : Array InfoTree := s.commandState.infoState.trees.toArray
  let collect : ProbeM Unit := traverseTopLevels trees.toList targetPos targetEndPos candidateTexts
  let pair ← collect.run (#[] : Array WorkerResult)
  let rows : Array WorkerResult := pair.2
  let result : WorkerResult ←
    match rows.toList with
    | [row] => pure row
    | [] => pure { targetFound := false, pos := targetPos, endPos := targetEndPos }
    | _ => throw <| IO.userError s!"ambiguous live TacticInfo target: {rows.size} matches"
  if let some parent := output.parent then IO.FS.createDirAll parent
  IO.FS.writeFile output (toJson result).pretty

end Exp49LiveBranch

open Exp49LiveBranch

unsafe def main (args : List String) : IO Unit := do
  match args with
  | path :: pos :: endPos :: output :: candidates =>
    let some p := pos.toNat? | throw <| IO.userError "invalid target pos"
    let some e := endPos.toNat? | throw <| IO.userError "invalid target endPos"
    processFile ⟨path⟩ p e ⟨output⟩ candidates
  | _ => throw <| IO.userError "usage: <source.lean> <raw-pos> <raw-end-pos> <output.json> <candidate>..."
'''

LEAN_SOURCE_SHA256 = hashlib.sha256(LEAN_SOURCE.encode("utf-8")).hexdigest()


def _endpoint(state: Any, goal_count: Any, kind: str) -> dict[str, Any] | None:
    if state is None:
        return None
    gc = int(goal_count) if isinstance(goal_count, int) else None
    if kind == "text48":
        value = normalize_goal_text(state)
        if gc is None and value == "no goals":
            gc = 0
    elif kind == "struct":
        value = str(state)
    else:
        value = str(state)
    return {
        "schema": STRICT_ENDPOINT_SCHEMA if kind == "struct" else f"exp49-{kind}-endpoint-v1",
        "state": value,
        "goal_count": gc,
        "terminal": bool(gc == 0),
    }


def _endpoint_map(raw: dict[str, Any]) -> dict[str, Any]:
    gc = raw.get("goalCount")
    values = {
        "raw": _endpoint(raw.get("stateAfter"), gc, "raw"),
        "text48": _endpoint(raw.get("stateAfter"), gc, "text48"),
        "struct": _endpoint(raw.get("strictStateAfter"), gc, "struct"),
    }
    return {kind: {"value": ep, "sha256": json_sha256(ep) if ep is not None else None}
            for kind, ep in values.items()}


def _enrich(raw: dict[str, Any], source: str, tactic: str, initial: dict[str, Any]) -> dict[str, Any]:
    out = {
        "source": source,
        "tactic": tactic,
        "head": tactic_head(tactic),
        "family": tactic_family(tactic),
        "executable": raw.get("executable") is True,
        "pre_state": normalize_goal_text(raw.get("preState")),
        "strict_pre_state": raw.get("strictPreState"),
    }
    if out["executable"]:
        endpoints = _endpoint_map(raw)
        out.update({
            "endpoints": endpoints,
            "goal_count": raw.get("goalCount"),
            "terminal": raw.get("goalCount") == 0,
            "no_op": {k: endpoints[k]["value"] == initial[k]["value"] for k in endpoints},
        })
    else:
        out.update({"error_type": "TacticFailureOrParseError", "error": raw.get("error")})
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    inp = read_json(args.input)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    project = Path(inp["project"]).resolve()
    source_file = (project / inp["file_path"]).resolve()
    alternatives = list(inp["alternatives"])
    if len(alternatives) != ALTERNATIVE_BUDGET:
        raise ValueError(f"Exp49 requires exactly {ALTERNATIVE_BUDGET} alternatives")
    if not source_file.is_file() or file_sha256(source_file) != inp["source_file_sha256"]:
        raise ValueError("Exp49 exact source identity failed")

    ast_path, ast_source = resolve_ast_source(
        project, Path(args.raid_data_root).resolve(), inp["slug"], inp["commit"],
        inp["file_path"], inp["source_file_sha256"],
    )
    edge = resolve_target_from_ast(
        ast_path, ast_source, inp["trace_root_state"], inp["authored_tactic"]
    )
    generated_dir = Path(args.generated_dir).resolve()
    generated_dir.mkdir(parents=True, exist_ok=True)
    lean_file = generated_dir / LEAN_FILE_NAME
    if lean_file.exists() and hashlib.sha256(lean_file.read_bytes()).hexdigest() != LEAN_SOURCE_SHA256:
        raise ValueError("generated Exp49 Lean worker source changed")
    if not lean_file.exists():
        lean_file.write_text(LEAN_SOURCE, encoding="utf-8")

    raw_out = output.with_suffix(output.suffix + ".lean.json")
    cmd = [
        "lake", "env", "lean", "--run", str(lean_file), str(source_file),
        str(edge["pos"]), str(edge["end_pos"]), str(raw_out), *alternatives,
    ]
    proc = subprocess.run(
        cmd, cwd=str(project), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=int(args.timeout),
    )
    base: dict[str, Any] = {
        "worker_version": WORKER_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "strict_endpoint_schema": STRICT_ENDPOINT_SCHEMA,
        "lean_source_sha256": LEAN_SOURCE_SHA256,
        "project": str(project), "slug": inp["slug"], "commit": inp["commit"],
        "file_path": inp["file_path"], "full_name": inp["full_name"],
        "source_file": str(source_file), "source_file_sha256": inp["source_file_sha256"],
        "ast_path": str(ast_path), "ast_sha256": file_sha256(ast_path),
        "target_record_index": edge["record_index"], "target_pos": edge["pos"],
        "target_end_pos": edge["end_pos"], "source_tactic_text": edge["source_tactic_text"],
        "authored_tactic": inp["authored_tactic"], "alternative_attempts": len(alternatives),
        "process": {"returncode": proc.returncode, "stdout": proc.stdout[-8000:],
                    "stderr": proc.stderr[-12000:]},
    }
    if proc.returncode != 0 or not raw_out.is_file():
        base.update({"worker_ok": False, "theorem_start_ok": False,
                     "error_type": "LeanProcessFailure",
                     "error": (proc.stderr or proc.stdout)[-12000:], "executions": []})
        atomic_json_dump(base, output)
        return base

    raw = read_json(raw_out)
    initial = {
        "raw": {"value": _endpoint(raw.get("stateBefore"), raw.get("preGoalCount"), "raw")},
        "text48": {"value": _endpoint(raw.get("stateBefore"), raw.get("preGoalCount"), "text48")},
        "struct": {"value": _endpoint(raw.get("strictStateBefore"), raw.get("preGoalCount"), "struct")},
    }
    for value in initial.values():
        value["sha256"] = json_sha256(value["value"])
    original = {
        "raw": {"value": _endpoint(raw.get("originalStateAfter"), raw.get("originalGoalCount"), "raw")},
        "text48": {"value": _endpoint(raw.get("originalStateAfter"), raw.get("originalGoalCount"), "text48")},
        "struct": {"value": _endpoint(raw.get("originalStrictStateAfter"), raw.get("originalGoalCount"), "struct")},
    }
    for value in original.values():
        value["sha256"] = json_sha256(value["value"])

    state_before = raw.get("stateBefore")
    strict_before = raw.get("strictStateBefore")
    root_ok = normalize_goal_text(state_before) == normalize_goal_text(inp["trace_root_state"])
    ast_before_ok = state_before == edge["state_before"]
    ast_after_ok = raw.get("originalStateAfter") == edge["state_after"]
    single_goal_ok = raw.get("preGoalCount") == 1

    authored_raw = dict(raw.get("authored") or {})
    authored = _enrich(authored_raw, "authored", inp["authored_tactic"], initial)
    alternatives_raw = list(raw.get("alternatives") or [])
    executions = [authored]
    for expected, rr0 in zip(alternatives, alternatives_raw):
        rr = dict(rr0)
        executions.append(_enrich(rr, "alternative", expected, initial))

    complete_budget = (
        len(alternatives_raw) == ALTERNATIVE_BUDGET
        and [x.get("tactic") for x in alternatives_raw] == alternatives
    )
    same_pre_text = all(
        normalize_goal_text(x.get("preState")) == normalize_goal_text(state_before)
        for x in [authored_raw, *alternatives_raw]
    )
    same_pre_struct = all(
        x.get("strictPreState") == strict_before for x in [authored_raw, *alternatives_raw]
    )
    authored_text_exact = bool(
        authored.get("executable") and authored.get("endpoints", {}).get("text48", {}).get("value")
        == original["text48"]["value"]
    )
    authored_struct_exact = bool(
        authored.get("executable") and authored.get("endpoints", {}).get("struct", {}).get("value")
        == original["struct"]["value"]
    )
    theorem_start_ok = bool(
        raw.get("targetFound") is True and root_ok and ast_before_ok and ast_after_ok
        and single_goal_ok and strict_before is not None
    )
    worker_ok = bool(
        theorem_start_ok and authored_text_exact and authored_struct_exact
        and complete_budget and same_pre_text and same_pre_struct
    )
    base.update({
        "target_found": raw.get("targetFound"), "pre_goal_count": raw.get("preGoalCount"),
        "single_goal_backend_gate_ok": single_goal_ok,
        "state_before": normalize_goal_text(state_before), "strict_state_before": strict_before,
        "original_state_after": normalize_goal_text(raw.get("originalStateAfter")),
        "original_strict_state_after": raw.get("originalStrictStateAfter"),
        "initial_endpoints": initial, "original_authored_endpoints": original,
        "frozen_trace_root_match": root_ok, "live_state_before_exact_ast": ast_before_ok,
        "live_original_state_after_exact_ast": ast_after_ok,
        "same_pre_state_text_all_branches": same_pre_text,
        "same_pre_state_struct_all_branches": same_pre_struct,
        "theorem_start_ok": theorem_start_ok,
        "authored_replay_text_ok": authored_text_exact,
        "authored_replay_struct_ok": authored_struct_exact,
        "complete_alternative_budget": complete_budget,
        "executions": executions, "worker_ok": worker_ok,
    })
    if not worker_ok:
        base["error_type"] = "Exp49WorkerGateFailure"
        base["error"] = "one or more exact-state or strict-endpoint gates failed"
    atomic_json_dump(base, output)
    return base


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--generated-dir", default="artifacts/v49/candidate_endpoint_robustness/generated")
    p.add_argument("--raid-data-root", default=str(RAID_DATA_ROOT))
    p.add_argument("--timeout", type=int, default=900)
    return p.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps({
        "worker_ok": result.get("worker_ok"),
        "theorem_start_ok": result.get("theorem_start_ok"),
        "authored_replay_text_ok": result.get("authored_replay_text_ok"),
        "authored_replay_struct_ok": result.get("authored_replay_struct_ok"),
        "complete_alternative_budget": result.get("complete_alternative_budget"),
        "full_name": result.get("full_name"),
    }, ensure_ascii=False))
