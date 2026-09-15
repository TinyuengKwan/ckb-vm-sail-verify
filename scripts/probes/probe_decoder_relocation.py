#!/usr/bin/env python3
"""Measure public extraction after relocating the production checkout/harness.

This is a bounded relocation probe, not a clean-room or main-gate PASS. It uses
the reviewed existing translator binaries and full-MIR sysroot, never their
previous Cargo build outputs. No policy is updated by this command.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import check_proof as proof
import ckb_source_baseline as baseline
import decoder_harness as harness
import decoder_model_identity as model_identity
import decoder_input_locations as locations
from decoder_public_source import check_reextraction
import public_decoder_gate as gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-inputs", type=Path,
                        help="use independently installed tools/sysroot/evidence instead of old experimental directories")
    args = parser.parse_args()
    parent = ROOT / "artifacts/boundary-check"
    out = Path(tempfile.mkdtemp(prefix="decoder-relocation-", dir=parent)).resolve()
    report = {"status": "running", "directory": str(out), "stages": [],
              "main_gate_adopted": False, "clean_room_claimed": False,
              "scope": "relocated public and iterator Rust extraction; generated model identity checked without editing outputs",
              "script_sha256": proof.file_hash(Path(__file__)),
              "model_identity_script_sha256": proof.file_hash(ROOT / "scripts/decoder_model_identity.py"),
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def save():
        proof.write_json(out / "report.json", report)

    def run(name, command, cwd=ROOT, env=None, timeout=600):
        row = {"name": name, "command": list(map(str, command)), "cwd": str(cwd), "status": "running"}
        report["stages"].append(row)
        save()
        print("==> relocation: " + name, flush=True)
        log = out / (name + ".log")
        try:
            with log.open("w") as stream:
                proc = subprocess.run(row["command"], cwd=cwd, env=env, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=timeout)
            row["exit_code"] = proc.returncode
            if proc.returncode:
                raise RuntimeError(name + " failed; see " + str(log))
            row["status"] = "passed"
            return log.read_text()
        except BaseException:
            row["status"] = "failed"
            raise
        finally:
            row["log_sha256"] = proof.file_hash(log)
            save()

    save()
    try:
        sys.setrecursionlimit(100000)
        original = baseline.check(ROOT)
        public_policy = json.loads(gate.POLICY.read_text())
        if args.installed_inputs:
            report["installed_inputs"] = locations.load(args.installed_inputs)
            proof.require_equal(gate.sources(), public_policy["sources"], "public proof/checker sources")
        else:
            gate.check_policy(public_policy)
        report["public_policy_sha256"] = proof.file_hash(gate.POLICY)
        inputs = ROOT / public_policy["inputs"]
        config = json.loads((ROOT / "proof/lean/decoder/toolchain/full-entry/extraction.json").read_text())
        if args.installed_inputs:
            payload = Path(report["installed_inputs"]["payload"])
            charon, aeneas = payload / "bin/charon", payload / "bin/aeneas"
            sysroot = payload / "sysroot"
            prior = payload / "qualification/sysroot.json"
            archive = payload / "llbc/OuterClosedDepsV3.llbc"
            iterator_archive = payload / "llbc/FnPtrFullMir.llbc"
        else:
            charon = inputs.parent / "charon-cfg-OYcaoK/candidate-bin/charon"
            aeneas = inputs / "candidate-v2-bin/aeneas"
            sysroot = inputs.parent / "decoder-sysroot-q8nI9W/sysroot"
            prior = inputs.parent / "full-mir-check-ykre555d/report.json"
            archive = inputs / "OuterClosedDepsV3.llbc"
            iterator_archive = inputs.parent / "decoder-sysroot-q8nI9W/FnPtrFullMir.llbc"
        for binary, key in [(charon, "charon_binary_sha256"),
                            (charon.with_name("charon-driver"), "charon_driver_sha256"),
                            (aeneas, "aeneas_binary_sha256")]:
            proof.require_equal(proof.file_hash(binary), config[key], key)
        proof.require_equal(proof.file_hash(prior),
            "69ea312f2e816dd9575d508f4226dc01ba654d253a9b69afd4c7029f8728f9a8", "sysroot provenance")
        libraries = {p.name: proof.file_hash(p) for p in sorted(
            (sysroot / "lib/rustlib/x86_64-unknown-linux-gnu/lib").iterdir()) if p.is_file()}
        proof.require_equal(libraries, json.loads(prior.read_text())["sysroot_libraries"], "sysroot libraries")
        report["reused"] = {"tool_binaries": {str(p): proof.file_hash(p) for p in
                            [charon, charon.with_name("charon-driver"), aeneas]}, "sysroot_libraries": libraries}
        head = proof.output(["git", "rev-parse", "HEAD"])
        checkout = out / "checkout"
        run("clone-project", ["git", "clone", "--no-hardlinks", "--no-checkout", ROOT, checkout])
        run("checkout-project", ["git", "checkout", "--detach", head], checkout)
        run("clone-ckb", ["git", "clone", "--no-hardlinks", "--no-checkout", ROOT / "deps/ckb-vm",
                          checkout / "deps/ckb-vm"])
        run("checkout-ckb", ["git", "checkout", "--detach", original["upstream_commit"]],
            checkout / "deps/ckb-vm")
        proof.require_equal(baseline.check(checkout, apply=True), original, "relocated production baseline")
        work = out / "outer"
        report["harness_before"] = harness.prepare(work, checkout)
        env = dict(os.environ, RUSTUP_TOOLCHAIN=config["rust_toolchain"])
        for key in ["RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "CARGO_BUILD_RUSTFLAGS", "RUSTC_WRAPPER",
                    "RUSTC_WORKSPACE_WRAPPER", "RUSTC", "RUSTDOC", "CHARON_ARGS", "CHARON_LOG", "RUST_LOG"]:
            env.pop(key, None)
        target = out / "cargo-target"
        proof.require_equal(target.exists(), False, "new Cargo target")
        env["CARGO_TARGET_DIR"] = str(target)
        report["cargo_target_initially_absent"] = True
        version = run("rust-version", ["rustc", "-vV"], env=env)
        if "commit-hash: " + config["rust_commit"] not in version:
            raise RuntimeError("Rust compiler identity changed")
        llbc = out / "OuterClosedDepsV3.llbc"
        cmd = [charon, "cargo", "--preset=aeneas", "--sysroot", sysroot, "--dest-file", llbc]
        for flag, key in [("start-from", "outer_start_from"), ("include", "outer_include"), ("opaque", "outer_opaque")]:
            for value in config[key]:
                cmd.extend(["--" + flag, value])
        run("extract-relocated", cmd + ["--", *config["outer_cargo_args"]], work, env)
        proof.require_equal(proof.file_hash(archive), config["llbc_sha256"], "archived extraction identity")
        if args.installed_inputs:
            report["extraction_location_mapping"] = locations.check_extraction(
                json.loads(llbc.read_bytes()), args.installed_inputs)
        else:
            check_reextraction(json.loads(archive.read_bytes()), json.loads(llbc.read_bytes()))
        report["extraction_options_match"] = True
        generated = out / "generated"
        env.update(config["aeneas_env"])
        for key in ["AENEAS_BRANCH_DIAGNOSTIC", "AENEAS_COLLAPSE_DIAGNOSTIC"]:
            env.pop(key, None)
        run("translate-relocated", [aeneas, *config["aeneas_args"], "-dest", generated, llbc], work, env)
        model = generated / "OuterClosedDepsV3.lean"
        report["generated_model_sha256"] = proof.file_hash(model)
        report["model_identity"] = model_identity.check(model, checkout)
        # The public proof also imports the full-MIR function-pointer iterator.
        # Extract its pinned Rust source from the new checkout, not the old path.
        iterator_relative = model_identity.ITERATOR_RELATIVE
        iterator_source = checkout / iterator_relative
        proof.require_equal(proof.file_hash(iterator_source), public_policy["sources"][iterator_relative],
                            "relocated iterator source")
        proof.require_equal(proof.file_hash(iterator_archive),
            "ec90aafd39b3a6154f98b73b12d99d7e8a567e2461d1c5baec113b20ac699ee4", "archived iterator")
        archived_iterator = json.loads(iterator_archive.read_bytes())
        iterator_llbc = out / "FnPtrFullMir.llbc"
        cmd = [charon, "rustc", "--preset=aeneas", "--sysroot", sysroot, "--dest-file", iterator_llbc]
        for pattern in archived_iterator["translated"]["options"]["include"]:
            cmd.extend(["--include", pattern])
        run("extract-relocated-iterator", cmd + ["--", iterator_source, "--crate-type=lib"], out, env)
        fresh_iterator = json.loads(iterator_llbc.read_bytes())
        if args.installed_inputs:
            report["iterator_extraction_location_mapping"] = locations.check_extraction(
                fresh_iterator, args.installed_inputs, "FnPtrFullMir.llbc")
        else:
            check_reextraction(archived_iterator, fresh_iterator)
        run("translate-relocated-iterator", [aeneas, "-backend", "lean", "-abort-on-error",
            "-no-progress-bar", "-checks", "-sequential", "-dest", generated, iterator_llbc], out, env)
        iterator_model = generated / "FnPtrFullMir.lean"
        report["iterator_model_sha256"] = proof.file_hash(iterator_model)
        report["iterator_llbc_sha256"] = proof.file_hash(iterator_llbc)
        report["iterator_model_identity"] = model_identity.check_iterator(iterator_model, checkout, out)
        proof.require_equal(proof.file_hash(iterator_source), public_policy["sources"][iterator_relative],
                            "iterator source changed during extraction")
        report["harness_after"] = harness.verify(work, checkout)
        proof.require_equal(report["harness_before"], report["harness_after"], "harness changed")
        proof.require_equal(baseline.check(ROOT), original, "original production source changed")
        proof.require_equal(proof.file_hash(gate.POLICY), report["public_policy_sha256"], "public policy changed")
        proof.require_equal(proof.file_hash(Path(__file__)), report["script_sha256"], "probe changed")
        proof.require_equal(proof.file_hash(ROOT / "scripts/decoder_model_identity.py"),
                            report["model_identity_script_sha256"], "model checker changed")
        if args.installed_inputs:
            proof.require_equal(locations.load(args.installed_inputs), report["installed_inputs"], "installed inputs changed")
            proof.require_equal(gate.sources(), public_policy["sources"], "public proof/checker sources changed")
        else:
            gate.check_policy(public_policy)
        report.update(status="passed", project_commit=head, llbc_sha256=proof.file_hash(llbc),
                      exact_model_after_source_comment_mapping=True, no_policy_change=True)
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="failed", error=str(error) or type(error).__name__)
        print("ERROR: " + report["error"], file=sys.stderr)
    finally:
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save()
        print("Report: " + str(out / "report.json"), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
