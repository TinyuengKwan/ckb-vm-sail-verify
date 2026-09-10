#!/usr/bin/env python3
"""Supplementary field correspondence gate, NOT the complete raw ADD decoder.

Keeps the production source/configuration and the main proof-check policy intact.
The separate field policy is reviewed input, never refreshed by this command.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import check_proof as gate
import ckb_source_baseline

ROOT = gate.ROOT
PROOF = ROOT / "proof/lean/decoder"
POLICY = PROOF / "field-policy.json"
SOURCES = ["proof/lean/decoder/RawFields.lean", "proof/lean/decoder/ExportFieldAudit.lean",
           "proof/lean/decoder/RuntimeCheck.rs", "scripts/check_raw_add_fields.py"]
ROOTS = ["ckb_vm::instructions::utils::" + n
         for n in ("rd", "rs1", "rs2", "opcode", "funct3", "funct7")]
MARKER = "FIELD_AUDIT_JSON="


def source_hashes():
    return {n: gate.file_hash(ROOT / n) for n in SOURCES}


def audit_from(log):
    rows = [s[len(MARKER):] for s in log.splitlines() if s.startswith(MARKER)]
    if len(rows) != 1:
        raise RuntimeError("expected one field audit record")
    return json.loads(rows[0])


def audit_summary(audit):
    return {"axioms": {n: sorted(v["axioms"]) for n, v in audit["theorems"].items()},
            "types": {n: gate.digest(v["type"].encode()) for n, v in audit["theorems"].items()},
            "definitions": {n: gate.digest(v.encode()) for n, v in audit["definitions"].items()}}


def check_audit(audit, policy):
    for entry in audit["theorems"].values():
        if not set(entry["axioms"]) <= {"propext", "Classical.choice", "Quot.sound"}:
            raise RuntimeError("nonstandard axiom in field correspondence")
    if any(v == "NOT_A_DEFINITION" for v in audit["definitions"].values()):
        raise RuntimeError("field function replaced with a non-definition")
    gate.require_equal(audit_summary(audit), policy["audit"], "field theorem types/bodies/dependencies")


def main():
    parent = ROOT / "artifacts/boundary-check"
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="raw-fields-", dir=parent))
    report = {"status": "running", "scope": "field-level correspondence and exhaustive Rust factory runtime checks",
              "raw_decoder_closed": False, "main_proof_check_stage": False,
              "clean_dependency_build": False, "directory": str(evidence), "stages": [],
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    report_path = evidence / "report.json"
    def save():
        gate.write_json(report_path, report)
    save()
    print("Supplementary raw field check: " + str(evidence), flush=True)
    try:
        policy = json.loads(POLICY.read_text())
        main_policy = json.loads(gate.POLICY.read_text())
        report["policy_sha256"] = gate.file_hash(POLICY)
        env, binaries, aeneas, lake = gate.tools_and_environment(main_policy)
        before = gate.source_evidence(main_policy, binaries, aeneas)
        generated_before = gate.generated_evidence(main_policy)
        report["source_baseline"] = before["ckb_source_baseline"]
        gate.require_equal(source_hashes(), policy["sources"], "supplementary sources")
        gate.require_equal(ROOTS, policy["roots"], "field extraction roots")
        report["sources"] = source_hashes()
        report["translator_versions"] = before["translator_versions"]
        report["tool_binaries"] = before["tool_binaries"]
        report["ckb_cargo_lock_sha256"] = gate.file_hash(ROOT / "deps/ckb-vm/Cargo.lock")
        gate.require_equal(report["ckb_cargo_lock_sha256"], policy["ckb_cargo_lock_sha256"], "CKB crate dependency lock")
        main_policy_sha = gate.file_hash(gate.POLICY)
        report["main_policy_sha256"] = main_policy_sha
        report["main_report_sha256_at_start"] = gate.file_hash(gate.ARTIFACTS / "report.json")
        env["CARGO_TARGET_DIR"] = str(evidence / "cargo-target")

        def run(name, cmd, cwd=ROOT, run_env=None, reject=False):
            print("==> " + name, flush=True)
            log = evidence / (name + ".log")
            with log.open("w") as stream:
                proc = subprocess.run(cmd, cwd=cwd, env=run_env or env, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=300)
            contents = log.read_text(errors="replace")
            record = {"name": name, "command": [str(a) for a in cmd], "cwd": str(cwd),
                      "exit_code": proc.returncode, "log_sha256": gate.file_hash(log),
                      "expected_compile_rejection": reject}
            report["stages"].append(record)
            save()
            if re.search(r"PANIC|uncaught exception|Stack overflow|Internal error", contents, re.I):
                raise RuntimeError(name + " emitted an internal error")
            if reject:
                if proc.returncode == 0 or "error:" not in contents or "unknown module" in contents:
                    raise RuntimeError(name + " did not reject the changed proof")
            elif proc.returncode:
                raise RuntimeError(name + " failed; see " + str(log))
            return contents

        llbc = evidence / "LocalFields.llbc"
        args = [str(binaries["charon"]), "cargo", "--preset=aeneas"]
        for root in ROOTS:
            args += ["--start-from", root]
        args += ["--dest-file", str(llbc), "--", "--lib", "--locked"]
        run("charon", args, ROOT / "deps/ckb-vm")
        if json.loads(llbc.read_text())["has_errors"]:
            raise RuntimeError("Charon reports translation errors")
        report["llbc_sha256"] = gate.file_hash(llbc)
        models = evidence / "models"
        run("aeneas", [str(binaries["aeneas"]), "-backend", "lean", "-abort-on-error",
            "-no-progress-bar", "-namespace", "RawDecodeExtract", "-dest", str(models), str(llbc)])
        model = models / "LocalFields.lean"
        gate.require_equal(gate.file_hash(model), policy["generated_sha256"], "field generated model")
        report["generated_sha256"] = gate.file_hash(model)
        project = ROOT / "proof/lean/theorems"
        lean = subprocess.check_output([lake, "env", "which", "lean"], cwd=project, env=env, text=True).strip()
        lean_path = subprocess.check_output([lake, "env", "printenv", "LEAN_PATH"], cwd=project, env=env, text=True).strip()
        env["LEAN_PATH"] = str(models) + os.pathsep + lean_path
        report["lean_version"] = subprocess.check_output([lean, "--version"], env=env, text=True).strip()
        report["initial_supplementary_oleans"] = len(list(models.glob("*.olean")))
        if report["initial_supplementary_oleans"]:
            raise RuntimeError("supplementary model cache must start empty")
        run("kernel-model", [lean, "--root=" + str(models), str(model), "-o", str(models / "LocalFields.olean")], project)
        run("kernel-fields", [lean, "--root=" + str(PROOF), str(PROOF / "RawFields.lean"),
                              "-o", str(models / "RawFields.olean")], project)
        audit = audit_from(run("field-audit", [lean, str(PROOF / "ExportFieldAudit.lean")], project))
        check_audit(audit, policy)
        gate.write_json(evidence / "field-audit.json", audit)
        report["theorem_axiom_counts"] = {n: len(v["axioms"]) for n, v in audit["theorems"].items()}

        # Negative copies never overwrite the real source or accepted .olean files.
        original = (PROOF / "RawFields.lean").read_text()
        wrong = evidence / "wrong-slice"
        wrong.mkdir()
        bad = original.replace("index (Sail.BitVec.extractLsb w.bv 11 7)",
                               "index (Sail.BitVec.extractLsb w.bv 12 8)", 1)
        if bad == original:
            raise RuntimeError("negative mutation did not apply")
        (wrong / "RawFields.lean").write_text(bad)
        run("negative-wrong-slice", [lean, "--root=" + str(wrong), str(wrong / "RawFields.lean")], project, reject=True)
        bad_model_dir = evidence / "wrong-rust-shift"
        bad_model_dir.mkdir()
        generated_text = model.read_text()
        bad_model = generated_text.replace("x instruction_bits 7#usize 5#usize", "x instruction_bits 8#usize 5#usize")
        if bad_model == generated_text:
            raise RuntimeError("Rust-shift mutation did not apply")
        (bad_model_dir / "LocalFields.lean").write_text(bad_model)
        bad_env = env.copy()
        bad_env["LEAN_PATH"] = str(bad_model_dir) + os.pathsep + env["LEAN_PATH"]
        run("negative-rust-model", [lean, "--root=" + str(bad_model_dir), str(bad_model_dir / "LocalFields.lean"),
                                   "-o", str(bad_model_dir / "LocalFields.olean")], project, bad_env)
        run("negative-rust-shift", [lean, str(PROOF / "RawFields.lean")], project, bad_env, reject=True)
        false_dir = evidence / "false-premise"
        false_dir.mkdir()
        bad = original.replace("theorem operands_correspond (w : U32)",
                               "theorem operands_correspond (unjustified : False) (w : U32)")
        if bad == original:
            raise RuntimeError("False-premise mutation did not apply")
        (false_dir / "RawFields.lean").write_text(bad)
        false_env = env.copy()
        false_env["LEAN_PATH"] = str(false_dir) + os.pathsep + env["LEAN_PATH"]
        run("negative-false-compile", [lean, "--root=" + str(false_dir), str(false_dir / "RawFields.lean"),
                                      "-o", str(false_dir / "RawFields.olean")], project, false_env)
        bad_audit = audit_from(run("negative-false-audit", [lean, str(PROOF / "ExportFieldAudit.lean")], project, false_env))
        try:
            check_audit(bad_audit, policy)
        except RuntimeError:
            report["false_premise_rejected_by_type_audit"] = True
        else:
            raise RuntimeError("type audit accepted a False premise")

        # Compile the published runtime checker against the unchanged CKB path
        # in a separate crate; do not touch the workspace manifest or its lock.
        runtime = evidence / "runtime"
        runtime.mkdir()
        (runtime / "Cargo.toml").write_text('[package]\nname = "raw-add-runtime-check"\nversion = "0.0.0"\nedition = "2024"\n[workspace]\n[dependencies]\nckb-vm = { path = ' + json.dumps(str(ROOT / "deps/ckb-vm")) + ' }\n[[bin]]\nname = "runtime-check"\npath = ' + json.dumps(str(PROOF / "RuntimeCheck.rs")) + '\n')
        # Cargo derives this small harness's lock independently; retain its exact
        # contents/hash, without claiming it equals the production workspace lock.
        run("runtime-lock", ["cargo", "generate-lockfile", "--offline"], runtime)
        report["runtime_cargo_lock_sha256"] = gate.file_hash(runtime / "Cargo.lock")
        output = run("runtime-check", ["cargo", "run", "--locked", "--offline", "--bin", "runtime-check"], runtime)
        rows = [line for line in output.splitlines() if line.startswith('{"status":')]
        if len(rows) != 1:
            raise RuntimeError("missing runtime report")
        result = json.loads(rows[0])
        if result.get("status") != "passed" or result.get("legal_add_encodings") != 32768 or result.get("non_add_neighbor_checks") != 196608 or result.get("detected_rd_mutations") != 32768:
            raise RuntimeError("runtime counts/status differ")
        report["runtime"] = result
        gate.require_equal(gate.source_evidence(main_policy, binaries, aeneas), before, "production inputs changed during field check")
        gate.require_equal(gate.generated_evidence(main_policy), generated_before, "main generated inputs changed")
        gate.require_equal(source_hashes(), policy["sources"], "supplementary sources changed")
        gate.require_equal(gate.file_hash(gate.POLICY), main_policy_sha, "main policy changed")
        gate.require_equal(gate.file_hash(POLICY), report["policy_sha256"], "field policy changed")
        gate.require_equal(gate.file_hash(ROOT / "deps/ckb-vm/Cargo.lock"), report["ckb_cargo_lock_sha256"], "CKB lock changed")
        report["status"] = "passed"
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="failed", error=str(error) or type(error).__name__)
        print("ERROR: " + report["error"], file=sys.stderr)
    finally:
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save()
    print("Report: " + str(report_path), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
