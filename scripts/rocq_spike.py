#!/usr/bin/env python3
"""Reproduce both specific Rocq NO-GO results; missing inputs never pass.

Existing generation inputs are checked against the Lean production policy.
The rebuilt main profile regenerates Sail Rocq inputs and uses explicit private
OPAM contexts; production LLBC must already satisfy its generation provenance.
The legacy profile still requires its Sail inputs to be generated beforehand.
Each run preserves a new evidence directory, including when it fails.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import check_proof as proof
import rocq_context as rebuilt_context

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    "ocaml": "5.2.1", "rocq-core": "9.1.1", "rocq-runtime": "9.1.1",
    "rocq-stdlib": "9.0.0", "rocq-stdpp": "1.13.0",
    "rocq-stdpp-bitvector": "1.13.0", "rocq-sail-stdpp": "0.20.2",
}
INFRA_FAILURE = re.compile(
    r"out of memory|stack overflow|segmentation fault|killed|timed? out|"
    r"cannot find a physical path|cannot find library|no such file|anomaly", re.I)
RUST_ERROR = ('The term "result bool" has type "Type -> Type" '
              'which should be Set, Prop or Type.')
SAIL_ERROR = "The reference e_div was not found in the current environment."


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_failure(kind, code, log):
    require(code == 1, f"{kind}: expected compiler rejection with exit 1, got {code}")
    require(not INFRA_FAILURE.search(log), f"{kind}: infrastructure failure is not NO-GO evidence")
    errors = re.findall(r"(?m)^Error:\s*([\s\S]*?)(?=^Error:|\Z)", log)
    require(len(errors) == 1, f"{kind}: expected exactly one compiler error")
    message = " ".join(errors[0].split())
    if kind == "rust":
        require("core_cmp_PartialEq_t" in message and message.endswith(RUST_ERROR),
                "rust: failure does not match the reviewed result-type conflict")
    elif kind == "sail":
        require(message == SAIL_ERROR, "sail: failure does not match the reviewed missing e_div")
    else:
        raise RuntimeError("unknown NO-GO classification: " + kind)


def check_packages(log):
    packages = {}
    for line in log.splitlines():
        words = line.split()
        require(len(words) == 2 and words[0] not in packages, "invalid OPAM package listing")
        packages[words[0]] = words[1]
    for name, version in PACKAGES.items():
        require(packages.get(name) == version, f"OPAM package pin mismatch: {name}={version}")
    return packages


def inputs(root, *, include_sail=True, rebuilt=False):
    paths = [
        "target/CkbVmProduction.llbc", "proof/lean/generated/rust/SOURCE_BASELINE.json",
        "proof/rocq/generated/sail/rv64d_types.v", "proof/rocq/generated/sail/rv64d.v",
        "deps/sail-riscv/handwritten_support/riscv_extras.v",
        "proof/rocq/spike/result_shadowing.v", "proof/rocq/spike/missing_e_div.v",
        "sail-model/build/ckb_vm_config.json", "proof/lean/audit/step-policy.json",
        "scripts/rocq_spike.py", "scripts/rocq_spike.sh",
    ]
    if not include_sail:
        paths = [name for name in paths if not name.startswith('proof/rocq/generated/sail/')]
    if rebuilt:
        paths += [*rebuilt_context.SOURCE_FILES, rebuilt_context.INSTALL_REPORT,
                  'scripts/generate_proof_model.sh', 'scripts/sail_model_transaction.py',
                  'deps/sail-riscv/build/CMakeCache.txt']
    missing = [name for name in paths if not (root / name).is_file()]
    require(not missing, "required spike input missing (no SKIP): " + ", ".join(missing))
    return {name: sha(root / name) for name in paths}


def new_directory(root, requested=None):
    if requested:
        path = Path(requested).resolve()
        # Existing locations, including roots and symlinks, are never removed.
        path.mkdir(parents=True, exist_ok=False)
        return path
    parent = root / "artifacts/rocq-spike"
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="run-", dir=parent)).resolve()


def save(out, report):
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")


def stage(out, report, env, name, command, cwd, rejection=None, timeout=600):
    log_path = out / (name + ".log")
    row = {"name": name, "command": list(map(str, command)), "cwd": str(cwd), "status": "running"}
    report["stages"].append(row)
    save(out, report)
    print("==> rocq-spike: " + name, flush=True)
    try:
        with log_path.open("w") as stream:
            proc = subprocess.run(row["command"], cwd=cwd, env=env,
                                  stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        row["exit_code"] = proc.returncode
        log = log_path.read_text(errors="replace")
        if rejection:
            check_failure(rejection, proc.returncode, log)
        else:
            require(proc.returncode == 0 and not INFRA_FAILURE.search(log),
                    name + ": required successful stage failed")
        row["status"] = "expected_rejection" if rejection else "passed"
        return log
    except BaseException as error:
        row.update(status="failed", error=str(error) or type(error).__name__)
        raise
    finally:
        if log_path.exists():
            row.update(log=log_path.name, log_sha256=sha(log_path))
        save(out, report)


def execute(out, report):
    policy = json.loads(proof.POLICY.read_text())
    rebuilt = rebuilt_context.selected(policy)
    before = inputs(ROOT, include_sail=not rebuilt, rebuilt=rebuilt)
    report["input_sha256"] = before
    env, binaries, home, lake = proof.tools_and_environment(policy)
    source = proof.source_evidence(policy, binaries, home)
    generated = proof.generated_evidence(policy)
    report.update(source=source, generated=generated, policy_sha256=sha(proof.POLICY))
    for key in ["COQPATH", "ROCQPATH", "OCAMLPATH"]:
        env.pop(key, None)
    if rebuilt:
        installation, rocq_env, context_record = rebuilt_context.resolve(ROOT, env, home)
        require(os.environ.get('ROCQ_SPIKE_SWITCH') in (None, installation['switch']),
                'conflicting Rocq switch override for rebuilt profile')
        switch = installation['switch']
        expected_commands = rebuilt_context.commands(ROOT, out, env, binaries, installation)
        report.update(execution_profile=rebuilt_context.PROFILE, tool_context=context_record,
                      pre_generation_input_sha256=before)
    else:
        switch = os.environ.get("ROCQ_SPIKE_SWITCH", "rocq-spike")
    require(switch and not switch.startswith("-"), "invalid Rocq switch")
    report["opam_switch"] = switch
    opam = ["opam", "exec", "--switch=" + switch, "--set-switch", "--"]

    def run(name, command, cwd=out, rejection=None):
        if rebuilt:
            command, cwd = expected_commands[name]
            selected_env = env if name in ('sail-generate', 'rust-generate') else rocq_env
            return stage(out, report, selected_env, name, command, cwd, rejection,
                         timeout=3600 if name == 'sail-generate' else 600)
        return stage(out, report, env, name, command, cwd, rejection)

    if rebuilt:
        run('sail-generate', ['bash', 'scripts/generate_proof_model.sh', 'rocq'], ROOT)
        report['sail_generation'] = rebuilt_context.generation_evidence(ROOT, out, report)
        proof.require_equal(proof.generated_evidence(policy), generated, 'Lean inputs changed during Rocq generation')
        before = inputs(ROOT, rebuilt=True)
        report.update(input_sha256=before,
                      input_regeneration='policy-bound production LLBC; fresh Sail Rocq generation and Rust retranslation in this run')
    packages = run("packages", ["opam", "list", "--switch=" + switch,
                                "--installed", "--short", "--columns=name,version"])
    report["packages"] = check_packages(packages)
    if rebuilt:
        require(report['packages'] == installation['packages'], 'full Rocq package inventory differs')
    version = run("version", opam + ["rocq", "--version"])
    require(version.strip() == "The Rocq Prover, version 9.1.1\ncompiled with OCaml 5.2.1",
            "unexpected Rocq/OCaml version")
    report["rocq_version"] = version.strip()
    rust, sail = out / "rust", out / "sail"
    rust.mkdir()
    sail.mkdir()
    run("rust-generate", [binaries["aeneas"], "-backend", "rocq", "-dest", rust,
                          ROOT / "target/CkbVmProduction.llbc"])
    if rebuilt:
        report['rust_primitives'] = rebuilt_context.install_primitives(home / 'backends/coq/Primitives.v', rust / 'Primitives.v')
    for name in ["Primitives.v", "CkbVmProduction.v"]:
        require((rust / name).is_file(), "Aeneas did not emit " + name)
    shutil.copyfile(ROOT / "proof/rocq/spike/result_shadowing.v", rust / "result_shadowing.v")
    for name, source_path in {
            "rv64d.v": ROOT / "proof/rocq/generated/sail/rv64d.v",
            "rv64d_types.v": ROOT / "proof/rocq/generated/sail/rv64d_types.v",
            "riscv_extras.v": ROOT / "deps/sail-riscv/handwritten_support/riscv_extras.v",
            "missing_e_div.v": ROOT / "proof/rocq/spike/missing_e_div.v"}.items():
        shutil.copyfile(source_path, sail / name)
    model_hashes = {str(p.relative_to(out)): sha(p) for folder in [rust, sail] for p in folder.glob("*.v")}

    def compile(name, folder, filename, rejection=None):
        return run(name, opam + ["rocq", "compile", "-Q", ".", "", filename], folder, rejection)

    compile("rust-primitives", rust, "Primitives.v")
    compile("rust-model", rust, "CkbVmProduction.v", "rust")
    repro = compile("rust-repro", rust, "result_shadowing.v")
    require("Expands to: Inductive Corelib.Init.Datatypes.result" in repro,
            "minimal Rust reproduction did not identify the shadowing declaration")
    compile("sail-support", sail, "riscv_extras.v")
    compile("sail-types", sail, "rv64d_types.v")
    compile("sail-model", sail, "rv64d.v", "sail")
    compile("sail-repro", sail, "missing_e_div.v", "sail")
    proof.require_equal(inputs(ROOT, rebuilt=rebuilt), before, "spike inputs changed during run")
    proof.require_equal(proof.source_evidence(policy, binaries, home), source, "source changed during spike")
    proof.require_equal(proof.generated_evidence(policy), generated, "generated inputs changed during spike")
    for relative, digest in model_hashes.items():
        proof.require_equal(sha(out / relative), digest, "Rocq source changed during checking")
    if rebuilt:
        rebuilt_context.check_commands(report, expected_commands)
        require(rebuilt_context.generation_evidence(ROOT, out, report) == report['sail_generation'], 'fresh Sail Rocq input drift')
        require(inputs(ROOT, include_sail=False, rebuilt=True) == report['pre_generation_input_sha256'], 'pre-generation source drift')
        require(rebuilt_context.resolve(ROOT, env, home)[2] == context_record, 'Rocq tool context drift')
    report.update(model_sha256=model_hashes, status="passed", verdict="NO-GO",
                  extra_proof_coverage=False, input_sha256_after=inputs(ROOT, rebuilt=rebuilt))


def main():
    require(len(sys.argv) == 1, "usage: rocq_spike.py (configuration via ROCQ_SPIKE_SWITCH/WORK)")
    out = new_directory(ROOT, os.environ.get("ROCQ_SPIKE_WORK"))
    report = {"schema_version": 1, "status": "running", "verdict": None,
              "extra_proof_coverage": False, "directory": str(out), "stages": [],
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "input_regeneration": "Rust retranslation only; release must first regenerate Rust LLBC and Sail sources",
              "clean_room_claimed": False}
    save(out, report)
    try:
        execute(out, report)
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="failed", error=str(error) or type(error).__name__)
        print("ERROR: " + report["error"], file=sys.stderr)
    finally:
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save(out, report)
        print("Report: " + str(out / "report.json"), flush=True)
    if report["status"] != "passed":
        return 1
    print("Both specific Rocq blockers and minimal reproductions confirmed: NO-GO (not proof coverage).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
