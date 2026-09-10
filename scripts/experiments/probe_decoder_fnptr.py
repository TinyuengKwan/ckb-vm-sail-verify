#!/usr/bin/env python3
"""Experimental translator regression probe, NOT a production proof gate.

Never changes tool policy, production source, or installed support libraries.
An outer model compiling does not establish a decoder correspondence theorem.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "proof/lean/decoder/toolchain/fnptr-experimental"
BASE = "379890b54b4961dc7729e314c6eefdc09fe50981"
STANDARD = {"propext", "Classical.choice", "Quot.sound"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translator", type=Path, required=True)
    parser.add_argument("--outer-llbc", type=Path)
    args = parser.parse_args()
    binary = args.translator.resolve()
    source = binary.parents[3]
    charon = Path.home() / ".local/share/aeneas/charon"
    old_policy_path = ROOT / "proof/lean/decoder/raw-policy.json"
    old_policy = json.loads(old_policy_path.read_text())
    accepted = ROOT / old_policy["tool_binary_path"]
    out = Path(tempfile.mkdtemp(prefix="fnptr-regression-", dir=ROOT / "artifacts/boundary-check"))
    report = {"status": "running", "directory": str(out), "stages": [],
              "production_decoder_proved": False, "main_proof_check_stage": False,
              "tool_adopted": False, "clean_dependency_build": False,
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def save():
        (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    def run(label, command, cwd=ROOT, env=None, reject=None):
        command = list(map(str, command))
        log = out / (label + ".log")
        stage = {"stage": label, "command": command, "cwd": str(cwd), "log": str(log)}
        report["stages"].append(stage)
        save()
        with log.open("w") as stream:
            result = subprocess.run(command, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=600)
        output = log.read_text(errors="replace")
        stage.update(exit_code=result.returncode, log_sha256=sha(log))
        save()
        if reject:
            if result.returncode not in (1, 2) or not re.search(reject, output):
                raise RuntimeError(label + ": expected specific rejection not observed")
            if re.search(r"maximum heartbeats|maximum recursion|out of memory|unknownIdentifier",
                         output, re.IGNORECASE):
                raise RuntimeError(label + ": unrelated failure is not negative evidence")
        elif result.returncode:
            raise RuntimeError(label + ": failed, see " + str(log))
        print(label + ": " + ("rejected as expected" if reject else "PASS"), flush=True)
        return output

    def extract(label, rust, llbc):
        run("charon-" + label, [charon, "rustc", "--preset=aeneas", "--include",
            "core::option::_", "--dest-file", llbc, "--", rust, "--crate-type", "lib"])
        if json.loads(llbc.read_text())["has_errors"]:
            raise RuntimeError(label + ": LLBC contains errors")

    def translate(label, llbc, dest, translator=binary, reject=None, extra=()):
        return run(label, [translator, "-backend", "lean", "-abort-on-error",
            "-no-progress-bar", "-checks", *extra, "-dest", dest, llbc], reject=reject)

    protected = [old_policy_path, accepted, ROOT / "proof/lean/audit/step-policy.json",
                 ROOT / "artifacts/proof-check/report.json"]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    try:
        report["protected_before"] = before
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        patch = subprocess.check_output(["git", "diff", "--", "src"], cwd=source)
        if commit != BASE or digest(patch) != sha(FIXTURES / "aeneas-fnptr-experimental.patch"):
            raise RuntimeError("candidate source differs from the published experimental patch")
        report.update(source_commit=commit, source_patch_sha256=digest(patch),
                      translator_sha256=sha(binary), charon_sha256=sha(charon))
        report["fixtures"] = {p.name: sha(p) for p in FIXTURES.iterdir() if p.is_file()}
        run("source-baseline", ["python3", ROOT / "scripts/ckb_source_baseline.py"])
        llbc = out / "FnPtrCases.llbc"
        extract("cases", FIXTURES / "fnptr_cases.rs", llbc)
        report["llbc_sha256"] = sha(llbc)
        translate("accepted-tool-negative", llbc, out / "old-tool", accepted,
                  reject="Arrow types are not supported yet")
        models = out / "models"
        translate("candidate", llbc, models)
        project = ROOT / "proof/lean/theorems"
        lean = subprocess.check_output(["lake", "env", "which", "lean"], cwd=project,
                                       text=True, timeout=180).strip()
        lean_path = subprocess.check_output(["lake", "env", "printenv", "LEAN_PATH"],
                                           cwd=project, text=True, timeout=180).strip()
        env = dict(os.environ, LEAN_PATH=str(models) + os.pathsep + lean_path)
        report["initial_new_oleans"] = len(list(models.glob("*.olean")))
        if report["initial_new_oleans"]:
            raise RuntimeError("new model cache is not empty")
        model = models / "FnPtrCases.lean"
        run("kernel-model", [lean, "--root=" + str(models), model,
            "-o", models / "FnPtrCases.olean"], project, env)
        proof = FIXTURES / "FnPtrProof.lean"
        audit = run("kernel-regressions", [lean, proof], project, env)
        counts = {}
        for line in audit.splitlines():
            match = re.fullmatch(r"'(FnPtrRegression\.[^']+)' (.*)", line)
            if not match:
                continue
            name, tail = match.groups()
            if tail == "does not depend on any axioms":
                axioms = []
            else:
                m = re.fullmatch(r"depends on axioms: \[(.*)\]", tail)
                if not m:
                    raise RuntimeError("unrecognized axiom audit line")
                axioms = m[1].split(", ") if m[1] else []
            if not set(axioms) <= STANDARD:
                raise RuntimeError("non-standard regression axiom: " + name)
            counts[name] = axioms
        if len(counts) != 16:
            raise RuntimeError("expected all 16 regression theorem audits")
        report["regression_axioms"] = counts
        report["model_sha256"] = sha(model)
        # This newly exposed entry remains opaque. Do not claim the whole Rust
        # for-loop entry is closed merely because the loop body is proved.
        report["open_iterator_entry"] = bool(re.search(
            r"axiom SharedAVec\..*into_iter", model.read_text()))
        bad = out / "swapped-call-arguments"
        bad.mkdir()
        text = model.read_text()
        if text.count("f bits version") != 1:
            raise RuntimeError("mutation anchor is not unique")
        (bad / model.name).write_text(text.replace("f bits version", "f version bits"))
        bad_env = dict(env, LEAN_PATH=str(bad) + os.pathsep + lean_path)
        run("kernel-mutated-model", [lean, "--root=" + str(bad), bad / model.name,
            "-o", bad / "FnPtrCases.olean"], project, bad_env)
        run("wrong-arguments-negative", [lean, proof], project, bad_env,
            reject=r"rfl.*failed|Tactic.*rfl.*failed|Type mismatch")
        negatives = {
            "borrow": "locally quantified regions",
            "abi": "Unsupported function pointer signature",
            "static_result": "Borrowed function pointer result",
            "unsafe": "Unsupported function pointer signature",
            "zero": "Unsupported function pointer signature",
        }
        for key, reason in negatives.items():
            negative = out / (key + ".llbc")
            extract(key, FIXTURES / ("fnptr_" + key + "_rejected.rs"), negative)
            translate("negative-" + key, negative, out / ("negative-" + key), reject=reason)
        if args.outer_llbc:
            outer = args.outer_llbc.resolve()
            if json.loads(outer.read_text())["has_errors"]:
                raise RuntimeError("outer LLBC has errors")
            report["outer_llbc"] = str(outer)
            report["outer_llbc_sha256"] = sha(outer)
            dest = out / "outer"
            translate("outer-translate", outer, dest, extra=("-namespace", "OuterDecodeCandidate"))
            outer_model = dest / (outer.stem + ".lean")
            run("kernel-outer", [lean, "--root=" + str(dest), outer_model,
                "-o", dest / (outer.stem + ".olean")], project, env)
            report["outer_model_sha256"] = sha(outer_model)
            report["outer_model_kernel_checked"] = True
            report["outer_opaque_declarations"] = re.findall(
                r"^axiom ([^\s(]+)", outer_model.read_text(), re.MULTILINE)
            for name in ("DefaultDecoder.Insts.Ckb_vmDecoderInstDecoder.new", "DefaultDecoder.decode_raw",
                         "DefaultDecoder.decode_bits", "DefaultDecoder.decode_raw_loop.body"):
                if not re.search(r"^def ckb_vm\.decoder\." + re.escape(name) + r"\b",
                                 outer_model.read_text(), re.MULTILINE):
                    raise RuntimeError("missing actual outer definition: " + name)
        run("source-baseline-after", ["python3", ROOT / "scripts/ckb_source_baseline.py"])
        report["protected_after"] = {str(p.relative_to(ROOT)): sha(p) for p in protected}
        if report["protected_after"] != before:
            raise RuntimeError("an accepted baseline artifact changed")
        report["status"] = "experimental-regressions-pass"
    except BaseException as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save()
        print("Experimental report: " + str(out / "report.json"), flush=True)


if __name__ == "__main__":
    main()
