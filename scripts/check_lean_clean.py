#!/usr/bin/env python3
"""Week 5 clean kernel build: fresh source-only project AND Lean dependencies.

Reuse the pinned Lean compiler/standard library, not project/support .oleans.
No cache download, lake update, or deletion of existing user build directories.
This is not Week 6 toolchain installation / third-party clean-room release.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import check_proof as gate


def source_copy(source, destination):
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
        ".lake", ".git", "target", "__pycache__", "*.olean", "*.ilean", "*.o", "*.so", "*.a"))


def check_paths(value, clean, compiler):
    paths = [Path(p).resolve() for p in value.split(os.pathsep) if p]
    if not paths:
        raise RuntimeError("empty clean-build LEAN_PATH")
    for path in paths:
        if not path.is_relative_to(clean) and not path.is_relative_to(compiler / "lib/lean"):
            raise RuntimeError("external compiled dependency in clean LEAN_PATH: " + str(path))
    return [str(p) for p in paths]


def prepare(clean, aeneas):
    project = clean / "proof/lean/theorems"
    for relative in ("proof/lean/theorems", "proof/lean/generated/rust",
                     "proof/lean/generated/sail", "proof/lean/audit", "proof/lean/compat"):
        source_copy(gate.ROOT / relative, clean / relative)
    support = clean / "support/Aeneas"
    source_copy(aeneas / "backends/lean", support)
    gate.require_equal(gate.tree_files(support, gate.lean_sources),
                       gate.tree_files(aeneas / "backends/lean", gate.lean_sources), "clean Aeneas source copy")
    (project / ".lake").mkdir()
    (project / ".lake/aeneas").symlink_to(support, target_is_directory=True)
    config = clean / "proof/lean/generated/rust/lakefile.toml"
    old = 'path = "' + str(aeneas / "backends/lean") + '"'
    text = config.read_text()
    if text.count(old) != 1:
        raise RuntimeError("unexpected generated Rust Aeneas path")
    config.write_text(text.replace(old, 'path = "' + str(support) + '"'))
    manifest = json.loads((project / "lake-manifest.json").read_text())
    dependencies = {}
    for package in manifest["packages"]:
        if package["type"] != "git":
            continue
        origin = gate.THEOREMS / manifest["packagesDir"] / package["name"]
        destination = project / manifest["packagesDir"] / package["name"]
        revision = gate.output(["git", "-C", str(origin), "rev-parse", "HEAD"])
        gate.require_equal(revision, package["rev"], "clean dependency " + package["name"])
        gate.require_equal(gate.output(["git", "-C", str(origin), "status", "--porcelain"]), "",
                           "clean dependency source " + package["name"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(origin), str(destination)], check=True)
        subprocess.run(["git", "-C", str(destination), "checkout", "--quiet", "--detach", revision], check=True)
        dependencies[package["name"]] = revision
    # No cached module can exist anywhere in the new project before Lake starts.
    if list(clean.rglob("*.olean")) or list(clean.rglob("*.ilean")):
        raise RuntimeError("compiled Lean input found in clean source tree")
    return project, dependencies


def run():
    policy = json.loads(gate.POLICY.read_text())
    env, binaries, aeneas, lake = gate.tools_and_environment(policy)
    before = gate.source_evidence(policy, binaries, aeneas)
    generated = gate.generated_evidence(policy)
    gate.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    clean = Path(tempfile.mkdtemp(prefix="clean-lean-", dir=gate.ARTIFACTS)).resolve()
    report_path = clean / "report.json"
    report = {"status": "running", "directory": str(clean), "policy_sha256": gate.file_hash(gate.POLICY),
              "reused": "pinned Lean compiler and its standard library only", "initial_compiled_modules": 0}
    gate.write_json(report_path, report)
    print("Clean source-only build: " + str(clean), flush=True)
    try:
        project, dependencies = prepare(clean, aeneas)
        compiler = Path(subprocess.check_output([lake, "env", "lean", "--print-prefix"],
                                                cwd=project, env=env, text=True).strip()).resolve()
        value = subprocess.check_output([lake, "env", "printenv", "LEAN_PATH"], cwd=project, env=env, text=True).strip()
        report["lean_path"] = check_paths(value, clean, compiler)
        report["dependency_revisions"] = dependencies
        report["source_models"] = generated
        gate.write_json(report_path, report)
        log_path = clean / "build.log"
        # Bound runtime threads; prohibit Lake's package build-cache downloads.
        env["LEAN_NUM_THREADS"] = "8"
        with log_path.open("w") as stream:
            result = subprocess.run([lake, "--no-cache", "build", "LeanRV64D", "CkbVmProduction", "SmokeImports",
                                     "AddRegisterAxioms", "RegisterRegression", "AddStepAxioms",
                                     "StepRegression", "ProductionAdd", "ProductionAddWitness"], cwd=project, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=int(env.get("PROOF_BUILD_TIMEOUT", "3600")))
        log = log_path.read_text(errors="replace")
        if result.returncode or gate.INTERNAL_FAILURE.search(log):
            raise RuntimeError("clean kernel build failed; see " + str(log_path))
        audit_log = subprocess.check_output([lake, "env", "lean", "../audit/ExportStepAudit.lean"],
                                           cwd=project, env=env, text=True, stderr=subprocess.STDOUT, timeout=180)
        if gate.INTERNAL_FAILURE.search(audit_log):
            raise RuntimeError("internal failure in clean audit")
        evidence = gate.parse_audit(audit_log)
        gate.check_audit(evidence, policy)
        gate.write_json(clean / "lean-audit.json", evidence)
        for relative in ("proof/lean/theorems", "proof/lean/generated/rust", "proof/lean/generated/sail"):
            gate.require_equal(gate.tree_files(clean / relative, gate.lean_sources),
                               gate.tree_files(gate.ROOT / relative, gate.lean_sources), "clean proof/model source copy")
        gate.require_equal(gate.file_hash(project / "lake-manifest.json"),
                           gate.file_hash(gate.THEOREMS / "lake-manifest.json"), "clean dependency lock")
        gate.require_equal(gate.source_evidence(policy, binaries, aeneas), before, "source changed during clean build")
        gate.require_equal(gate.generated_evidence(policy), generated, "model changed during clean build")
        gate.require_equal(gate.file_hash(gate.POLICY), report["policy_sha256"], "policy changed during clean build")
        report.update({"status": "passed", "build_log_sha256": gate.file_hash(log_path),
                       "built_olean_count": len(list(clean.rglob("*.olean"))),
                       "theorem": evidence["theorem"], "axiom_count": len(evidence["axioms"]),
                       "witness_axiom_counts": {name: len(items) for name, items in evidence["witness_axioms"].items()},
                       "audit_sha256": gate.file_hash(clean / "lean-audit.json")})
    except BaseException as error:
        report.update({"status": "failed", "error": str(error)})
        raise
    finally:
        gate.write_json(report_path, report)
    print("CLEAN_BUILD_JSON=" + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
