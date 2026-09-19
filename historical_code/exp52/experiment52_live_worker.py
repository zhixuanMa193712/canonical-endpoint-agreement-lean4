"""Execute one frozen Exp52 continuation cell in one fresh Lean process.

A cell is exactly ``(root, pair-role, side, probe, repeat-kind)``.  The Lean
process reconstructs the original live ``TacticInfo`` state, executes the
frozen Exp51 candidate, compares its exact raw and structural post-state with
the archived Exp51 state *inside Lean*, and executes one probe only after that
comparison succeeds.  Python then independently verifies raw, text48, and
strict endpoint hashes against the immutable Exp51 row.

There is no retry path in this worker.  Timeout and process failures are
retained as first-attempt scientific records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

from alignment_protocol import (
    EXECUTION_ALIGNMENT_VERSION,
    EXECUTION_FIX_ID,
    EXP52_WORKER_VERSION,
    CHECKPOINT_COMPACT_SCHEMA,
    CHECKPOINT_RAW_SCHEMA,
    INPUT_SCHEMA,
    LEAN_TIMEOUT_SECONDS,
    SCIENTIFIC_ROOT,
    WORKER_SCHEMA,
    atomic_json_dump,
    base,
    base_worker,
    file_sha256,
    hydrate_text,
    json_sha256,
    read_json,
    validate_amendment,
)


LEAN_FILE_NAME = "Experiment52LiveContinuationWorker.lean"

# Reuse the exact Exp51 text renderer and strict serializer.  The split point
# precedes Exp51's branch runner and leaves namespace Exp51Independent open.
_LEAN_PREFIX, _separator, _unused = base_worker.LEAN_SOURCE.partition(
    "structure Branch where"
)
if not _separator:
    raise RuntimeError("locked Exp51 Lean worker layout changed")

LEAN_SOURCE = _LEAN_PREFIX + r'''
structure Step where
  executable : Bool
  afterText : Option String := none
  afterStruct : Option String := none
  goalCount : Option Nat := none
  error : Option String := none
deriving ToJson

structure RunValue where
  candidateText : String
  candidateStruct : String
  candidateGoalCount : Nat
  reconstructionMatched : Bool
  probeAttempted : Bool
  probe : Step

structure CandidateCheckpoint where
  schema : String := "experiment52-candidate-checkpoint-raw-fix3-v1"
  beforeText : String
  beforeStruct : String
  preGoalCount : Nat
  candidateText : String
  candidateStruct : String
  candidateGoalCount : Nat
  reconstructionMatched : Bool
  probeInvocationNext : Bool
deriving ToJson

structure CellResult where
  targetFound : Bool
  pos : Nat
  endPos : Nat
  preGoalCount : Option Nat := none
  beforeText : Option String := none
  beforeStruct : Option String := none
  candidate : Step := { executable := false }
  reconstructionMatched : Bool := false
  probeAttempted : Bool := false
  probe : Step := { executable := false }
deriving ToJson

def failedStep (message : String) : Step := {
  executable := false
  error := some message
}

def runCandidate (ctx : ContextInfo) (ti : TacticInfo)
    (candidateText probeText expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) (candidateStx : Syntax)
    (probeParsed : Except String Syntax)
    (checkpointPath : FilePath) : IO CellResult := do
  let beforeCtx := { ctx with mctx := ti.mctxBefore }
  let preText ← TextState.render beforeCtx ti.goalsBefore
  let preStruct ← Structural.encode beforeCtx ti.goalsBefore
  try
    let value ← beforeCtx.runMetaM {} do
      let [goal] := ti.goalsBefore
        | throwError "Exp52 requires one original pre-state goal"
      let action : Term.TermElabM RunValue := do
        let afterCandidate ←
          Tactic.run goal (Tactic.evalTactic candidateStx)
        let candidateRendered ← liftM (m := MetaM) do
          let text ← TextState.renderM afterCandidate
          let structural ← Structural.encodeM afterCandidate
          pure (text, structural)
        let matched :=
          candidateRendered.1 == expectedRaw &&
          candidateRendered.2 == expectedStruct &&
          afterCandidate.length == expectedGoalCount
        if !matched then
          pure {
            candidateText := candidateRendered.1
            candidateStruct := candidateRendered.2
            candidateGoalCount := afterCandidate.length
            reconstructionMatched := false
            probeAttempted := false
            probe := failedStep "probe prohibited: candidate post-state mismatch"
          }
        else
          let checkpoint : CandidateCheckpoint := {
            beforeText := preText
            beforeStruct := preStruct
            preGoalCount := ti.goalsBefore.length
            candidateText := candidateRendered.1
            candidateStruct := candidateRendered.2
            candidateGoalCount := afterCandidate.length
            reconstructionMatched := true
            probeInvocationNext := true
          }
          liftM (m := IO) <| do
            if let some parent := checkpointPath.parent then
              IO.FS.createDirAll parent
            let temporary : FilePath := ⟨checkpointPath.toString ++ ".tmp"⟩
            IO.FS.writeFile temporary (toJson checkpoint).pretty
            IO.FS.rename temporary checkpointPath
          match probeParsed with
          | .error message =>
            pure {
              candidateText := candidateRendered.1
              candidateStruct := candidateRendered.2
              candidateGoalCount := afterCandidate.length
              reconstructionMatched := true
              probeAttempted := true
              probe := failedStep ("parse: " ++ message)
            }
          | .ok probeStx =>
            if afterCandidate.isEmpty then
              pure {
                candidateText := candidateRendered.1
                candidateStruct := candidateRendered.2
                candidateGoalCount := 0
                reconstructionMatched := true
                probeAttempted := false
                probe := failedStep "probe prohibited: candidate endpoint is terminal"
              }
            else
              let probeResult : Step ←
                try
                  let afterProbe ← Tactic.run afterCandidate.head! do
                    Tactic.setGoals afterCandidate
                    Tactic.evalTactic probeStx
                  let rendered ← liftM (m := MetaM) do
                    let text ← TextState.renderM afterProbe
                    let structural ← Structural.encodeM afterProbe
                    pure (text, structural)
                  pure {
                    executable := true
                    afterText := some rendered.1
                    afterStruct := some rendered.2
                    goalCount := some afterProbe.length
                  }
                catch ex =>
                  let message ← liftM (m := BaseIO) ex.toMessageData.toString
                  pure (failedStep message)
              pure {
                candidateText := candidateRendered.1
                candidateStruct := candidateRendered.2
                candidateGoalCount := afterCandidate.length
                reconstructionMatched := true
                probeAttempted := true
                probe := probeResult
              }
      let (result, _) ← liftM (m := MetaM) <|
        Term.TermElabM.run action ({} : Term.Context) ({} : Term.State)
      pure result
    return {
      targetFound := true
      pos := ti.stx.getPos?.map (·.1) |>.getD 0
      endPos := ti.stx.getTailPos?.map (·.1) |>.getD 0
      preGoalCount := some ti.goalsBefore.length
      beforeText := some preText
      beforeStruct := some preStruct
      candidate := {
        executable := true
        afterText := some value.candidateText
        afterStruct := some value.candidateStruct
        goalCount := some value.candidateGoalCount
      }
      reconstructionMatched := value.reconstructionMatched
      probeAttempted := value.probeAttempted
      probe := value.probe
    }
  catch ex =>
    return {
      targetFound := true
      pos := ti.stx.getPos?.map (·.1) |>.getD 0
      endPos := ti.stx.getTailPos?.map (·.1) |>.getD 0
      preGoalCount := some ti.goalsBefore.length
      beforeText := some preText
      beforeStruct := some preStruct
      candidate := failedStep (toString ex)
      probe := failedStep "probe prohibited: candidate execution failed"
    }

def runTexts (ctx : ContextInfo) (ti : TacticInfo)
    (candidateText probeText expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) (checkpointPath : FilePath) : IO CellResult := do
  match Parser.runParserCategory ctx.env `tactic candidateText with
  | .error message =>
    let beforeCtx := { ctx with mctx := ti.mctxBefore }
    return {
      targetFound := true
      pos := ti.stx.getPos?.map (·.1) |>.getD 0
      endPos := ti.stx.getTailPos?.map (·.1) |>.getD 0
      preGoalCount := some ti.goalsBefore.length
      beforeText := some (← TextState.render beforeCtx ti.goalsBefore)
      beforeStruct := some (← Structural.encode beforeCtx ti.goalsBefore)
      candidate := failedStep ("parse: " ++ message)
      probe := failedStep "probe prohibited: candidate parse failed"
    }
  | .ok candidateStx =>
    runCandidate ctx ti candidateText probeText expectedRaw expectedStruct
      expectedGoalCount candidateStx
      (Parser.runParserCategory ctx.env `tactic probeText) checkpointPath

abbrev CollectM := StateT (Array CellResult) IO

private def inspectTactic (ctx : ContextInfo) (ti : TacticInfo)
    (parent : InfoTree) (targetPos targetEnd : Nat)
    (candidate probe expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) (checkpointPath : FilePath) : CollectM Unit := do
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
        let row ← runTexts ctx ti candidate probe expectedRaw expectedStruct
          expectedGoalCount checkpointPath
        modify fun out => out.push row
    | _ => pure ()
  | _ => pure ()

mutual
  private partial def walk (ctx : ContextInfo) (tree parent : InfoTree)
      (start finish : Nat) (candidate probe expectedRaw expectedStruct : String)
      (expectedGoalCount : Nat) (checkpointPath : FilePath) : CollectM Unit := do
    match tree with
    | .context inner child =>
      match inner.mergeIntoOuter? ctx with
      | some merged => walk merged child tree start finish candidate probe expectedRaw expectedStruct expectedGoalCount checkpointPath
      | none => throw <| IO.userError "Exp52 ContextInfo merge failed"
    | .node info children =>
      match info with
      | .ofTacticInfo ti => inspectTactic ctx ti parent start finish candidate probe expectedRaw expectedStruct expectedGoalCount checkpointPath
      | _ => pure ()
      walkChildren ctx children.toList tree start finish candidate probe expectedRaw expectedStruct expectedGoalCount checkpointPath
    | _ => pure ()

  private partial def walkChildren (ctx : ContextInfo)
      (children : List InfoTree) (parent : InfoTree) (start finish : Nat)
      (candidate probe expectedRaw expectedStruct : String)
      (expectedGoalCount : Nat) (checkpointPath : FilePath) : CollectM Unit := do
    match children with
    | [] => pure ()
    | child :: rest =>
      walk ctx child parent start finish candidate probe expectedRaw expectedStruct expectedGoalCount checkpointPath
      walkChildren ctx rest parent start finish candidate probe expectedRaw expectedStruct expectedGoalCount checkpointPath
end

private def walkTop (tree : InfoTree) (start finish : Nat)
    (candidate probe expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) (checkpointPath : FilePath) : CollectM Unit := do
  match tree with
  | .context ctx child =>
    match ctx.mergeIntoOuter? none with
    | some merged => walk merged child tree start finish candidate probe expectedRaw expectedStruct expectedGoalCount checkpointPath
    | none => throw <| IO.userError "Exp52 top-level ContextInfo merge failed"
  | _ => pure ()

private partial def walkTops (trees : List InfoTree) (start finish : Nat)
    (candidate probe expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) (checkpointPath : FilePath) : CollectM Unit := do
  match trees with
  | [] => pure ()
  | tree :: rest =>
    walkTop tree start finish candidate probe expectedRaw expectedStruct expectedGoalCount checkpointPath
    walkTops rest start finish candidate probe expectedRaw expectedStruct expectedGoalCount checkpointPath

unsafe def elaborate (source : FilePath) (start finish : Nat)
    (output : FilePath) (candidate probe expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) (checkpointPath : FilePath) : IO Unit := do
  let input ← IO.FS.readFile source
  enableInitializersExecution
  let inputCtx := Parser.mkInputContext input source.toString
  let (header, parserState, messages) ← Parser.parseHeader inputCtx
  let (env, messages) ← processHeader header {} messages inputCtx
  if messages.hasErrors then throw <| IO.userError "Exp52 source header failed"
  let env := env.setMainModule (← moduleNameOfFileName source none)
  let commandState := {
    Command.mkState env messages {} with infoState.enabled := true
  }
  let final ← IO.processCommands inputCtx parserState commandState
  let action : CollectM Unit := walkTops
    final.commandState.infoState.trees.toArray.toList start finish candidate
    probe expectedRaw expectedStruct expectedGoalCount checkpointPath
  let collected ← action.run (#[] : Array CellResult)
  let result : CellResult ←
    match collected.2.toList with
    | [row] => pure row
    | [] => pure { targetFound := false, pos := start, endPos := finish }
    | rows => throw <| IO.userError s!"Exp52 ambiguous TacticInfo target: {rows.length}"
  if let some parent := output.parent then IO.FS.createDirAll parent
  IO.FS.writeFile output (toJson result).pretty

end Exp51Independent

open Exp51Independent

unsafe def main (args : List String) : IO Unit := do
  match args with
  | [source, start, finish, output, checkpoint, candidate, probe,
      expectedRawPath, expectedStructPath, expectedGoalCount] =>
    let some p := start.toNat?
      | throw <| IO.userError "bad start position"
    let some q := finish.toNat?
      | throw <| IO.userError "bad end position"
    let some count := expectedGoalCount.toNat?
      | throw <| IO.userError "bad expected goal count"
    let expectedRaw ← IO.FS.readFile ⟨expectedRawPath⟩
    let expectedStruct ← IO.FS.readFile ⟨expectedStructPath⟩
    elaborate ⟨source⟩ p q ⟨output⟩ candidate probe expectedRaw
      expectedStruct count ⟨checkpoint⟩
  | _ => throw <| IO.userError "usage: source start finish output checkpoint candidate probe expectedRaw expectedStruct expectedGoalCount"
'''

LEAN_SOURCE_SHA256 = hashlib.sha256(LEAN_SOURCE.encode("utf-8")).hexdigest()


def _record_sha(value: Mapping[str, Any]) -> str:
    return json_sha256({key: item for key, item in value.items()
                        if key != "record_sha256"})


def _endpoint_matches(
    observed: Mapping[str, Any], expected: Mapping[str, Any]
) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for kind in ("raw", "text48", "struct"):
        left = observed.get(kind, {})
        right = expected.get(kind, {})
        result[kind] = bool(
            left.get("sha256") == right.get("sha256")
            and left.get("metadata") == right.get("metadata")
            and left.get("state", {}).get("sha256")
            == right.get("state", {}).get("sha256")
        )
    return result


def _consume_checkpoint(
    *,
    raw_path: Path,
    receipt_path: Path,
    runtime_root: Path,
    source_row: Mapping[str, Any],
    branch: Mapping[str, Any],
    cell_id: str,
    input_identity_sha256: str,
    source_exp51_row_sha256: str,
    candidate_record_sha256: str,
) -> dict[str, Any] | None:
    """Validate and compact the pre-probe checkpoint, then remove raw duplication."""
    if not raw_path.is_file():
        return None
    raw_text = raw_path.read_text(encoding="utf-8")
    raw_sha = file_sha256(raw_path)
    raw_bytes = raw_path.stat().st_size
    raw_content = base.store_text(
        runtime_root, "candidate_checkpoint_raw", raw_text
    )
    if not (
        raw_content.get("sha256") == raw_sha
        and raw_content.get("bytes") == raw_bytes
    ):
        raise ValueError("Exp52 raw checkpoint content-store copy changed")
    checkpoint = read_json(raw_path)
    if not (
        checkpoint.get("schema")
        == CHECKPOINT_RAW_SCHEMA
        and checkpoint.get("reconstructionMatched") is True
        and checkpoint.get("probeInvocationNext") is True
        and int(checkpoint.get("preGoalCount", 0)) == 1
    ):
        raise ValueError("Exp52 candidate checkpoint schema or gate changed")
    initial_payload = base.endpoint_payload(
        str(checkpoint["beforeText"]), str(checkpoint["beforeStruct"]),
        int(checkpoint["preGoalCount"]),
    )
    candidate_payload = base.endpoint_payload(
        str(checkpoint["candidateText"]), str(checkpoint["candidateStruct"]),
        int(checkpoint["candidateGoalCount"]),
    )
    initial = base.compact_endpoint(runtime_root, initial_payload)
    candidate = base.compact_endpoint(runtime_root, candidate_payload)
    initial_match = _endpoint_matches(initial, source_row["initial_endpoints"])
    candidate_match = _endpoint_matches(candidate, branch["endpoints"])
    valid = bool(
        all(initial_match.values())
        and all(candidate_match.values())
        and int(checkpoint["candidateGoalCount"]) == int(branch["goal_count"])
        and branch.get("terminal") is False
    )
    receipt = {
        "version": 1,
        "schema": CHECKPOINT_COMPACT_SCHEMA,
        "cell_id": cell_id,
        "input_identity_sha256": input_identity_sha256,
        "source_exp51_row_sha256": source_exp51_row_sha256,
        "candidate_record_sha256": candidate_record_sha256,
        "raw_checkpoint_sha256": raw_sha,
        "raw_checkpoint_bytes": raw_bytes,
        "raw_checkpoint_content": raw_content,
        "lean_exact_match": checkpoint["reconstructionMatched"],
        "probe_invocation_next": checkpoint["probeInvocationNext"],
        "initial_endpoints": initial,
        "candidate_endpoints": candidate,
        "prestate_match": initial_match,
        "candidate_post_match": candidate_match,
        "candidate_goal_count": int(checkpoint["candidateGoalCount"]),
        "valid_reconstruction": valid,
    }
    receipt["record_sha256"] = _record_sha(receipt)
    if receipt_path.is_file():
        if read_json(receipt_path) != receipt:
            raise ValueError("existing compact Exp52 checkpoint changed")
    else:
        atomic_json_dump(receipt, receipt_path)
    raw_path.unlink()
    return {
        "receipt": receipt,
        "receipt_path": str(receipt_path),
        "receipt_sha256": file_sha256(receipt_path),
    }


def _failure_category(error: str) -> str:
    value = error.lower()
    if error.startswith("parse:") or "unexpected token" in value:
        return "syntax_or_elaboration_failure"
    return "tactic_failure"


def _process_failure_category(
    returncode: int | None, stderr: str, timed_out: bool
) -> str:
    if timed_out:
        return "timeout"
    text = stderr.lower()
    if (returncode is not None and returncode < 0) or any(
        marker in text for marker in (
            "out of memory", "cannot allocate memory", "killed", "resource"
        )
    ):
        return "resource_failure"
    return "worker_or_protocol_failure"


def _load_frozen_cell(inp: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(inp["scientific_root"]).resolve()
    amendment = validate_amendment(root)
    expected_input_identity = json_sha256({
        key: item for key, item in inp.items()
        if key != "input_identity_sha256"
    })
    if not (
        inp.get("schema") == INPUT_SCHEMA
        and inp.get("alignment_version") == EXECUTION_ALIGNMENT_VERSION
        and inp.get("mechanical_fix_id") == EXECUTION_FIX_ID
        and inp.get("amendment_sha256") == amendment["amendment_sha256"]
        and inp.get("exp52_protocol_sha256") == amendment["protocol_sha256"]
        and inp.get("input_identity_sha256") == expected_input_identity
    ):
        raise ValueError("Exp52 cell input differs from the execution amendment")
    source_row_path = Path(inp["source_exp51_row"]).resolve()
    if not (
        source_row_path.is_file()
        and source_row_path.is_relative_to(root)
        and file_sha256(source_row_path) == inp.get("source_exp51_row_sha256")
    ):
        raise ValueError("Exp52 source Exp51 row changed")
    source_row = read_json(source_row_path)
    if not (
        source_row.get("worker_ok") is True
        and source_row.get("theorem_id") == inp.get("theorem_id")
        and source_row.get("record_sha256") == _record_sha(source_row)
    ):
        raise ValueError("Exp52 source Exp51 row is not an exact evaluable row")
    index = int(inp["candidate_position_frozen"])
    candidates = list(source_row.get("candidates", []))
    if not 0 <= index < len(candidates):
        raise ValueError("Exp52 candidate index is outside the Exp51 row")
    branch = candidates[index]
    expected_endpoint = inp.get("expected_candidate_endpoint", {})
    if not (
        branch.get("executable") is True
        and branch.get("candidate_position_frozen") == index
        and branch.get("tactic") == inp.get("candidate_tactic")
        and branch.get("head") == inp.get("candidate_head")
        and branch.get("record_sha256") == inp.get("candidate_record_sha256")
        and branch.get("endpoints", {}).get("raw", {}).get("sha256")
        == expected_endpoint.get("raw_sha256")
        and branch.get("endpoints", {}).get("text48", {}).get("sha256")
        == expected_endpoint.get("text48_sha256")
        and branch.get("endpoints", {}).get("struct", {}).get("sha256")
        == expected_endpoint.get("strict_sha256")
        and branch.get("goal_count") == expected_endpoint.get("goal_count")
        and branch.get("terminal") == expected_endpoint.get("terminal")
        and branch.get("terminal") is False
        and int(branch.get("goal_count", 0)) > 0
    ):
        raise ValueError("Exp52 candidate identity or eligibility changed")
    targets = {
        str(row["theorem_id"]): row for row in amendment["targets"]
    }
    target = targets.get(str(inp.get("theorem_id")))
    if target is None or not (
        target.get("slug") == inp.get("slug")
        and target.get("rid") == inp.get("rid")
        and target.get("source_file_sha256")
        == source_row.get("source_file_sha256")
    ):
        raise ValueError("Exp52 frozen target identity changed")
    retained = amendment["protocol"]["probe_surface"]["retained_panel"]
    if inp.get("probe") not in retained:
        raise ValueError("Exp52 cell contains a probe outside the frozen panel")
    return {
        "root": root,
        "amendment": amendment,
        "source_row": source_row,
        "source_row_path": source_row_path,
        "target": target,
        "branch": branch,
    }


def _base_record(inp: Mapping[str, Any], process: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": WORKER_SCHEMA,
        "version": 1,
        "alignment_version": EXECUTION_ALIGNMENT_VERSION,
        "mechanical_fix_id": EXECUTION_FIX_ID,
        "worker_version": EXP52_WORKER_VERSION,
        "cell_id": inp["cell_id"],
        "cell_index": inp["cell_index"],
        "amendment_sha256": inp["amendment_sha256"],
        "exp52_protocol_sha256": inp["exp52_protocol_sha256"],
        "selection_ledger_sha256": inp["selection_ledger_sha256"],
        "selection_record_sha256": inp["selection_record_sha256"],
        "cell_plan_record_sha256": inp["cell_plan_record_sha256"],
        "root_id": inp["root_id"],
        "theorem_id": inp["theorem_id"],
        "rid": inp["rid"],
        "slug": inp["slug"],
        "pair_id": inp["pair_id"],
        "pair_role": inp["pair_role"],
        "side": inp["side"],
        "probe": inp["probe"],
        "probe_index": inp["probe_index"],
        "repeat_kind": inp["repeat_kind"],
        "candidate_tactic": inp["candidate_tactic"],
        "candidate_head": inp["candidate_head"],
        "candidate_position_frozen": inp["candidate_position_frozen"],
        "candidate_record_sha256": inp["candidate_record_sha256"],
        "expected_candidate_endpoint": inp["expected_candidate_endpoint"],
        "input_identity_sha256": inp["input_identity_sha256"],
        "source_exp51_row": inp["source_exp51_row"],
        "source_exp51_row_sha256": inp["source_exp51_row_sha256"],
        "process": dict(process),
        "manual_reconciliation_count": 0,
        "scientific_retry_permitted": False,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input).resolve()
    inp = read_json(input_path)
    frozen = _load_frozen_cell(inp)
    root = frozen["root"]
    target = frozen["target"]
    branch = frozen["branch"]
    runtime_root = Path(args.runtime_root).resolve()
    output = Path(args.output).resolve()
    execution_shards = (root / "exp52/execution/shards").resolve()
    if not (
        runtime_root.is_relative_to(execution_shards)
        and output.is_relative_to(execution_shards)
        and output.parent.name == "rows"
        and output.name == f"{inp['cell_id']}.json"
        and runtime_root == output.parent.parent / "runtime"
        and input_path
        == output.parent.parent / "inputs" / f"{inp['cell_id']}.json"
    ):
        raise ValueError("Exp52 worker paths are outside the frozen shard root")
    if output.is_file():
        existing = read_json(output)
        if not (
            existing.get("cell_id") == inp.get("cell_id")
            and existing.get("record_sha256") == _record_sha(existing)
        ):
            raise ValueError("existing Exp52 cell row changed")
        return existing
    if int(args.timeout) != LEAN_TIMEOUT_SECONDS:
        raise ValueError("Exp52 timeout differs from the frozen 900 seconds")
    project = Path(target["checkout"]).resolve()
    source = (project / target["file_path"]).resolve()
    if not (
        source.is_file()
        and file_sha256(source) == target["source_file_sha256"]
    ):
        raise ValueError("Exp52 theorem source identity changed")
    generated = runtime_root / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    lean_file = generated / LEAN_FILE_NAME
    if lean_file.is_file():
        if file_sha256(lean_file) != LEAN_SOURCE_SHA256:
            raise ValueError("generated Exp52 Lean worker changed")
    else:
        lean_file.write_text(LEAN_SOURCE, encoding="utf-8")

    expected_raw = branch["endpoints"]["raw"]["state"]
    expected_struct = branch["endpoints"]["struct"]["state"]
    # Hydration validates the archived content before its path is given to Lean.
    hydrate_text(expected_raw)
    hydrate_text(expected_struct)
    raw_out = runtime_root / "raw" / f"{inp['cell_id']}.json"
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_raw = (
        runtime_root / "candidate_checkpoint_raw" / f"{inp['cell_id']}.json"
    )
    checkpoint_receipt = (
        runtime_root / "candidate_checkpoints" / f"{inp['cell_id']}.json"
    )
    if raw_out.exists() or checkpoint_raw.exists() or checkpoint_receipt.exists():
        raise ValueError(
            "Exp52 raw/checkpoint evidence already exists before the sole attempt"
        )
    cmd = [
        "lake", "env", "lean", "--run", str(lean_file), str(source),
        str(target["target_pos"]), str(target["target_end_pos"]), str(raw_out),
        str(checkpoint_raw),
        str(inp["candidate_tactic"]), str(inp["probe"]),
        str(expected_raw["path"]), str(expected_struct["path"]),
        str(branch["goal_count"]),
    ]
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        lean_process_group_id: int | None = os.getpgid(proc.pid)
    except ProcessLookupError:
        lean_process_group_id = None
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=LEAN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
    elapsed = time.monotonic() - started
    process = {
        "fresh_lean_process": lean_process_group_id == proc.pid,
        "fresh_session_requested": True,
        "lean_pid": proc.pid,
        "lean_process_group_id": lean_process_group_id,
        "attempt_ordinal": 1,
        "retry_permitted": False,
        "timeout_seconds": LEAN_TIMEOUT_SECONDS,
        "timed_out": timed_out,
        "returncode": proc.returncode,
        "command_sha256": json_sha256(cmd),
        "command": cmd,
        "working_directory": str(project),
        "lean_source_sha256": LEAN_SOURCE_SHA256,
        "stdout": base.store_text(runtime_root, "process_stdout", stdout or ""),
        "stderr": base.store_text(runtime_root, "process_stderr", stderr or ""),
        "stdout_tail": (stdout or "")[-4000:],
        "stderr_tail": (stderr or "")[-8000:],
        "elapsed_seconds_descriptive": elapsed,
    }
    value = _base_record(inp, process)
    checkpoint = _consume_checkpoint(
        raw_path=checkpoint_raw,
        receipt_path=checkpoint_receipt,
        runtime_root=runtime_root,
        source_row=frozen["source_row"],
        branch=branch,
        cell_id=str(inp["cell_id"]),
        input_identity_sha256=str(inp["input_identity_sha256"]),
        source_exp51_row_sha256=str(inp["source_exp51_row_sha256"]),
        candidate_record_sha256=str(inp["candidate_record_sha256"]),
    )
    if checkpoint is not None:
        value["candidate_checkpoint"] = checkpoint
    if timed_out or proc.returncode != 0 or not raw_out.is_file():
        category = _process_failure_category(proc.returncode, stderr or "", timed_out)
        checkpoint_valid = bool(
            checkpoint is not None
            and checkpoint["receipt"].get("valid_reconstruction") is True
            and checkpoint["receipt"].get("probe_invocation_next") is True
            and category in {"timeout", "resource_failure"}
        )
        if checkpoint_valid:
            # The checkpoint is written atomically immediately before the
            # frozen probe invocation.  A later timeout/resource termination
            # is therefore retained as a probe response.  In particular,
            # genuine one-sided probe timeouts remain visible to H9.  A
            # worker/protocol failure is never promoted by this checkpoint.
            value.update({
                "record_complete": True,
                "worker_ok": True,
                "target_found": True,
                "pre_goal_count": 1,
                "initial_endpoints": checkpoint["receipt"]["initial_endpoints"],
                "prestate_match": checkpoint["receipt"]["prestate_match"],
                "candidate_observed_endpoints": (
                    checkpoint["receipt"]["candidate_endpoints"]
                ),
                "candidate_post_match": (
                    checkpoint["receipt"]["candidate_post_match"]
                ),
                "valid_reconstruction": True,
                "candidate_reconstruction_ok": True,
                "probe_attempted": True,
                "probe_executable": False,
                "probe_status": "failure",
                "failure_category": category,
                "response_component": "failure",
                "diagnostic": base.store_text(
                    runtime_root,
                    "diagnostic",
                    (stderr or stdout or category)[-12000:],
                ),
            })
        else:
            value.update({
                "record_complete": True,
                "worker_ok": False,
                "valid_reconstruction": False,
                "candidate_reconstruction_ok": False,
                "probe_attempted": False,
                "probe_executable": False,
                "probe_status": "not_executed",
                "failure_category": category,
                "response_component": "invalid_reconstruction",
                "diagnostic": base.store_text(
                    runtime_root,
                    "diagnostic",
                    (stderr or stdout or category)[-12000:],
                ),
            })
    else:
        raw = read_json(raw_out)
        raw_out.unlink(missing_ok=True)
        before_payload = base.endpoint_payload(
            str(raw.get("beforeText") or ""),
            str(raw.get("beforeStruct") or ""),
            int(raw.get("preGoalCount") or 0),
        )
        observed_initial = base.compact_endpoint(runtime_root, before_payload)
        candidate_raw = dict(raw.get("candidate") or {})
        candidate_payload = base.endpoint_payload(
            str(candidate_raw.get("afterText") or ""),
            str(candidate_raw.get("afterStruct") or ""),
            int(candidate_raw.get("goalCount") or 0),
        ) if candidate_raw.get("executable") is True else None
        observed_candidate = (
            base.compact_endpoint(runtime_root, candidate_payload)
            if candidate_payload is not None else None
        )
        initial_match = _endpoint_matches(
            observed_initial, frozen["source_row"]["initial_endpoints"]
        )
        candidate_match = (
            _endpoint_matches(observed_candidate, branch["endpoints"])
            if observed_candidate is not None else {
                "raw": False, "text48": False, "struct": False
            }
        )
        reconstruction_ok = bool(
            checkpoint is not None
            and checkpoint["receipt"].get("valid_reconstruction") is True
            and raw.get("targetFound") is True
            and int(raw.get("preGoalCount") or 0) == 1
            and all(initial_match.values())
            and candidate_raw.get("executable") is True
            and raw.get("reconstructionMatched") is True
            and all(candidate_match.values())
            and int(candidate_raw.get("goalCount") or 0)
            == int(branch["goal_count"])
            and branch.get("terminal") is False
            and checkpoint["receipt"].get("initial_endpoints") == observed_initial
            and checkpoint["receipt"].get("candidate_endpoints")
            == observed_candidate
        )
        probe_raw = dict(raw.get("probe") or {})
        probe_attempted = raw.get("probeAttempted") is True
        probe_executable = probe_raw.get("executable") is True
        value.update({
            "target_found": raw.get("targetFound") is True,
            "pre_goal_count": raw.get("preGoalCount"),
            "initial_endpoints": observed_initial,
            "prestate_match": initial_match,
            "candidate_observed_endpoints": observed_candidate,
            "candidate_post_match": candidate_match,
            "candidate_reconstruction_ok": reconstruction_ok,
            "valid_reconstruction": reconstruction_ok,
            "probe_attempted": probe_attempted,
            "probe_executable": probe_executable,
        })
        if not reconstruction_ok or probe_attempted is not True:
            value.update({
                "record_complete": True,
                "worker_ok": False,
                "probe_status": "not_executed",
                "failure_category": "worker_or_protocol_failure",
                "response_component": "invalid_reconstruction",
                "diagnostic": base.store_text(
                    runtime_root,
                    "diagnostic",
                    str(candidate_raw.get("error") or probe_raw.get("error")
                        or "candidate reconstruction mismatch"),
                ),
            })
        elif probe_executable:
            count = int(probe_raw["goalCount"])
            next_payload = base.endpoint_payload(
                str(probe_raw["afterText"]), str(probe_raw["afterStruct"]), count
            )
            value.update({
                "record_complete": True,
                "worker_ok": True,
                "probe_status": "success",
                "failure_category": None,
                "response_component": "success",
                "next_endpoints": base.compact_endpoint(runtime_root, next_payload),
                "next_goal_count": count,
                "next_terminal": count == 0,
            })
        else:
            error = str(probe_raw.get("error") or "tactic failure")
            value.update({
                "record_complete": True,
                "worker_ok": True,
                "probe_status": "failure",
                "failure_category": _failure_category(error),
                "response_component": "failure",
                "diagnostic": base.store_text(runtime_root, "diagnostic", error),
            })
    value["record_sha256"] = _record_sha(value)
    atomic_json_dump(value, output)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--timeout", type=int, default=LEAN_TIMEOUT_SECONDS)
    parser.add_argument("--root", default=str(SCIENTIFIC_ROOT))
    return parser.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps({
        "cell_id": result.get("cell_id"),
        "record_complete": result.get("record_complete"),
        "valid_reconstruction": result.get("valid_reconstruction"),
        "probe_status": result.get("probe_status"),
        "failure_category": result.get("failure_category"),
    }, ensure_ascii=False))
