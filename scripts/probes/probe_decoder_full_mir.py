#!/usr/bin/env python3
"""Recheck the archived full-MIR experiment, not the full decoder acceptance gate.

Regenerates both Lean models from pinned LLBC inputs and checks all new modules
in a fresh directory. Existing main/raw proof dependencies are reused. Records
exact theorem types, dependencies, and definition bodies; does not repin policy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "proof/lean/decoder/toolchain/full-mir"
INPUT_HASHES = {
    "FnPtrFullMir.llbc": "ec90aafd39b3a6154f98b73b12d99d7e8a567e2461d1c5baec113b20ac699ee4",
    "OuterRawFullMir.llbc": "88ccbff7bb4eae947d88502ba22ae1cde070135433952b9583bdd23e02f91ca2",
}
BINARY_HASH = "504cd66e34a386174fd763b41fb7fd91f50ab00f8edd5c811562365defcd6554"
MODULES = ["IteratorProof", "OuterFactories", "OuterInit", "OuterLoop", "OuterFetch", "OuterEntry"]
GENERAL_MODULES = ["OuterCache", "OuterPage", "OuterGeneral", "OuterMemoryWitness", "OuterStep", "OuterStepWitness"]
MARKER = "FULL_MIR_AUDIT_JSON="
GENERAL_MARKER = "GENERAL_DECODER_AUDIT_JSON="


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_summary(audit):
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    return {"theorems": {name: {"type_sha256": digest(row["type"]),
                               "axioms": sorted(row["axioms"])}
                         for name, row in audit["theorems"].items()},
            "definitions": {name: digest(body) for name, body in audit["definitions"].items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--translator", required=True, type=Path)
    parser.add_argument("--general", action="store_true",
                        help="also check arbitrary-PC, page-edge, memory witnesses and raw-entry ADD step")
    args = parser.parse_args()
    inputs, binary = args.inputs.resolve(), args.translator.resolve()
    out = Path(tempfile.mkdtemp(prefix="full-mir-check-", dir=ROOT / "artifacts/boundary-check"))
    report = {"status": "running", "directory": str(out), "stages": [],
              "full_decoder_proved": False, "main_gate_adopted": False,
              "rust_reextracted": False, "sysroot_rebuilt": False,
              "clean_dependency_build": False, "entry_scope": "decode_raw, fresh cache, PC=0, all ADD fields",
              "open": ["arbitrary PC", "page-edge fetch", "public decode/MOP extraction",
                       "final ADD connection", "concrete memory contract witnesses", "policy adoption"]}
    protected = [ROOT / p for p in ["proof/lean/audit/step-policy.json",
        "proof/lean/decoder/raw-policy.json", "artifacts/proof-check/report.json",
        "proof/lean/generated/rust/CkbVmProduction.lean",
        "proof/lean/decoder/toolchain/aeneas-join-recovery.patch"]]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    if args.general:
        report.update(entry_scope="arbitrary-PC decode_raw, both fetch widths, cold cache and hit/miss contracts",
                      open=["public decode/MOP extraction and final connection",
                            "actual SparseMemory implementation and physical memory coupling",
                            "opaque execution Machine seed inhabitation", "production tool/policy adoption"])

    def save():
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    def run(label, command, cwd=ROOT, env=None, reject=False):
        log = out / (label + ".log")
        stage = {"stage": label, "command": list(map(str, command)), "cwd": str(cwd),
                 "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        report["stages"].append(stage)
        save()
        with log.open("w") as stream:
            try:
                result = subprocess.run(stage["command"], cwd=cwd, env=env,
                    stdout=stream, stderr=subprocess.STDOUT, timeout=300)
            except subprocess.TimeoutExpired:
                stage["status"] = "timeout-not-proof-evidence"
                save()
                raise
        text = log.read_text(errors="replace")
        stage.update(exit_code=result.returncode, log_sha256=sha(log))
        save()
        if reject:
            marker = reject if isinstance(reject, str) else "Type mismatch"
            if result.returncode != 1 or marker not in text:
                raise RuntimeError(label + ": expected semantic type rejection")
            if re.search(r"unknownIdentifier|maximum.*(recursion|heartbeats|steps)|out of memory", text, re.I):
                raise RuntimeError(label + ": infrastructure failure is not negative evidence")
        elif result.returncode or "sorryAx" in text:
            raise RuntimeError(label + ": failed; see " + str(log))
        print(label + ": " + ("expected rejection" if reject else "PASS"), flush=True)
        return text

    try:
        report["protected_before"] = before
        if sha(binary) != BINARY_HASH:
            raise RuntimeError("unreviewed experimental translator binary")
        source = binary.parents[3]
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        patch = subprocess.check_output(["git", "diff", "--", "src"], cwd=source)
        if commit != "379890b54b4961dc7729e314c6eefdc09fe50981" or hashlib.sha256(patch).hexdigest() != sha(
                ROOT / "proof/lean/decoder/toolchain/fnptr-experimental/aeneas-fnptr-experimental.patch"):
            raise RuntimeError("experimental translator source identity mismatch")
        report.update(translator_sha256=sha(binary), translator_commit=commit,
                      patch_sha256=hashlib.sha256(patch).hexdigest())
        report["sources"] = {str(p.relative_to(ROOT)): sha(p) for p in FIXTURES.iterdir() if p.is_file()}
        report["sources"][str(Path(__file__).resolve().relative_to(ROOT))] = sha(Path(__file__).resolve())
        run("source-baseline", [sys.executable, ROOT / "scripts/ckb_source_baseline.py"])
        sys.setrecursionlimit(100000)
        report["inputs"] = {}
        for name, expected in INPUT_HASHES.items():
            p = inputs / name
            if sha(p) != expected:
                raise RuntimeError("archived LLBC input mismatch: " + name)
            data = json.loads(p.read_bytes())
            if data["has_errors"]:
                raise RuntimeError("LLBC contains frontend errors")
            report["inputs"][name] = {"sha256": sha(p), "options": data["translated"]["options"],
                                      "charon_version": data["charon_version"]}
        sysroot = Path(report["inputs"]["OuterRawFullMir.llbc"]["options"]["sysroot"])
        libs = sorted((sysroot / "lib/rustlib/x86_64-unknown-linux-gnu/lib").glob("*"))
        if not libs:
            raise RuntimeError("archived sysroot is absent")
        report["sysroot_libraries"] = {p.name: sha(p) for p in libs if p.is_file()}
        models = out / "models"
        for name in INPUT_HASHES:
            extra = ["-namespace", "OuterDecodeCandidate"] if name.startswith("Outer") else []
            run("translate-" + Path(name).stem, [binary, "-backend", "lean", "-abort-on-error",
                "-no-progress-bar", "-checks", *extra, "-dest", models, inputs / name])
        raw = models / "OuterRawFullMir.lean"
        raw_text = raw.read_text()
        if raw_text.count("import Aeneas\n") != 1:
            raise RuntimeError("unexpected generated import layout")
        linked = models / "OuterRawLinked.lean"
        linked.write_text(raw_text.replace("import Aeneas\n", "import Aeneas\nimport CkbVmProduction\n", 1))
        report["compatibility"] = {"operation": "insert only import CkbVmProduction after import Aeneas",
                                   "raw_sha256": sha(raw), "linked_sha256": sha(linked)}
        report["opaque_declarations"] = re.findall(r"^(?:axiom|opaque)\s+([^\s:{]+)", raw_text, re.M)
        if re.search(r"^axiom .*IntoIterator.*into_iter", raw_text, re.M):
            raise RuntimeError("shared iterator entry regressed to an axiom")
        project = ROOT / "proof/lean/theorems"
        lean = subprocess.check_output(["lake", "env", "which", "lean"], cwd=project, text=True).strip()
        base = subprocess.check_output(["lake", "env", "printenv", "LEAN_PATH"], cwd=project, text=True).strip()
        dependencies = [ROOT / "artifacts/boundary-check/raw-add-0__trc1y/models",
                        ROOT / "artifacts/boundary-check/raw-fields-6zf2keby/models"]
        env = dict(os.environ, LEAN_PATH=os.pathsep.join(map(str, [models, *dependencies])) + os.pathsep + base)
        report["initial_new_oleans"] = len(list(models.glob("*.olean")))
        if report["initial_new_oleans"]:
            raise RuntimeError("new model cache is not empty")
        for model in [models / "FnPtrFullMir.lean", raw, linked]:
            run("kernel-" + model.stem, [lean, "--root=" + str(models), "-o",
                models / (model.stem + ".olean"), model], project, env)
        for module in MODULES + (GENERAL_MODULES if args.general else []):
            run("kernel-" + module, [lean, "--root=" + str(FIXTURES), "-o",
                models / (module + ".olean"), FIXTURES / (module + ".lean")], project, env)
        output = run("kernel-audit", [lean, FIXTURES / "ExportFullMirAudit.lean"], project, env)
        records = [line[len(MARKER):] for line in output.splitlines() if line.startswith(MARKER)]
        if len(records) != 1:
            raise RuntimeError("expected one complete environment audit")
        audit = json.loads(records[0])
        if len(audit["theorems"]) != 32 or len(audit["definitions"]) != 16:
            raise RuntimeError("incomplete theorem/definition audit")
        for name, entry in audit["theorems"].items():
            if any(re.search(r"sorryAx|_native|native_decide", a) for a in entry["axioms"]):
                raise RuntimeError("unaccepted proof dependency: " + name)
        (out / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
        report["audit_sha256"] = sha(out / "audit.json")
        snapshot = json.loads((FIXTURES / "audit-snapshot.json").read_text())
        report["audit_snapshot_sha256"] = sha(FIXTURES / "audit-snapshot.json")
        summary = audit_summary(audit)
        if summary != {k: snapshot[k] for k in ["theorems", "definitions"]}:
            raise RuntimeError("exact experimental theorem types/axioms/definitions changed; review required")
        report["theorems"] = summary["theorems"]
        if args.general:
            output = run("kernel-general-audit", [lean, FIXTURES / "ExportGeneralAudit.lean"], project, env)
            records = [line[len(GENERAL_MARKER):] for line in output.splitlines() if line.startswith(GENERAL_MARKER)]
            if len(records) != 1:
                raise RuntimeError("expected one general decoder environment audit")
            general = json.loads(records[0])
            if len(general["theorems"]) != 24 or len(general["definitions"]) != 9 or len(general["contracts"]) != 3:
                raise RuntimeError("incomplete general decoder audit")
            for name, entry in general["theorems"].items():
                if any(re.search(r"sorryAx|_native|native_decide", a) for a in entry["axioms"]):
                    raise RuntimeError("unaccepted general decoder proof dependency: " + name)
            general_summary = audit_summary(general)
            general_summary["contracts"] = {name: hashlib.sha256(value.encode()).hexdigest()
                                             for name, value in general["contracts"].items()}
            snapshot_path = FIXTURES / "general-audit-snapshot.json"
            general_snapshot = json.loads(snapshot_path.read_text())
            if general_summary != {k: general_snapshot[k] for k in ["theorems", "definitions", "contracts"]}:
                raise RuntimeError("general decoder exact types/dependencies/bodies/contracts changed; review required")
            (out / "general-audit.json").write_text(json.dumps(general, indent=2) + "\n")
            report["general_audit_sha256"] = sha(out / "general-audit.json")
            report["general_snapshot_sha256"] = sha(snapshot_path)
            report["theorems"].update(general_summary["theorems"])
            bad_memory = out / "bad-memory"
            bad_memory.mkdir()
            text = (FIXTURES / "OuterMemoryWitness.lean").read_text()
            needle = "then .ok (.Ok (highHalf w), ())"
            if text.count(needle) != 1:
                raise RuntimeError("halfword negative test no longer matches")
            (bad_memory / "OuterMemoryWitness.lean").write_text(text.replace(needle,
                "then .ok (.Ok (lowHalf w), ())", 1))
            run("negative-wrong-high-half", [lean, bad_memory / "OuterMemoryWitness.lean"], project, env,
                reject="unsolved goals")
        # Valid Lean syntax with an intentionally wrong result; rejection must be semantic.
        negative = out / "WrongEntry.lean"
        negative.write_text("import OuterEntry\nopen Aeneas.Std OuterAdd OuterDecodeCandidate\n"
            "example : fresh_decoder = Result.fail .panic := by\n  exact fresh_initial\n")
        run("negative-wrong-entry", [lean, negative], project, env, reject=True)
        negative = out / "WrongCache.lean"
        negative.write_text("import OuterLoop\nopen Aeneas.Std OuterAdd\n"
            "example (a : Cache) (k : Usize) (p : U64 × U64) (h : k.val < a.val.length) :\n"
            "  Array.index_usize (a.set k p) k = Result.fail .arrayOutOfBounds := by\n"
            "  exact cache_write_visible a k p h\n")
        run("negative-wrong-cache", [lean, negative], project, env, reject=True)
        weakened = out / "weakened"
        weakened.mkdir()
        text = (FIXTURES / "OuterEntry.lean").read_text()
        needle = "theorem decode_raw_zero {M R : Type}"
        if text.count(needle) != 1:
            raise RuntimeError("weakening negative test no longer matches")
        (weakened / "OuterEntry.lean").write_text(text.replace(needle,
            "theorem decode_raw_zero (unused : False) {M R : Type}", 1))
        bad_env = dict(env, LEAN_PATH=str(weakened) + os.pathsep + env["LEAN_PATH"])
        run("negative-weakened-compiles", [lean, "--root=" + str(weakened), "-o",
            weakened / "OuterEntry.olean", weakened / "OuterEntry.lean"], project, bad_env)
        bad = run("negative-weakened-audit", [lean, FIXTURES / "ExportFullMirAudit.lean"], project, bad_env)
        records = [line[len(MARKER):] for line in bad.splitlines() if line.startswith(MARKER)]
        if len(records) != 1:
            raise RuntimeError("missing weakening audit")
        bad_summary = audit_summary(json.loads(records[0]))
        original = summary["theorems"]["OuterAdd.decode_raw_zero"]
        changed = bad_summary["theorems"]["OuterAdd.decode_raw_zero"]
        if original["type_sha256"] == changed["type_sha256"] or original["axioms"] != changed["axioms"]:
            raise RuntimeError("weakening test did not isolate the changed theorem type")
        report["weakened_premise_rejected_by_type_audit"] = True
        run("source-baseline-after", [sys.executable, ROOT / "scripts/ckb_source_baseline.py"])
        report["protected_after"] = {str(p.relative_to(ROOT)): sha(p) for p in protected}
        if report["protected_after"] != before:
            raise RuntimeError("protected baseline changed")
        report["status"] = "PASS"
    except Exception as error:
        report.update(status="FAIL", error=str(error))
        raise
    finally:
        save()
        print("Report: " + str(out / "report.json"), flush=True)


if __name__ == "__main__":
    main()
