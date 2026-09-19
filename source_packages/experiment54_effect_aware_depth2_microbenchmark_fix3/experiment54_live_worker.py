"""Execute one frozen Exp54 depth-2 cell in one fresh Lean process."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

from experiment54_protocol import *


WORKER_VERSION = "experiment54-live-tacticinfo-depth2-worker-v1-fix3"
LEAN_FILE_NAME = "Experiment54EffectAwareDepth2Worker.lean"


def _load_exp49_worker() -> Any:
    root = server_root()
    candidates = [
        root / "experiment49_candidate_endpoint_robustness",
        root / "server_packages/experiment49_candidate_endpoint_robustness",
    ]
    for candidate in candidates:
        if (candidate / "experiment49_strict_worker.py").is_file():
            sys.path.insert(0, str(candidate))
            import experiment49_strict_worker as worker  # type: ignore
            return worker
    raise FileNotFoundError("locked Exp49 worker source is unavailable")


EXP49_WORKER = _load_exp49_worker()
_PREFIX, _SEPARATOR, _TAIL = EXP49_WORKER.LEAN_SOURCE.partition(
    "structure BranchResult where"
)
if not _SEPARATOR:
    raise RuntimeError("locked Exp49 Lean worker layout changed")


LEAN_SOURCE = _PREFIX + r'''
structure Step where
  executable : Bool
  stateAfter : Option String := none
  strictStateAfter : Option String := none
  goalCount : Option Nat := none
  error : Option String := none
deriving ToJson

structure CellResult where
  targetFound : Bool
  pos : Nat
  endPos : Nat
  preGoalCount : Option Nat := none
  stateBefore : Option String := none
  strictStateBefore : Option String := none
  candidate : Step := { executable := false }
  candidateMatched : Bool := false
  probeAttempted : Bool := false
  probe : Step := { executable := false }
deriving ToJson

def failedStep (message : String) : Step := {
  executable := false
  error := some message
}

def runTexts (ctx : ContextInfo) (ti : TacticInfo)
    (candidateText probeText expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) : IO CellResult := do
  -- Exp49's generated worker declared a 2,000,000-heartbeat budget, but
  -- ContextInfo.runMetaM reinstalls the target command's options.  Make that
  -- intended budget explicit in the live context and reset it before the
  -- downstream probe so candidate reconstruction cannot consume probe budget.
  let executionOptions := ctx.options.setNat `maxHeartbeats 2000000
  let beforeCtx := { ctx with mctx := ti.mctxBefore, options := executionOptions }
  let pre ← Pp.ppGoals beforeCtx ti.goalsBefore
  let strictPre ← Strict.goalsKey beforeCtx ti.goalsBefore
  match Parser.runParserCategory ctx.env `tactic candidateText with
  | .error message =>
    return {
      targetFound := true
      pos := ti.stx.getPos?.map (·.1) |>.getD 0
      endPos := ti.stx.getTailPos?.map (·.1) |>.getD 0
      preGoalCount := some ti.goalsBefore.length
      stateBefore := some pre
      strictStateBefore := some strictPre
      candidate := failedStep ("parse: " ++ message)
      probe := failedStep "probe prohibited: candidate parse failed"
    }
  | .ok candidateStx =>
    try
      let value ← beforeCtx.runMetaM {} do
        let [goal] := ti.goalsBefore
          | throwError "Exp54 requires exactly one pre-state goal"
        let action : Term.TermElabM (String × String × Nat × Bool × Bool × Step) := do
          let afterCandidate ← Tactic.run goal (Tactic.evalTactic candidateStx)
          let candidateRaw ← liftM (m := MetaM) <| Pp.ppGoalsM afterCandidate
          let candidateStruct ← liftM (m := MetaM) <| Strict.goalsKeyM afterCandidate
          let matched :=
            candidateRaw == expectedRaw &&
            candidateStruct == expectedStruct &&
            afterCandidate.length == expectedGoalCount
          if !matched then
            pure (candidateRaw, candidateStruct, afterCandidate.length, false, false,
              failedStep "probe prohibited: candidate checkpoint mismatch")
          else if afterCandidate.isEmpty then
            pure (candidateRaw, candidateStruct, 0, true, false,
              failedStep "probe prohibited: terminal candidate checkpoint")
          else
            match Parser.runParserCategory ctx.env `tactic probeText with
            | .error message =>
              pure (candidateRaw, candidateStruct, afterCandidate.length, true, true,
                failedStep ("parse: " ++ message))
            | .ok probeStx =>
              let probeResult : Step ← tryCatchRuntimeEx
                (withCurrHeartbeats do
                  let afterProbe ← Tactic.run afterCandidate.head! do
                    Tactic.setGoals afterCandidate
                    Tactic.evalTactic probeStx
                  let raw ← liftM (m := MetaM) <| Pp.ppGoalsM afterProbe
                  let structural ← liftM (m := MetaM) <| Strict.goalsKeyM afterProbe
                  pure {
                    executable := true
                    stateAfter := some raw
                    strictStateAfter := some structural
                    goalCount := some afterProbe.length
                  })
                (fun _ =>
                  -- CoreM deliberately lets resource-limit exceptions escape
                  -- ordinary try/catch.  Use Lean's runtime-exception boundary
                  -- around the isolated probe budget and record only the
                  -- registered failure category, never lazy exception text.
                  pure (failedStep "tactic execution failed"))
              pure (candidateRaw, candidateStruct, afterCandidate.length, true, true,
                probeResult)
        let (result, _) ← liftM (m := MetaM) <|
          Term.TermElabM.run action ({} : Term.Context) ({} : Term.State)
        pure result
      return {
        targetFound := true
        pos := ti.stx.getPos?.map (·.1) |>.getD 0
        endPos := ti.stx.getTailPos?.map (·.1) |>.getD 0
        preGoalCount := some ti.goalsBefore.length
        stateBefore := some pre
        strictStateBefore := some strictPre
        candidate := {
          executable := true
          stateAfter := some value.1
          strictStateAfter := some value.2.1
          goalCount := some value.2.2.1
        }
        candidateMatched := value.2.2.2.1
        probeAttempted := value.2.2.2.2.1
        probe := value.2.2.2.2.2
      }
    catch ex =>
      return {
        targetFound := true
        pos := ti.stx.getPos?.map (·.1) |>.getD 0
        endPos := ti.stx.getTailPos?.map (·.1) |>.getD 0
        preGoalCount := some ti.goalsBefore.length
        stateBefore := some pre
        strictStateBefore := some strictPre
        candidate := failedStep (toString ex)
        probe := failedStep "probe prohibited: candidate execution failed"
      }

abbrev CollectM := StateT (Array CellResult) IO

private def inspectTactic (ctx : ContextInfo) (ti : TacticInfo)
    (parent : InfoTree) (targetPos targetEnd : Nat)
    (candidate probe expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) : CollectM Unit := do
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
          expectedGoalCount
        modify fun rows => rows.push row
    | _ => pure ()
  | _ => pure ()

mutual
  private partial def walk (ctx : ContextInfo) (tree parent : InfoTree)
      (start finish : Nat) (candidate probe expectedRaw expectedStruct : String)
      (expectedGoalCount : Nat) : CollectM Unit := do
    match tree with
    | .context inner child =>
      match inner.mergeIntoOuter? ctx with
      | some merged => walk merged child tree start finish candidate probe expectedRaw expectedStruct expectedGoalCount
      | none => throw <| IO.userError "Exp54 ContextInfo merge failed"
    | .node info children =>
      match info with
      | .ofTacticInfo ti => inspectTactic ctx ti parent start finish candidate probe expectedRaw expectedStruct expectedGoalCount
      | _ => pure ()
      walkChildren ctx children.toList tree start finish candidate probe expectedRaw expectedStruct expectedGoalCount
    | _ => pure ()

  private partial def walkChildren (ctx : ContextInfo)
      (children : List InfoTree) (parent : InfoTree) (start finish : Nat)
      (candidate probe expectedRaw expectedStruct : String)
      (expectedGoalCount : Nat) : CollectM Unit := do
    match children with
    | [] => pure ()
    | child :: rest =>
      walk ctx child parent start finish candidate probe expectedRaw expectedStruct expectedGoalCount
      walkChildren ctx rest parent start finish candidate probe expectedRaw expectedStruct expectedGoalCount
end

private def walkTop (tree : InfoTree) (start finish : Nat)
    (candidate probe expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) : CollectM Unit := do
  match tree with
  | .context ctx child =>
    match ctx.mergeIntoOuter? none with
    | some merged => walk merged child tree start finish candidate probe expectedRaw expectedStruct expectedGoalCount
    | none => throw <| IO.userError "Exp54 top-level ContextInfo merge failed"
  | _ => pure ()

private partial def walkTops (trees : List InfoTree) (start finish : Nat)
    (candidate probe expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) : CollectM Unit := do
  match trees with
  | [] => pure ()
  | tree :: rest =>
    walkTop tree start finish candidate probe expectedRaw expectedStruct expectedGoalCount
    walkTops rest start finish candidate probe expectedRaw expectedStruct expectedGoalCount

unsafe def elaborate (source : FilePath) (start finish : Nat)
    (output : FilePath) (candidate probe expectedRaw expectedStruct : String)
    (expectedGoalCount : Nat) : IO Unit := do
  let input ← IO.FS.readFile source
  enableInitializersExecution
  let inputCtx := Parser.mkInputContext input source.toString
  let (header, parserState, messages) ← Parser.parseHeader inputCtx
  let (env, messages) ← processHeader header {} messages inputCtx
  if messages.hasErrors then throw <| IO.userError "Exp54 source header failed"
  let env := env.setMainModule (← moduleNameOfFileName source none)
  let commandState := {
    Command.mkState env messages {} with infoState.enabled := true
  }
  let final ← IO.processCommands inputCtx parserState commandState
  let action : CollectM Unit := walkTops
    final.commandState.infoState.trees.toArray.toList start finish candidate
    probe expectedRaw expectedStruct expectedGoalCount
  let collected ← action.run (#[] : Array CellResult)
  let result : CellResult ←
    match collected.2.toList with
    | [row] => pure row
    | [] => pure { targetFound := false, pos := start, endPos := finish }
    | rows => throw <| IO.userError s!"Exp54 ambiguous TacticInfo target: {rows.length}"
  if let some parent := output.parent then IO.FS.createDirAll parent
  IO.FS.writeFile output (toJson result).pretty

end Exp49LiveBranch

open Exp49LiveBranch

unsafe def main (args : List String) : IO Unit := do
  match args with
  | [source, start, finish, output, candidate, probe,
      expectedRawPath, expectedStructPath, expectedGoalCount] =>
    let some p := start.toNat? | throw <| IO.userError "bad start position"
    let some q := finish.toNat? | throw <| IO.userError "bad end position"
    let some count := expectedGoalCount.toNat? | throw <| IO.userError "bad goal count"
    let expectedRaw ← IO.FS.readFile ⟨expectedRawPath⟩
    let expectedStruct ← IO.FS.readFile ⟨expectedStructPath⟩
    elaborate ⟨source⟩ p q ⟨output⟩ candidate probe expectedRaw expectedStruct count
  | _ => throw <| IO.userError "usage: source start finish output candidate probe expectedRaw expectedStruct goalCount"
'''

LEAN_SOURCE_SHA256 = hashlib.sha256(LEAN_SOURCE.encode("utf-8")).hexdigest()


def build_lean_source(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if file_sha256(path) != LEAN_SOURCE_SHA256:
            raise ValueError("generated Exp54 Lean source changed")
    else:
        path.write_text(LEAN_SOURCE, encoding="utf-8")
    return path


def failure_category(message: str) -> str:
    text = message.lower()
    if message.startswith("parse:") or "unexpected token" in text:
        return "syntax_or_elaboration_failure"
    return "tactic_failure"


def find_cell_and_target(
    frozen: Mapping[str, Any], inp: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cells = {
        row["cell_id"]: row for row in read_jsonl(frozen["cells_path"])
    }
    cell = cells.get(inp.get("cell_id"))
    if cell is None or cell != inp.get("cell"):
        raise ValueError("Exp54 cell input differs from frozen plan")
    target_meta = next(
        (row for row in frozen["targets"] if row["target_id"] == cell["target_id"]),
        None,
    )
    if target_meta is None:
        raise ValueError("Exp54 target missing")
    target_path = Path(target_meta["path"])
    if not target_path.is_file() or file_sha256(target_path) != target_meta["sha256"]:
        raise ValueError("Exp54 target record changed")
    target = read_json(target_path)
    assert_sealed(target, "target")
    pair = target["pairs"][cell["pair_role"]]
    if pair["pair_id"] != cell["pair_id"]:
        raise ValueError("Exp54 pair identity changed")
    branch = pair[f"{cell['side']}_branch"]
    return cell, target, branch


def run(args: argparse.Namespace) -> dict[str, Any]:
    inp = read_json(args.input)
    root = Path(inp["artifact_root"]).resolve()
    frozen = load_freeze(root)
    expected_identity = json_sha256({
        k: v for k, v in inp.items() if k != "input_identity_sha256"
    })
    if not (
        inp.get("protocol_version") == PROTOCOL_VERSION
        and inp.get("input_identity_sha256") == expected_identity
        and inp.get("design_record_sha256") == frozen["record_sha256"]
    ):
        raise ValueError("Exp54 worker input changed")
    cell, target, branch = find_cell_and_target(frozen, inp)
    output = Path(args.output).resolve()
    if output.is_file():
        existing = read_json(output)
        assert_sealed(existing, "existing worker row")
        return existing
    project = Path(target["checkout"]).resolve()
    source = (project / target["file_path"]).resolve()
    if not source.is_file() or file_sha256(source) != target["source_file_sha256"]:
        raise ValueError("Exp54 source identity changed")
    runtime = output.parent.parent / "runtime"
    lean_file = build_lean_source(root / "generated" / LEAN_FILE_NAME)
    expected_raw = branch["endpoints"]["raw"]["value"]["state"]
    expected_struct = branch["endpoints"]["struct"]["value"]["state"]
    expected_dir = runtime / "expected"
    expected_dir.mkdir(parents=True, exist_ok=True)
    raw_expected_path = expected_dir / f"{cell['cell_id']}.raw.txt"
    struct_expected_path = expected_dir / f"{cell['cell_id']}.struct.txt"
    raw_expected_path.write_text(str(expected_raw), encoding="utf-8")
    struct_expected_path.write_text(str(expected_struct), encoding="utf-8")
    raw_out = runtime / "lean_raw" / f"{cell['cell_id']}.json"
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "lake", "env", "lean", "--run", str(lean_file), str(source),
        str(target["target_pos"]), str(target["target_end_pos"]), str(raw_out),
        str(branch["tactic"]), str(cell["probe"]),
        str(raw_expected_path), str(struct_expected_path),
        str(branch["goal_count"]),
    ]
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=project, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    try:
        pgid: int | None = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = None
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
    process = {
        "fresh_lean_process": pgid == proc.pid,
        "fresh_session_requested": True,
        "lean_pid": proc.pid,
        "lean_process_group_id": pgid,
        "attempt_ordinal": 1,
        "retry_permitted": False,
        "timeout_seconds": LEAN_TIMEOUT_SECONDS,
        "timed_out": timed_out,
        "returncode": proc.returncode,
        "command_sha256": json_sha256(cmd),
        "lean_source_sha256": LEAN_SOURCE_SHA256,
        "elapsed_seconds_descriptive": time.monotonic() - started,
        "stdout_tail": (stdout or "")[-2000:],
        "stderr_tail": (stderr or "")[-6000:],
    }
    value: dict[str, Any] = {
        "schema": ROW_SCHEMA,
        "version": VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "execution_version": EXECUTION_VERSION,
        "mechanical_fix_id": MECHANICAL_FIX_ID,
        "worker_version": WORKER_VERSION,
        "cell": cell,
        "cell_id": cell["cell_id"],
        "policy": cell["policy"],
        "pair_role": cell["pair_role"],
        "pair_id": cell["pair_id"],
        "root_id": cell["root_id"],
        "slug": cell["slug"],
        "side": cell["side"],
        "probe": cell["probe"],
        "candidate_tactic": branch["tactic"],
        "candidate_head": branch["head"],
        "candidate_position_frozen": branch["candidate_position_frozen"],
        "input_identity_sha256": inp["input_identity_sha256"],
        "process": process,
        "scientific_retry_count": 0,
        "manual_reconciliation_count": 0,
    }
    if timed_out or proc.returncode != 0 or not raw_out.is_file():
        value.update({
            "record_complete": True,
            "valid_reconstruction": False,
            "probe_status": "timeout" if timed_out else "worker_failure",
            "failure_category": "timeout" if timed_out else "worker_or_protocol_failure",
        })
    else:
        raw = read_json(raw_out)
        pre_goal_count = raw.get("preGoalCount")
        initial_ready = bool(
            isinstance(pre_goal_count, int)
            and raw.get("stateBefore") is not None
            and raw.get("strictStateBefore") is not None
        )
        initial = (
            endpoint_map(
                raw["stateBefore"], raw["strictStateBefore"], pre_goal_count
            )
            if initial_ready else None
        )
        candidate_raw = raw.get("candidate", {})
        candidate_goal_count = candidate_raw.get("goalCount")
        candidate_ready = bool(
            candidate_raw.get("executable") is True
            and isinstance(candidate_goal_count, int)
            and candidate_raw.get("stateAfter") is not None
            and candidate_raw.get("strictStateAfter") is not None
        )
        candidate = (
            endpoint_map(
                candidate_raw["stateAfter"],
                candidate_raw["strictStateAfter"],
                candidate_goal_count,
            )
            if candidate_ready else None
        )
        initial_exact = bool(
            initial is not None and all(
                initial[k]["sha256"]
                == target["initial_endpoints"][k]["sha256"]
                for k in ("raw", "text48", "struct")
            )
        )
        candidate_exact = bool(
            candidate is not None and all(
                candidate[k]["sha256"] == branch["endpoints"][k]["sha256"]
                for k in ("raw", "text48", "struct")
            )
        )
        valid = bool(
            raw.get("targetFound") is True
            and raw.get("candidateMatched") is True
            and raw.get("probeAttempted") is True
            and initial_exact and candidate_exact
            and pre_goal_count == 1
        )
        value.update({
            "record_complete": True,
            "target_found": raw.get("targetFound") is True,
            "initial_endpoint_exact": initial_exact,
            "candidate_endpoint_exact": candidate_exact,
            "lean_candidate_checkpoint_exact": raw.get("candidateMatched") is True,
            "valid_reconstruction": valid,
            "candidate_endpoint": (
                {
                    k: compact_endpoint(runtime, candidate[k])
                    for k in ("raw", "text48", "struct")
                }
                if candidate is not None else None
            ),
        })
        probe = raw.get("probe", {})
        if not valid:
            candidate_message = str(
                candidate_raw.get("error") or "candidate reconstruction failed"
            )
            value.update({
                "probe_status": (
                    "candidate_reconstruction_failure"
                    if not candidate_ready else "invalid_reconstruction"
                ),
                "failure_category": (
                    "candidate_execution_failure"
                    if not candidate_ready else "candidate_checkpoint_mismatch"
                ),
                "error_sha256": hashlib.sha256(
                    candidate_message.encode()
                ).hexdigest(),
                "error_tail": candidate_message[-1000:],
            })
        elif probe.get("executable") is True:
            endpoint = endpoint_map(
                str(probe["stateAfter"]), str(probe["strictStateAfter"]),
                int(probe["goalCount"]),
            )
            value.update({
                "probe_status": "success",
                "failure_category": None,
                "probe_endpoint": {
                    k: compact_endpoint(runtime, endpoint[k])
                    for k in ("raw", "text48", "struct")
                },
            })
        else:
            message = str(probe.get("error") or "unknown tactic failure")
            value.update({
                "probe_status": "failure",
                "failure_category": failure_category(message),
                "error_sha256": hashlib.sha256(message.encode()).hexdigest(),
                "error_tail": message[-1000:],
            })
    seal(value)
    atomic_json_dump(value, output)
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
