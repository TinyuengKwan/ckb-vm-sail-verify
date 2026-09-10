#!/usr/bin/env python3
"""Independent raw ADD gate. Never refreshes policy or changes production tools.

Closes i::factory -> Sail ext_decode -> production ADD execution, not the outer
DefaultDecoder interface. Main dependencies are checked but their cache is reused.
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
import check_raw_add_fields as fields

ROOT = gate.ROOT
PROOF = ROOT / "proof/lean/decoder"
POLICY = PROOF / "raw-policy.json"
CONFIG = PROOF / "extraction.json"
MODULES = ["SailRawAdd", "RawEncoding", "RustRawAdd", "DecodedRawAdd",
           "RawAddStep", "RawAddWitness", "MiniProof"]
SOURCES = ["proof/lean/decoder/" + m + ".lean" for m in MODULES] + [
    "proof/lean/decoder/ExportRawAudit.lean", "proof/lean/decoder/FactoryRoot.rs",
    "proof/lean/decoder/extraction.json", "proof/lean/decoder/toolchain/aeneas-join-recovery.patch",
    "proof/lean/decoder/toolchain/decoder_shared_closure.rs",
    "proof/lean/decoder/toolchain/opam-packages.txt", "scripts/build_decoder_toolchain.sh",
    "scripts/check_raw_add.py"]
MARKER = "RAW_ADD_AUDIT_JSON="


def source_hashes():
    return {p: gate.file_hash(ROOT / p) for p in SOURCES}


def normalized_model(path):
    text = path.read_text().replace(str(ROOT), "<repo>")
    for rel in ("proof/lean/decoder/FactoryRoot.rs", "proof/lean/decoder/toolchain/decoder_shared_closure.rs"):
        text = re.sub(r"Source: '[^'\n]*" + re.escape(rel) + "'", "Source: '<repo>/" + rel + "'", text)
    return gate.digest(text.encode())


def audit_from(output):
    rows = [line[len(MARKER):] for line in output.splitlines() if line.startswith(MARKER)]
    if len(rows) != 1:
        raise RuntimeError("expected exactly one raw ADD audit record")
    return json.loads(rows[0])


def check_audit(audit, policy):
    for entry in audit["theorems"].values():
        if any("sorryAx" in n or "_native" in n or "native_decide" in n for n in entry["axioms"]):
            raise RuntimeError("unaccepted sorry/native axiom")
    if any(b == "NOT_A_DEFINITION" for b in audit["definitions"].values()):
        raise RuntimeError("actual decoder operation replaced by a non-definition")
    gate.require_equal(fields.audit_summary(audit), policy["audit"], "raw ADD exact types/bodies/axioms")


def main():
    evidence = Path(tempfile.mkdtemp(prefix="raw-add-", dir=ROOT / "artifacts/boundary-check"))
    report = {"status": "running", "directory": str(evidence), "stages": [],
              "scope": "RV64 VERSION2 production i::factory and Sail ext_decode, connected to production ADD step",
              "outer_default_decoder_closed": False, "main_proof_check_stage": False,
              "clean_dependency_build": False,
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    report_path = evidence / "report.json"
    def save():
        gate.write_json(report_path, report)
    save()
    print("Raw ADD proof check: " + str(evidence), flush=True)
    try:
        policy = json.loads(POLICY.read_text())
        config = json.loads(CONFIG.read_text())
        main_policy = json.loads(gate.POLICY.read_text())
        report["policy_sha256"] = gate.file_hash(POLICY)
        report["main_policy_sha256"] = gate.file_hash(gate.POLICY)
        gate.require_equal(source_hashes(), policy["sources"], "raw ADD sources")
        env, binaries, aeneas_home, lake = gate.tools_and_environment(main_policy)
        before = gate.source_evidence(main_policy, binaries, aeneas_home)
        generated_before = gate.generated_evidence(main_policy)
        report["source_baseline"] = before["ckb_source_baseline"]
        report["tools"] = before["tool_binaries"]
        translator = Path(os.environ.get("AENEAS_DECODER_BIN", str(ROOT / policy["tool_binary_path"]))).resolve()
        gate.require_equal(gate.file_hash(translator), policy["tool_binary_sha256"], "reviewed patched translator")
        report["decoder_translator_sha256"] = gate.file_hash(translator)
        report["decoder_translator"] = str(translator)
        source = translator.parents[3]
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        gate.require_equal(commit, config["aeneas_source_commit"], "decoder translator source commit")
        patch = subprocess.check_output(["git", "diff", "--", "src"], cwd=source)
        gate.require_equal(gate.digest(patch), gate.file_hash(ROOT / config["aeneas_patch"]), "decoder translator patch")
        charon_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source / "charon", text=True).strip()
        gate.require_equal(charon_commit, config["charon_source_commit"], "translator Charon source")
        report["sources"] = source_hashes()
        report["field_policy_sha256"] = gate.file_hash(fields.POLICY)
        gate.require_equal(report["field_policy_sha256"], policy["field_policy_sha256"], "field proof policy")

        def run(label, cmd, cwd=ROOT, run_env=None, rejection=None, timeout=600):
            print("==> " + label, flush=True)
            log = evidence / (label + ".log")
            with log.open("w") as stream:
                result = subprocess.run(cmd, cwd=cwd, env=run_env or env,
                    stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            output = log.read_text(errors="replace")
            report["stages"].append({"name": label, "command": list(map(str, cmd)), "cwd": str(cwd),
                "exit_code": result.returncode, "log_sha256": gate.file_hash(log), "expected_rejection": rejection})
            save()
            if rejection:
                if result.returncode == 0 or rejection not in output or "unknown module" in output:
                    raise RuntimeError(label + " failed to reject for the intended reason")
                if re.search(r"maximum recursion depth|maxHeartbeats|deterministic timeout|out of memory|unknownIdentifier", output, re.I):
                    raise RuntimeError(label + " failed for a resource/import reason, not the intended semantic rejection")
            elif result.returncode or re.search(r"PANIC|uncaught exception|Stack overflow|Internal error", output, re.I):
                raise RuntimeError(label + " failed; see " + str(log))
            return output

        # Re-extract/recompile fields, re-run all existing field negatives and
        # the 32768-case production-factory runtime check in its own fresh tree.
        output = run("field-gate", [sys.executable, str(ROOT / "scripts/check_raw_add_fields.py")], timeout=1200)
        rows = [line[8:] for line in output.splitlines() if line.startswith("Report: ")]
        if len(rows) != 1:
            raise RuntimeError("field report missing")
        field_report_path = Path(rows[0])
        field_report = json.loads(field_report_path.read_text())
        gate.require_equal(field_report["status"], "passed", "field gate")
        report["field_report"] = str(field_report_path)
        report["field_report_sha256"] = gate.file_hash(field_report_path)
        report["runtime"] = field_report["runtime"]
        field_models = field_report_path.parent / "models"

        crate = evidence / "crate"
        crate.mkdir()
        (crate / "Cargo.toml").write_text('[package]\nname = "raw-add-decoder-connection"\nversion = "0.0.0"\nedition = "2024"\n[workspace]\n[dependencies]\nckb-vm = { path = ' + json.dumps(str(ROOT / "deps/ckb-vm")) + ' }\n[lib]\npath = ' + json.dumps(str(PROOF / "FactoryRoot.rs")) + '\n')
        env["CARGO_TARGET_DIR"] = str(evidence / "cargo-target")
        run("cargo-lock", ["cargo", "generate-lockfile", "--offline"], crate)
        report["extraction_cargo_lock_sha256"] = gate.file_hash(crate / "Cargo.lock")
        gate.require_equal(report["extraction_cargo_lock_sha256"], policy["extraction_cargo_lock_sha256"], "decoder harness dependency lock")
        llbc = evidence / "FactoryScoped.llbc"
        args = [str(binaries["charon"]), "cargo", "--preset=aeneas", "--start-from", config["root"]]
        for key in ("include", "opaque"):
            for pat in config[key]:
                args += ["--" + key, pat]
        run("charon-factory", args + ["--dest-file", str(llbc), "--", "--lib", "--locked"], crate)
        if json.loads(llbc.read_text())["has_errors"]:
            raise RuntimeError("factory LLBC contains extraction errors")
        report["llbc_sha256"] = gate.file_hash(llbc)
        models = evidence / "models"
        run("aeneas-factory", [str(translator)] + config["aeneas_args"] + ["-namespace", config["namespace"], "-dest", str(models), str(llbc)])
        gate.require_equal(normalized_model(models / "FactoryScoped.lean"), policy["generated_normalized_sha256"], "factory model")

        mini = evidence / "MiniComplete.llbc"
        run("charon-regression", [str(binaries["charon"]), "rustc", "--preset=aeneas", "--include", "core::option::_",
            "--dest-file", str(mini), "--", str(PROOF / "toolchain/decoder_shared_closure.rs"), "--crate-type", "lib"])
        if json.loads(mini.read_text())["has_errors"]:
            raise RuntimeError("regression LLBC contains extraction errors")
        run("aeneas-regression", [str(translator)] + config["aeneas_args"] + ["-dest", str(models), str(mini)])
        gate.require_equal(normalized_model(models / "MiniComplete.lean"), policy["regression_model_normalized_sha256"], "regression model")
        run("strict-join-negative", [str(translator)] + config["aeneas_args"] + ["-strict-joins", "-dest", str(evidence / "strict-negative"), str(mini)], rejection="Context collapse does not support concrete shared borrows")

        project = ROOT / "proof/lean/theorems"
        lean = subprocess.check_output([lake, "env", "which", "lean"], cwd=project, env=env, text=True, timeout=180).strip()
        lean_path = subprocess.check_output([lake, "env", "printenv", "LEAN_PATH"], cwd=project, env=env, text=True, timeout=180).strip()
        env["LEAN_PATH"] = str(models) + os.pathsep + str(field_models) + os.pathsep + lean_path
        report["initial_new_oleans"] = len(list(models.glob("*.olean")))
        gate.require_equal(report["initial_new_oleans"], 0, "empty new-model cache")
        def compile_module(module, directory=PROOF, run_env=None, label=None, rejection=None):
            return run(label or "kernel-" + module, [lean, "--root=" + str(directory), str(directory / (module + ".lean")),
                "-o", str(models / (module + ".olean"))] if not rejection else
                [lean, "--root=" + str(directory), str(directory / (module + ".lean"))], project, run_env, rejection)
        for module in ("FactoryScoped", "MiniComplete"):
            compile_module(module, models)
        for module in MODULES:
            compile_module(module)
        audit = audit_from(run("raw-audit", [lean, str(PROOF / "ExportRawAudit.lean")], project))
        gate.write_json(evidence / "raw-audit.json", audit)
        check_audit(audit, policy)
        report["axiom_counts"] = {n: len(v["axioms"]) for n, v in audit["theorems"].items()}

        # Three independent failure modes: raw selector, assembled encoding,
        # and a theorem made vacuous while retaining a compilable proof.
        for label, module, old, new in [
            ("wrong-selector", "SailRawAdd", "rd) 0x33#7", "rd) 0x13#7"),
            ("wrong-register-field", "DecodedRawAdd",
             "((internal rd rs1 rs2).bv >>> 40).setWidth 8 = rs2.zeroExtend 8",
             "((internal rd rs1 rs2).bv >>> 40).setWidth 8 = rs1.zeroExtend 8")]:
            directory = evidence / label
            directory.mkdir()
            text = (PROOF / (module + ".lean")).read_text()
            if text.count(old) != 1:
                raise RuntimeError("negative mutation anchor not unique")
            (directory / (module + ".lean")).write_text(text.replace(old, new))
            compile_module(module, directory, label=label, rejection="error:")
        directory = evidence / "false-premise"
        directory.mkdir()
        text = (PROOF / "RawEncoding.lean").read_text()
        old = "theorem raw_add_iff (w : BitVec 32)"
        if text.count(old) != 1:
            raise RuntimeError("False mutation anchor not unique")
        (directory / "RawEncoding.lean").write_text(text.replace(old, "theorem raw_add_iff (unjustified : False) (w : BitVec 32)"))
        bad_env = env.copy()
        bad_env["LEAN_PATH"] = str(directory) + os.pathsep + env["LEAN_PATH"]
        run("false-premise-compile", [lean, "--root=" + str(directory), str(directory / "RawEncoding.lean"), "-o", str(directory / "RawEncoding.olean")], project, bad_env)
        bad = audit_from(run("false-premise-audit", [lean, str(PROOF / "ExportRawAudit.lean")], project, bad_env))
        try:
            check_audit(bad, policy)
        except RuntimeError:
            report["false_premise_type_rejected"] = True
        else:
            raise RuntimeError("audit accepted added False premise")

        gate.require_equal(gate.source_evidence(main_policy, binaries, aeneas_home), before, "production inputs changed")
        gate.require_equal(gate.generated_evidence(main_policy), generated_before, "main models changed")
        gate.require_equal(source_hashes(), policy["sources"], "raw ADD sources changed")
        gate.require_equal(gate.file_hash(POLICY), report["policy_sha256"], "raw policy changed")
        gate.require_equal(gate.file_hash(gate.POLICY), report["main_policy_sha256"], "main policy changed")
        gate.require_equal(gate.file_hash(translator), policy["tool_binary_sha256"], "decoder tool changed")
        report["raw_factory_decode_closed"] = True
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
