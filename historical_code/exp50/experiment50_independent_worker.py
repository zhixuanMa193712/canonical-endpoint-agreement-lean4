"""Standalone live-TacticInfo worker for Exp50.

This implementation imports no Exp48/Exp49 worker.  It accepts a frozen raw
source span, elaborates the unchanged source, locates one live TacticInfo node,
validates authored replay, and evaluates the supplied candidates as independent
branches.  Large states are moved to Exp50's content-addressed store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from experiment50_protocol import (
    PROTOCOL_VERSION,
    RAID_DATA_ROOT,
    STRICT_ENDPOINT_SCHEMA,
    WORKER_SCHEMA,
    atomic_json_dump,
    compact_endpoint,
    endpoint_payload,
    file_sha256,
    json_sha256,
    normalize_goal_text,
    read_json,
    store_text,
    tactic_family,
    tactic_head,
    tail_text,
)

WORKER_VERSION = "experiment50-independent-live-worker-v1"
LEAN_FILE_NAME = "Experiment50IndependentWorker.lean"

LEAN_SOURCE = r'''
import Lean
import Lake

open Lean Elab System
set_option maxHeartbeats 2000000

instance : ToJson String.Pos.Raw where
  toJson n := toJson n.1

namespace Exp50Independent

namespace TextState

private def newlineIfNeeded (s : String) : String := if s.isEmpty then s else s ++ "\n"

private def renderGoal (goal : MVarId) : MetaM String := do
  let mctx ← getMCtx
  match mctx.findDecl? goal with
  | none => return "unknown goal"
  | some md =>
    let indent := 2
    let clean := md.lctx.sanitizeNames.run' { options := (← getOptions) }
    Meta.withLCtx clean md.localInstances do
      let rec flush (names : List Name) (ty? : Option Expr) (out : String) : MetaM String := do
        if names.isEmpty then return out
        let out := newlineIfNeeded out
        match ty? with
        | none => return out
        | some ty =>
          let fmt ← Meta.ppExpr ty
          return (out ++ (Format.joinSep names.reverse (format " ") ++ " :" ++
            Format.nest indent (Format.line ++ fmt)).group).pretty
      let rec addDecl (names : List Name) (previous? : Option Expr) (out : String)
          (decl : LocalDecl) : MetaM (List Name × Option Expr × String) := do
        match decl with
        | .cdecl _ _ user ty _ _ =>
          let user := user.simpMacroScopes
          let ty ← instantiateMVars ty
          if previous? == none || previous? == some ty then
            return (user :: names, some ty, out)
          let out ← flush names previous? out
          return ([user], some ty, out)
        | .ldecl _ _ user ty val _ _ =>
          let user := user.simpMacroScopes
          let out ← flush names previous? out
          let out := newlineIfNeeded out
          let tyFmt ← Meta.ppExpr (← instantiateMVars ty)
          let valFmt ← Meta.ppExpr (← instantiateMVars val)
          return ([], none, out ++ (format user ++ " : " ++ tyFmt ++ " :=" ++
            Format.nest indent (Format.line ++ valFmt)).group.pretty)
      let (names, ty?, out) ← clean.foldlM (init := ([], none, "")) fun acc decl =>
        if decl.isAuxDecl || decl.isImplementationDetail then pure acc
        else addDecl acc.1 acc.2.1 acc.2.2 decl
      let out ← flush names ty? out
      let target ← Meta.ppExpr (← instantiateMVars md.type)
      let rendered := out ++ "\n" ++ (Meta.getGoalPrefix md ++ Format.nest indent target).pretty
      match md.userName with
      | Name.anonymous => return rendered
      | n => return "case " ++ n.eraseMacroScopes.toString ++ "\n" ++ rendered

def renderM (goals : List MVarId) : MetaM String := do
  if goals.isEmpty then return "no goals"
  return (String.intercalate "\n\n" (← goals.mapM renderGoal)).trimAscii.toString

def render (ctx : ContextInfo) (goals : List MVarId) : IO String :=
  if goals.isEmpty then pure "no goals" else ctx.runMetaM {} (renderM goals)

end TextState

namespace Structural

structure Renaming where
  emvars : List MVarId := []
  lmvars : List LMVarId := []
  lparams : List Name := []
  externalFVars : List FVarId := []
deriving Inhabited

abbrev EncodeM := StateT Renaming MetaM

private def indexOf? [BEq α] (needle : α) : List α → Option Nat
  | [] => none
  | x :: xs => if x == needle then some 0 else (indexOf? needle xs).map Nat.succ

private def sexp (tag : String) (parts : List String) : String :=
  "(" ++ tag ++ (if parts.isEmpty then "" else " " ++ String.intercalate " " parts) ++ ")"

private def q (s : String) : String := reprStr s

private def binder : BinderInfo → String
  | .default => "explicit"
  | .implicit => "implicit"
  | .strictImplicit => "strictImplicit"
  | .instImplicit => "instImplicit"

private def localKind : LocalDeclKind → String
  | .default => "default"
  | .implDetail => "implDetail"
  | .auxDecl => "auxDecl"

private def metaKind : MetavarKind → String
  | .natural => "natural"
  | .synthetic => "synthetic"
  | .syntheticOpaque => "syntheticOpaque"

private def levelMVarNumber (id : LMVarId) : EncodeM Nat := do
  let s ← get
  match indexOf? id s.lmvars with
  | some i => pure i
  | none =>
    let i := s.lmvars.length
    set { s with lmvars := s.lmvars ++ [id] }
    pure i

private def levelParamNumber (id : Name) : EncodeM Nat := do
  let s ← get
  match indexOf? id s.lparams with
  | some i => pure i
  | none =>
    let i := s.lparams.length
    set { s with lparams := s.lparams ++ [id] }
    pure i

private partial def encodeLevel : Level → EncodeM String
  | .zero => pure "L0"
  | .succ x => return sexp "LS" [← encodeLevel x]
  | .max x y => return sexp "LMAX" [← encodeLevel x, ← encodeLevel y]
  | .imax x y => return sexp "LIMAX" [← encodeLevel x, ← encodeLevel y]
  | .param n => return sexp "LP" [toString (← levelParamNumber n)]
  | .mvar id => do
    let assigned? ← getLevelMVarAssignment? id
    match assigned? with
    | some value => encodeLevel value
    | none => return sexp "LM" [toString (← levelMVarNumber id)]

private def encodeFVar (locals : List FVarId) (id : FVarId) : EncodeM String := do
  match indexOf? id locals with
  | some i => return "L" ++ toString i
  | none =>
    let s ← get
    match indexOf? id s.externalFVars with
    | some i => return "X" ++ toString i
    | none =>
      let i := s.externalFVars.length
      set { s with externalFVars := s.externalFVars ++ [id] }
      return "X" ++ toString i

private partial def encodeExpr (locals : List FVarId) (e : Expr) : EncodeM String := do
  match e with
  | .bvar i => return sexp "B" [toString i]
  | .fvar id => return sexp "F" [← encodeFVar locals id]
  | .mvar id =>
    let assigned? ← getExprMVarAssignment? id
    match assigned? with
    | some value => encodeExpr locals value
    | none =>
      let s ← get
      match indexOf? id s.emvars with
      | some i => return sexp "MREF" [toString i]
      | none =>
        let i := s.emvars.length
        set { s with emvars := s.emvars ++ [id] }
        let mctx ← getMCtx
        match mctx.findDecl? id with
        | none => return sexp "M" [toString i, "missing"]
        | some md =>
          let allowed ← md.lctx.getFVarIds.toList.mapM (encodeFVar locals)
          let instances ← md.localInstances.toList.mapM fun inst => do
            return sexp "INSTANCE" [q inst.className.toString, ← encodeExpr locals inst.fvar]
          let ty ← encodeExpr locals md.type
          return sexp "M" [toString i, metaKind md.kind, toString md.lctx.size,
            toString md.numScopeArgs, sexp "MCTX" allowed, sexp "MINST" instances, ty]
  | .sort u => return sexp "SORT" [← encodeLevel u]
  | .const n us => return sexp "CONST" [q n.toString, sexp "LEVELS" (← us.mapM encodeLevel)]
  | .app f a => return sexp "APP" [← encodeExpr locals f, ← encodeExpr locals a]
  | .lam _ ty body bi => return sexp "LAM" [binder bi, ← encodeExpr locals ty, ← encodeExpr locals body]
  | .forallE _ ty body bi => return sexp "FORALL" [binder bi, ← encodeExpr locals ty, ← encodeExpr locals body]
  | .letE _ ty value body nondep => return sexp "LET" [toString nondep,
      ← encodeExpr locals ty, ← encodeExpr locals value, ← encodeExpr locals body]
  | .lit lit => return sexp "LIT" [q (reprStr lit)]
  | .mdata _ body => encodeExpr locals body
  | .proj n i body => return sexp "PROJ" [q n.toString, toString i, ← encodeExpr locals body]

private def registered (md : MetavarDecl) (id : FVarId) : Bool :=
  md.localInstances.any fun inst =>
    match inst.fvar with
    | .fvar other => other == id
    | _ => false

private def encodeLocal (md : MetavarDecl) (locals : List FVarId)
    (decl : LocalDecl) : EncodeM String := do
  match decl with
  | .cdecl _ id _ ty bi kind =>
    return sexp "LOCAL" ["cdecl", ← encodeFVar locals id, binder bi, localKind kind,
      toString (registered md id), ← encodeExpr locals ty]
  | .ldecl _ id _ ty value nondep kind =>
    return sexp "LOCAL" ["ldecl", ← encodeFVar locals id, localKind kind,
      toString nondep, toString (registered md id), ← encodeExpr locals ty,
      ← encodeExpr locals value]

private def encodeGoal (id : MVarId) : EncodeM String := do
  let mctx ← getMCtx
  match mctx.findDecl? id with
  | none => return sexp "GOAL" ["missing"]
  | some md =>
    let locals := md.lctx.getFVarIds.toList
    let declarations ← md.lctx.foldlM (init := ([] : List String)) fun out decl => do
      return out ++ [← encodeLocal md locals decl]
    let instances ← md.localInstances.toList.mapM fun inst => do
      return sexp "INSTANCE" [q inst.className.toString, ← encodeExpr locals inst.fvar]
    let target ← encodeExpr locals md.type
    return sexp "GOAL" [metaKind md.kind, toString md.numScopeArgs,
      sexp "INSTANCES" instances, sexp "LOCALS" declarations, sexp "TARGET" [target]]

def encodeM (goals : List MVarId) : MetaM String := do
  let action : EncodeM (List String) := goals.mapM encodeGoal
  let result ← action.run {}
  return sexp "STATE" [sexp "GOALS" result.1]

def encode (ctx : ContextInfo) (goals : List MVarId) : IO String :=
  ctx.runMetaM {} (encodeM goals)

end Structural

structure Branch where
  tactic : String
  executable : Bool
  preText : String
  preStruct : String
  afterText : Option String := none
  afterStruct : Option String := none
  goalCount : Option Nat := none
  error : Option String := none
deriving ToJson

structure Result where
  targetFound : Bool
  pos : Nat
  endPos : Nat
  preGoalCount : Option Nat := none
  beforeText : Option String := none
  beforeStruct : Option String := none
  originalAfterText : Option String := none
  originalAfterStruct : Option String := none
  originalGoalCount : Option Nat := none
  authored : Option Branch := none
  candidates : Array Branch := #[]
deriving ToJson

def runSyntax (ctx : ContextInfo) (ti : TacticInfo) (label : String) (stx : Syntax) : IO Branch := do
  let beforeCtx := { ctx with mctx := ti.mctxBefore }
  let preText ← TextState.render beforeCtx ti.goalsBefore
  let preStruct ← Structural.encode beforeCtx ti.goalsBefore
  try
    let value ← beforeCtx.runMetaM {} do
      let [goal] := ti.goalsBefore | throwError "Exp50 requires one pre-state goal"
      let action : Term.TermElabM (List MVarId) := Tactic.run goal (Tactic.evalTactic stx)
      let (after, _) ← liftM (m := MetaM) <|
        Term.TermElabM.run action ({} : Term.Context) ({} : Term.State)
      let text ← TextState.renderM after
      let structural ← Structural.encodeM after
      pure (text, structural, after.length)
    return {
      tactic := label
      executable := true
      preText := preText
      preStruct := preStruct
      afterText := some value.1
      afterStruct := some value.2.1
      goalCount := some value.2.2
    }
  catch ex =>
    return {
      tactic := label
      executable := false
      preText := preText
      preStruct := preStruct
      error := some (toString ex)
    }

def runText (ctx : ContextInfo) (ti : TacticInfo) (text : String) : IO Branch := do
  match Parser.runParserCategory ctx.env `tactic text with
  | .ok stx => runSyntax ctx ti text stx
  | .error err =>
    let beforeCtx := { ctx with mctx := ti.mctxBefore }
    return {
      tactic := text
      executable := false
      preText := (← TextState.render beforeCtx ti.goalsBefore)
      preStruct := (← Structural.encode beforeCtx ti.goalsBefore)
      error := some ("parse: " ++ err)
    }

private partial def runTexts (ctx : ContextInfo) (ti : TacticInfo)
    (texts : List String) (out : Array Branch) : IO (Array Branch) := do
  match texts with
  | [] => pure out
  | text :: rest => runTexts ctx ti rest (out.push (← runText ctx ti text))

abbrev CollectM := StateT (Array Result) IO

private def inspectTactic (ctx : ContextInfo) (ti : TacticInfo) (parent : InfoTree)
    (targetPos targetEnd : Nat) (texts : List String) : CollectM Unit := do
  match parent with
  | .node (Info.ofTacticInfo parentTi) _ =>
    match parentTi.stx.getKind with
    | ``Lean.Parser.Tactic.tacticSeq1Indented
    | ``Lean.Parser.Tactic.tacticSeqBracketed
    | ``Lean.Parser.Tactic.rewriteSeq =>
      let some start := ti.stx.getPos? true | pure ()
      let some finish := ti.stx.getTailPos? true | pure ()
      if start.1 != targetPos || finish.1 != targetEnd then pure ()
      else
        let beforeCtx := { ctx with mctx := ti.mctxBefore }
        let afterCtx := { ctx with mctx := ti.mctxAfter }
        let beforeText ← TextState.render beforeCtx ti.goalsBefore
        let beforeStruct ← Structural.encode beforeCtx ti.goalsBefore
        let afterText ← TextState.render afterCtx ti.goalsAfter
        let afterStruct ← Structural.encode afterCtx ti.goalsAfter
        let authored ← runSyntax ctx ti "<authored>" ti.stx
        let candidates ← runTexts ctx ti texts #[]
        modify fun out => out.push {
          targetFound := true
          pos := targetPos
          endPos := targetEnd
          preGoalCount := some ti.goalsBefore.length
          beforeText := some beforeText
          beforeStruct := some beforeStruct
          originalAfterText := some afterText
          originalAfterStruct := some afterStruct
          originalGoalCount := some ti.goalsAfter.length
          authored := some authored
          candidates := candidates
        }
    | _ => pure ()
  | _ => pure ()

mutual
  private partial def walk (ctx : ContextInfo) (tree parent : InfoTree)
      (start finish : Nat) (texts : List String) : CollectM Unit := do
    match tree with
    | .context inner child =>
      match inner.mergeIntoOuter? ctx with
      | some merged => walk merged child tree start finish texts
      | none => throw <| IO.userError "Exp50 ContextInfo merge failed"
    | .node info children =>
      match info with
      | .ofTacticInfo ti => inspectTactic ctx ti parent start finish texts
      | _ => pure ()
      walkChildren ctx children.toList tree start finish texts
    | _ => pure ()

  private partial def walkChildren (ctx : ContextInfo) (children : List InfoTree)
      (parent : InfoTree) (start finish : Nat) (texts : List String) : CollectM Unit := do
    match children with
    | [] => pure ()
    | child :: rest =>
      walk ctx child parent start finish texts
      walkChildren ctx rest parent start finish texts
end

private def walkTop (tree : InfoTree) (start finish : Nat) (texts : List String) : CollectM Unit := do
  match tree with
  | .context ctx child =>
    match ctx.mergeIntoOuter? none with
    | some merged => walk merged child tree start finish texts
    | none => throw <| IO.userError "Exp50 top-level ContextInfo merge failed"
  | _ => pure ()

private partial def walkTops (trees : List InfoTree) (start finish : Nat)
    (texts : List String) : CollectM Unit := do
  match trees with
  | [] => pure ()
  | tree :: rest =>
    walkTop tree start finish texts
    walkTops rest start finish texts

unsafe def elaborate (source : FilePath) (start finish : Nat) (output : FilePath)
    (texts : List String) : IO Unit := do
  let input ← IO.FS.readFile source
  enableInitializersExecution
  let inputCtx := Parser.mkInputContext input source.toString
  let (header, parserState, messages) ← Parser.parseHeader inputCtx
  let (env, messages) ← processHeader header {} messages inputCtx
  if messages.hasErrors then throw <| IO.userError "Exp50 source header failed"
  let env := env.setMainModule (← moduleNameOfFileName source none)
  let commandState := { Command.mkState env messages {} with infoState.enabled := true }
  let final ← IO.processCommands inputCtx parserState commandState
  let action : CollectM Unit := walkTops final.commandState.infoState.trees.toArray.toList start finish texts
  let collected ← action.run (#[] : Array Result)
  let result : Result ←
    match collected.2.toList with
    | [row] => pure row
    | [] => pure { targetFound := false, pos := start, endPos := finish }
    | rows => throw <| IO.userError s!"Exp50 ambiguous TacticInfo target: {rows.length}"
  if let some parent := output.parent then IO.FS.createDirAll parent
  IO.FS.writeFile output (toJson result).pretty

end Exp50Independent

open Exp50Independent

unsafe def main (args : List String) : IO Unit := do
  match args with
  | source :: start :: finish :: output :: candidates =>
    let some p := start.toNat? | throw <| IO.userError "bad start position"
    let some q := finish.toNat? | throw <| IO.userError "bad end position"
    elaborate ⟨source⟩ p q ⟨output⟩ candidates
  | _ => throw <| IO.userError "usage: <source> <start> <finish> <output> <candidate>..."
'''

LEAN_SOURCE_SHA256 = hashlib.sha256(LEAN_SOURCE.encode("utf-8")).hexdigest()


def _compact_branch(root: Path, raw: dict[str, Any], source: str, tactic: str,
                    initial: dict[str, Any], frozen_position: int | None = None,
                    execution_order_index: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source": source, "tactic": tactic, "head": tactic_head(tactic),
        "family": tactic_family(tactic), "attempted": True,
        "candidate_position_frozen": frozen_position,
        "execution_order_index": execution_order_index,
        "executable": raw.get("executable") is True,
        "pre_text_sha256": hashlib.sha256(normalize_goal_text(raw.get("preText")).encode()).hexdigest(),
        "pre_struct_sha256": hashlib.sha256(str(raw.get("preStruct") or "").encode()).hexdigest(),
    }
    if out["executable"]:
        gc = int(raw["goalCount"])
        payload = endpoint_payload(str(raw["afterText"]), str(raw["afterStruct"]), gc)
        out["endpoints"] = compact_endpoint(root, payload)
        out["goal_count"] = gc
        out["terminal"] = gc == 0
        out["no_op"] = {
            kind: out["endpoints"][kind]["sha256"] == initial[kind]["sha256"]
            for kind in ("raw", "text48", "struct")
        }
    else:
        error = str(raw.get("error") or "")
        out["failure_category"] = "parse" if error.startswith("parse:") else "tactic_failure"
        out["diagnostic"] = store_text(root, "diagnostic", error)
    out["record_sha256"] = json_sha256_without_self(out)
    return out


def json_sha256_without_self(value: dict[str, Any]) -> str:
    return json_sha256({k: v for k, v in value.items() if k != "record_sha256"})


def run(args: argparse.Namespace) -> dict[str, Any]:
    inp = read_json(args.input)
    root = Path(inp["artifact_root"]).resolve()
    output = Path(args.output).resolve()
    project = Path(inp["project"]).resolve()
    source = (project / inp["file_path"]).resolve()
    candidates = list(inp["candidates"])
    frozen_positions = list(inp["candidate_positions_frozen"])
    if not candidates:
        raise ValueError("Exp50 worker requires at least one candidate")
    if len(frozen_positions) != len(candidates):
        raise ValueError("candidate position metadata mismatch")
    if not source.is_file() or file_sha256(source) != inp["source_file_sha256"]:
        raise ValueError("Exp50 source identity mismatch")
    generated = Path(args.generated_dir).resolve()
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / LEAN_FILE_NAME
    if lean_file.exists() and hashlib.sha256(lean_file.read_bytes()).hexdigest() != LEAN_SOURCE_SHA256:
        raise ValueError("generated independent Lean worker changed")
    if not lean_file.exists():
        lean_file.write_text(LEAN_SOURCE, encoding="utf-8")
    raw_out = output.with_suffix(output.suffix + ".temporary-lean.json")
    cmd = ["lake", "env", "lean", "--run", str(lean_file), str(source),
           str(inp["target_pos"]), str(inp["target_end_pos"]), str(raw_out), *candidates]
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=project, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=int(args.timeout))
        process = {"returncode": proc.returncode,
                   "resource_limit_status": "normal_exit" if proc.returncode == 0 else "nonzero_exit",
                   "stdout": store_text(root, "process_stdout", proc.stdout),
                   "stderr": store_text(root, "process_stderr", proc.stderr),
                   "stdout_tail": proc.stdout[-4000:], "stderr_tail": proc.stderr[-8000:]}
    except subprocess.TimeoutExpired as exc:
        process = {"returncode": None, "timeout": True,
                   "resource_limit_status": "timeout",
                   "stdout": store_text(root, "process_stdout", tail_text(exc.stdout, 1 << 20)),
                   "stderr": store_text(root, "process_stderr", tail_text(exc.stderr, 1 << 20)),
                   "stdout_tail": tail_text(exc.stdout, 4000),
                   "stderr_tail": tail_text(exc.stderr, 8000)}
    elapsed = time.monotonic() - started
    base: dict[str, Any] = {
        "schema": WORKER_SCHEMA, "version": 1, "protocol_version": PROTOCOL_VERSION,
        "worker_version": WORKER_VERSION,
        "lean_source_sha256": LEAN_SOURCE_SHA256, "mode": inp["mode"],
        "config_sha256": inp["config_sha256"],
        "environment_receipt_sha256": inp["environment_receipt_sha256"],
        "execution_record_id": inp["execution_record_id"],
        "slug": inp["slug"], "commit": inp["commit"], "file_path": inp["file_path"],
        "full_name": inp["full_name"], "theorem_id": inp["theorem_id"],
        "source_file_sha256": inp["source_file_sha256"],
        "trace_root_state_sha256": inp["trace_root_state_sha256"],
        "target_pos": inp["target_pos"], "target_end_pos": inp["target_end_pos"],
        "ast_sha256": inp["ast_sha256"],
        "candidate_order": candidates, "candidate_order_sha256": json_sha256(candidates),
        "process": process, "elapsed_seconds_descriptive": elapsed,
    }
    if process.get("returncode") != 0 or not raw_out.is_file():
        base.update({"worker_ok": False, "error_type": "lean_process_failure",
                     "candidates": []})
        base["record_sha256"] = json_sha256_without_self(base)
        atomic_json_dump(base, output)
        return base
    raw = read_json(raw_out)
    raw_out.unlink(missing_ok=True)
    before_text = str(raw.get("beforeText") or "")
    before_struct = str(raw.get("beforeStruct") or "")
    pre_gc = int(raw.get("preGoalCount") or 0)
    initial_payload = endpoint_payload(before_text, before_struct, pre_gc)
    initial = compact_endpoint(root, initial_payload)
    original_payload = endpoint_payload(
        str(raw.get("originalAfterText") or ""), str(raw.get("originalAfterStruct") or ""),
        int(raw.get("originalGoalCount") or 0),
    )
    original = compact_endpoint(root, original_payload)
    authored_raw = dict(raw.get("authored") or {})
    authored = _compact_branch(root, authored_raw, "authored", inp["authored_tactic"], initial)
    candidate_raw = list(raw.get("candidates") or [])
    branches = [_compact_branch(root, rr, "candidate", expected, initial,
                                frozen_position=frozen_positions[index],
                                execution_order_index=index)
                for index, (expected, rr) in enumerate(zip(candidates, candidate_raw))]
    pre_text_sha = hashlib.sha256(normalize_goal_text(before_text).encode()).hexdigest()
    pre_struct_sha = hashlib.sha256(before_struct.encode()).hexdigest()
    same_pre = all(x["pre_text_sha256"] == pre_text_sha and
                   x["pre_struct_sha256"] == pre_struct_sha for x in [authored, *branches])
    complete = len(candidate_raw) == len(candidates) and [x.get("tactic") for x in candidate_raw] == candidates
    authored_ok = bool(authored.get("executable") and
                       authored["endpoints"]["text48"]["sha256"] == original["text48"]["sha256"] and
                       authored["endpoints"]["struct"]["sha256"] == original["struct"]["sha256"])
    root_ok = normalize_goal_text(before_text) == normalize_goal_text(inp["trace_root_state"])
    worker_ok = bool(raw.get("targetFound") is True and pre_gc == 1 and root_ok and
                     authored_ok and complete and same_pre)
    base.update({
        "target_found": raw.get("targetFound"), "pre_goal_count": pre_gc,
        "trace_root_match": root_ok, "initial_endpoints": initial,
        "live_tacticinfo_prestate_identity": {
            "source": "ContextInfo with TacticInfo.mctxBefore and TacticInfo.goalsBefore",
            "raw_goal_state_sha256": initial["raw"]["state"]["sha256"],
            "text48_endpoint_sha256": initial["text48"]["sha256"],
            "strict_goal_structure_sha256": initial["struct"]["sha256"],
            "goals_before_count": pre_gc,
        },
        "original_authored_endpoints": original, "authored": authored,
        "candidates": branches, "authored_replay_ok": authored_ok,
        "same_pre_state_all_branches": same_pre, "complete_candidate_order": complete,
        "worker_ok": worker_ok,
    })
    base["record_sha256"] = json_sha256_without_self(base)
    atomic_json_dump(base, output)
    return base


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--generated-dir", required=True)
    p.add_argument("--raid-data-root", default=str(RAID_DATA_ROOT))
    p.add_argument("--timeout", type=int, default=900)
    return p.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps({"worker_ok": result.get("worker_ok"), "mode": result.get("mode"),
                      "full_name": result.get("full_name"),
                      "candidates": len(result.get("candidates", []))}, ensure_ascii=False))
