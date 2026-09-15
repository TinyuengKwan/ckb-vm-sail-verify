#!/usr/bin/env python3
"""Strict conditional ADD acceptance. No expected-blocked or skip mode.

The checked-in policy is a review baseline, never refreshed by this command.
Local source/binary hashes are evidence of identity, not translator correctness
or an authenticated upstream supply-chain attestation.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

import ckb_source_baseline


ROOT = Path(__file__).resolve().parent.parent
THEOREMS = ROOT / "proof/lean/theorems"
POLICY = ROOT / "proof/lean/audit/step-policy.json"
ARTIFACTS = ROOT / "artifacts/proof-check"
MARKER = "PROOF_AUDIT_JSON="
INTERNAL_FAILURE = re.compile(r"PANIC|uncaught exception|Stack overflow")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    return digest(path.read_bytes())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def tree_files(directory, predicate=lambda p: True):
    """Hash source contents and relative names; exclude build/VCS caches."""
    result = {}
    for base, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if d not in (".lake", ".git", "target", "__pycache__"))
        for name in sorted(files):
            path = Path(base) / name
            if predicate(path):
                result[path.relative_to(directory).as_posix()] = file_hash(path)
    if not result:
        raise RuntimeError(f"empty or missing source tree: {directory}")
    return result


def lean_sources(path):
    return path.suffix == ".lean" or path.name == "lean-toolchain"


def output(args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True, timeout=60).strip()


def require_equal(actual, expected, label):
    if actual != expected:
        if isinstance(actual, dict) and isinstance(expected, dict):
            changed = sorted(k for k in actual.keys() | expected.keys()
                             if actual.get(k) != expected.get(k))
            detail = ": " + ", ".join(changed[:12])
        else:
            detail = ""
        raise RuntimeError(f"{label} differs from reviewed policy{detail}; review required")


def local_sources():
    files = {}
    for directory, predicate in [
        (ROOT / "crates", lambda p: p.suffix in (".rs", ".toml")),
        (THEOREMS, lean_sources),
        (ROOT / "proof/lean/compat", lambda p: p.suffix in (".lean", ".patch")),
    ]:
        for name, value in tree_files(directory, predicate).items():
            files[(directory / name).relative_to(ROOT).as_posix()] = value
    for name in ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml",
                 "sail-model/ckb_vm_config.json", "proof/lean/theorems/lakefile.toml",
                 "proof/lean/theorems/lake-manifest.json",
                 "proof/lean/expected_build_status.txt",
                 "proof/lean/audit/ExportStepAudit.lean",
                 "scripts/generate_rust_model.sh", "scripts/generate_proof_model.sh",
                 "scripts/sail_model_transaction.py", "scripts/tests/test_sail_model_transaction.py",
                 "scripts/configure_lean_project.sh", "scripts/prepare_sail_config.sh",
                 "scripts/check_proof.py", "scripts/check_lean_imports.sh",
                 "scripts/tests/test_proof_check.py", "scripts/tests/test_lean_imports.py",
                 "scripts/tests/test_lean_step.py", "scripts/verify_environment.sh",
                 "scripts/ckb_source_baseline.py", "scripts/tests/test_ckb_source_baseline.py",
                 "scripts/check_lean_clean.py", "scripts/tests/test_lean_clean.py",
                 "scripts/public_decoder_gate.py", "scripts/public_decoder_acceptance.py",
                 "proof/lean/decoder/public-policy.json",
                 "proof/lean/decoder/public-rebuilt-policy.json",
                 "scripts/probes/probe_add_decoder.py",
                 "proof/lean/extraction/ckb-source-baseline.json",
                 "proof/lean/extraction/ckb-vm.json", "patches/ckb-vm/runtime-container.patch",
                 "scripts/build_sail_emulator.sh", "Makefile"]:
        files[name] = file_hash(ROOT / name)
    import rebuilt_main_tools
    for name in rebuilt_main_tools.SOURCES:
        files[name] = file_hash(ROOT / name)
    return files


def tools_and_environment(policy):
    if "main_toolchain" in policy:
        import rebuilt_main_tools
        return rebuilt_main_tools.resolve(ROOT, policy)
    env = os.environ.copy()
    aeneas_home = Path(env.get("AENEAS_HOME", str(Path.home() / ".local/share/aeneas"))).resolve()
    cache = ROOT / "deps/sail-riscv/build/CMakeCache.txt"
    if not cache.is_file():
        raise RuntimeError("Sail CMake project missing; run make sail-config first")
    settings = dict(line.split("=", 1) for line in cache.read_text().splitlines()
                    if "=" in line and not line.startswith(("#", "//")))
    sail = Path(settings["SAIL_BIN:FILEPATH"]).resolve()
    require_equal(Path(settings["CMAKE_HOME_DIRECTORY:INTERNAL"]).resolve(),
                  (ROOT / "deps/sail-riscv").resolve(), "CMake source directory")
    # Use exactly the compiler CMake invokes, not a same-number release on PATH.
    lake = shutil.which("lake") or str(Path.home() / ".elan/bin/lake")
    env["PATH"] = str(sail.parent) + os.pathsep + str(Path(lake).parent) + os.pathsep + env["PATH"]
    env.update({"AENEAS_HOME": str(aeneas_home),
                "CHARON": str(aeneas_home / "charon"), "AENEAS": str(aeneas_home / "aeneas"),
                "SAIL_RISCV_DIR": str(ROOT / "deps/sail-riscv"),
                "SAIL_BIN": str(ROOT / "deps/sail-riscv/build/c_emulator/sail_riscv_sim"),
                "SAIL_CONFIG_OVERRIDE": str(ROOT / "sail-model/ckb_vm_config.json"),
                "SAIL_CONFIG": str(ROOT / "sail-model/build/ckb_vm_config.json"),
                "ELAN_TOOLCHAIN": policy["lean_toolchain"], "LEAN_ABORT_ON_PANIC": "1"})
    # Do not let an ambient import path substitute definitions for Lake's inputs.
    env.pop("LEAN_PATH", None)
    binaries = {"sail": sail, "aeneas": aeneas_home / "aeneas",
                "charon": aeneas_home / "charon", "charon-driver": aeneas_home / "charon-driver"}
    return env, binaries, aeneas_home, lake


def source_evidence(policy, binaries, aeneas_home):
    # Adoption of a source patch does not approve a theorem/policy migration.
    source_baseline = ckb_source_baseline.check(ROOT)
    require_equal(source_baseline["manifest_sha256"], policy.get("ckb_source_baseline_sha256"),
                  "CKB upstream-plus-patch baseline (theorem/policy migration pending)")
    repos = {}
    for name, revision in policy["repositories"].items():
        path = ROOT / name
        head = output(["git", "-C", str(path), "rev-parse", "HEAD"])
        require_equal(head, revision, name + " revision")
        if name != "deps/ckb-vm" and output(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"]):
            raise RuntimeError(f"{name} source checkout is dirty")
        repos[name] = head
    sources = local_sources()
    require_equal(sources, policy["local_sources"], "proof/extraction source files")
    binary_hashes = {name: file_hash(path) for name, path in binaries.items()}
    require_equal(binary_hashes, policy["tool_binaries"], "translator binaries")
    support = tree_files(aeneas_home / "backends/lean", lean_sources)
    require_equal(digest(canonical(support)), policy["aeneas_lean_sources_sha256"], "Aeneas source contents")
    versions = {name: output([str(binaries[name]), option]) for name, option in
                [("sail", "--version"), ("charon", "version"), ("aeneas", "-version")]}
    require_equal(versions, policy["translator_versions"], "translator versions")
    return {"repositories": repos, "ckb_source_baseline": source_baseline,
            "local_sources": sources, "tool_binaries": binary_hashes,
            "translator_versions": versions, "aeneas_lean_sources": support}


def generated_evidence(policy):
    models = {}
    for side in ("rust", "sail"):
        models[side] = tree_files(ROOT / "proof/lean/generated" / side, lean_sources)
        require_equal(digest(canonical(models[side])), policy["generated_sha256"][side],
                      side + " generated Lean source tree")
    config = file_hash(ROOT / "sail-model/build/ckb_vm_config.json")
    require_equal(config, policy["sail_config_sha256"], "materialized Sail config")
    require_equal(file_hash(ROOT / "proof/lean/generated/sail/ckb_vm_config.json"), config,
                  "generated Sail config")
    provenance = json.loads((ROOT / "proof/lean/generated/rust/SOURCE_BASELINE.json").read_text())
    if "main_toolchain" in policy:
        import generate_rebuilt_rust
        generate_rebuilt_rust.check_provenance(ROOT, policy, provenance)
    for name, value in ckb_source_baseline.check(ROOT).items():
        require_equal(provenance.get(name), value, "generated Rust provenance " + name)
    require_equal(provenance["generated_lean_sha256"],
                  file_hash(ROOT / "proof/lean/generated/rust/CkbVmProduction.lean"), "generated Rust provenance model")
    require_equal(provenance["llbc_sha256"], file_hash(ROOT / "target/CkbVmProduction.llbc"),
                  "generated Rust provenance LLBC")
    return {"models": models, "sail_config_sha256": config,
            "rust_provenance": provenance,
            "llbc_sha256": file_hash(ROOT / "target/CkbVmProduction.llbc")}


def parse_audit(log):
    rows = [line[len(MARKER):] for line in log.splitlines() if line.startswith(MARKER)]
    if len(rows) != 1:
        raise RuntimeError("expected exactly one Lean environment audit record")
    return json.loads(rows[0])


def boundary_hashes(audit):
    return {name: digest(canonical(value)) for name, value in audit["boundary"].items()}


def check_audit(audit, policy):
    require_equal(audit["theorem"], policy["theorem"], "theorem name")
    names = audit["axioms"]
    if "sorryAx" in names or len(set(names)) != len(names):
        raise RuntimeError("sorryAx or duplicate axiom in final theorem")
    expected = sorted(name for group in policy["axioms"].values() for name in group)
    require_equal(sorted(names), expected, "final theorem axiom set")
    require_equal(boundary_hashes(audit), policy["boundary_sha256"],
                  "elaborated theorem signature / contract constructors / state relation")
    contracts = audit["contract_axioms"]
    require_equal({name: sorted(deps) for name, deps in contracts.items()}, policy["contract_axioms"],
                  "production wrapper contract axiom sets")
    if any("sorryAx" in deps or len(set(deps)) != len(deps) for deps in contracts.values()):
        raise RuntimeError("sorryAx or duplicate axiom in production wrapper contracts")
    witnesses = audit["witness_axioms"]
    if any("sorryAx" in deps or len(set(deps)) != len(deps) for deps in witnesses.values()):
        raise RuntimeError("sorryAx or duplicate axiom in non-vacuity witnesses")
    require_equal({name: sorted(deps) for name, deps in witnesses.items()}, policy["witness_axioms"],
                  "non-vacuity witness axiom sets")


def write_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


def run_stage(name, args, env, report, *, cwd=ROOT):
    log = ARTIFACTS / (name + ".log")
    print(f"==> proof-check: {name} (log: {log})", flush=True)
    record = {"name": name, "status": "running", "log": log.name}
    report["stages"].append(record)
    write_json(ARTIFACTS / "report.json", report)
    timeout = int(env.get("PROOF_BUILD_TIMEOUT", "3600"))
    if timeout <= 0:
        raise RuntimeError("PROOF_BUILD_TIMEOUT must be positive")
    with log.open("w") as stream:
        process = subprocess.Popen(args, cwd=cwd, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            record["status"] = "failed"
            raise
    contents = log.read_text(errors="replace")
    record.update({"exit_code": code, "sha256": file_hash(log), "status": "passed"})
    if code or INTERNAL_FAILURE.search(contents):
        record["status"] = "failed"
        raise RuntimeError(f"{name} failed (exit {code}) or emitted an internal failure; see {log}")
    return contents


def execute(policy, report):
    report["ckb_source_baseline"] = ckb_source_baseline.check(ROOT)
    env, binaries, aeneas_home, lake = tools_and_environment(policy)
    before = source_evidence(policy, binaries, aeneas_home)
    report["source"] = before
    report["project_head"] = output(["git", "rev-parse", "HEAD"])
    report["project_worktree_status"] = output(["git", "status", "--porcelain"])
    # No check_proof_model.sh: its expected-blocked success is not acceptance.
    run_stage("sail-config", ["make", "sail-config"], env, report)
    run_stage("environment", ["bash", "scripts/verify_environment.sh"], env, report)
    generator = ([sys.executable, "scripts/generate_rebuilt_rust.py"] if "main_toolchain" in policy
                 else ["bash", "scripts/generate_rust_model.sh"])
    run_stage("generate-rust", generator, env, report)
    run_stage("generate-sail", ["bash", "scripts/generate_proof_model.sh", "lean"], env, report)
    generated = generated_evidence(policy)
    report["generated"] = generated
    run_stage("kernel-step", ["bash", "scripts/check_lean_imports.sh", "--step"], env, report)
    evidence = parse_audit(run_stage("theorem-audit",
        [lake, "env", "lean", "../audit/ExportStepAudit.lean"], env, report, cwd=THEOREMS))
    write_json(ARTIFACTS / "lean-audit.json", evidence)
    check_audit(evidence, policy)
    report["axiom_counts"] = {name: len(items) for name, items in policy["axioms"].items()}
    report["witness_axiom_counts"] = {name: len(items) for name, items in evidence["witness_axioms"].items()}
    report["boundary_sha256"] = boundary_hashes(evidence)
    for name in ("test_lean_imports", "test_lean_step", "test_proof_check", "test_ckb_source_baseline", "test_lean_clean",
                 "test_decoder_public_source", "test_decoder_public_clean",
                 "test_public_decoder_acceptance", "test_public_decoder_gate",
                 "test_decoder_harness", "test_decoder_model_identity", "test_decoder_iterator_identity",
                 "test_decoder_input_bundle", "test_decoder_input_locations", "test_sail_model_transaction",
                 "test_decoder_rebuilt_inputs", "test_decoder_rebuilt_locations", "test_rebuilt_main_tools",
                 "test_generate_rebuilt_rust", "test_rebuilt_production_rust", "test_source_snapshot"):
        run_stage(name, [sys.executable, "scripts/tests/" + name + ".py"], env, report)
    # The public decoder producer rebuilds the same main source/support graph
    # and independently audits it before checking the additional decoder layer.
    # Keep the original clean acceptance requirements; do not run a second,
    # redundant main-only clean build or fall back if the public stage fails.
    import public_decoder_gate
    public = public_decoder_gate.execute(run_stage, env, report)
    clean = public["clean_build"]
    require_equal(clean["status"], "passed", "clean kernel status")
    require_equal(clean["initial_compiled_modules"], 0, "clean initial compiled modules")
    require_equal(clean["theorem"], policy["theorem"], "clean theorem")
    require_equal(clean["policy_sha256"], report["policy_sha256"], "clean policy")
    report["clean_build"] = clean
    require_equal(source_evidence(policy, binaries, aeneas_home), before, "sources changed during check")
    require_equal(generated_evidence(policy), generated, "generated inputs changed during check")
    require_equal(file_hash(POLICY), report["policy_sha256"], "policy changed during check")
    report["status"] = "passed"


def main(args):
    # Reject unsupported backend before generation, even when another backend's
    # expected build status happens to be blocked.
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    # Avoid two runs publishing a mixture of evidence in this fixed directory.
    import fcntl
    with (ARTIFACTS / ".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("ERROR: another proof-check is running", file=sys.stderr)
            return 1
        report = {"schema_version": 1, "status": "running", "assurance": "conditional",
                  "coverage": "runtime-only", "release_audit": False,
                  "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stages": []}
        write_json(ARTIFACTS / "report.json", report)
        try:
            if args != ["lean"]:
                raise RuntimeError("usage: check_proof.py lean; only BACKEND=lean is supported")
            policy = json.loads(POLICY.read_text())
            report.update({"policy_sha256": file_hash(POLICY), "theorem": policy["theorem"],
                           "outstanding_contracts": policy["outstanding_contracts"],
                           "configuration": policy["configuration"]})
            execute(policy, report)
        except (Exception, KeyboardInterrupt) as error:
            report.update({"status": "failed", "error": str(error) or type(error).__name__})
            print("ERROR: " + report["error"], file=sys.stderr)
        finally:
            report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_json(ARTIFACTS / "report.json", report)
        if report["status"] != "passed":
            return 1
        print("OK: public ADD decode and production execution proof-check passed from clean dependencies; state/fetch/Sail readiness contracts remain explicit.")
        print("Report: artifacts/proof-check/report.json (not audit-release or proved coverage)")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
