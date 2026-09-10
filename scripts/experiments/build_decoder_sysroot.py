#!/usr/bin/env python3
"""Build a separate full-MIR std sysroot; never install or modify global std."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "proof/lean/decoder/toolchain/full-mir"
NIGHTLY = "nightly-2026-08-18"
COMMIT = "8fa1c96cfd489e4c27654c144ae871ce2c4db6c6"
FLAGS = "-Zalways-encode-mir=yes -Zmir-opt-level=0 -Zinline-mir=no"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    out = Path(tempfile.mkdtemp(prefix="decoder-sysroot-build-", dir=ROOT / "artifacts/boundary-check"))
    report = {"status": "running", "directory": str(out), "nightly": NIGHTLY,
              "rustflags": FLAGS, "installed_sysroot_modified": False}
    report_path = out / "report.json"
    lock = None
    try:
        rustc = subprocess.check_output(["rustup", "which", "--toolchain", NIGHTLY, "rustc"], text=True).strip()
        info = subprocess.check_output([rustc, "-vV"], text=True)
        # Full compiler identity is recorded, and the pinned release commit is checked.
        if "commit-hash: " + COMMIT not in info:
            raise RuntimeError("unexpected pinned Rust compiler identity: " + info)
        report.update(rustc=info, rustc_sha256=sha(Path(rustc)))
        installed = Path(subprocess.check_output([rustc, "--print", "sysroot"], text=True).strip())
        lock = installed / "lib/rustlib/src/rust/library/Cargo.lock"
        report["stdlib_lock_before"] = sha(lock)
        if report["stdlib_lock_before"] != "34656569ab979fdf259efffc99d2b68e253e73e0e6fba6762dc51e83df71aa76":
            raise RuntimeError("pinned standard library lockfile differs")
        for name in ["Cargo.toml", "Cargo.lock", "lib.rs"]:
            shutil.copyfile(ASSETS / name, out / name)
        report["assets"] = {name: sha(out / name) for name in ["Cargo.toml", "Cargo.lock", "lib.rs"]}
        command = ["cargo", "+" + NIGHTLY, "build", "-Zbuild-std=std,panic_abort",
                   "--target", "x86_64-unknown-linux-gnu", "--locked", "-j4"]
        if args.offline:
            command.append("--offline")
        report["command"] = command
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        with (out / "build.log").open("w") as log:
            result = subprocess.run(command, cwd=out, env=dict(os.environ, RUSTFLAGS=FLAGS),
                                    stdout=log, stderr=subprocess.STDOUT, timeout=600)
        report["exit_code"] = result.returncode
        if result.returncode:
            raise RuntimeError("sysroot build failed; see build.log")
        # Nightly Cargo's std artifacts reside in build/<crate>/<hash>/out, not deps/.
        build = out / "target/x86_64-unknown-linux-gnu/debug/build"
        files = sorted([*build.glob("*/*/out/*.rlib"), *build.glob("*/*/out/*.rmeta")])
        if not any(p.name.startswith("libstd-") and p.suffix == ".rlib" for p in files):
            raise RuntimeError("standard library artifacts missing from expected Cargo layout")
        lib = out / "sysroot/lib/rustlib/x86_64-unknown-linux-gnu/lib"
        lib.mkdir(parents=True)
        report["libraries"] = {}
        for p in files:
            if (lib / p.name).exists():
                raise RuntimeError("ambiguous sysroot artifact name: " + p.name)
            (lib / p.name).symlink_to(p)
            report["libraries"][p.name] = sha(p)
        report["sysroot"] = str(out / "sysroot")
        report["status"] = "PASS"
    except Exception as error:
        report.update(status="FAIL", error=str(error))
        raise
    finally:
        if lock is not None and lock.is_file():
            report["stdlib_lock_after"] = sha(lock)
            if report.get("stdlib_lock_before") != report["stdlib_lock_after"]:
                report.update(status="FAIL", error="installed standard-library lockfile changed")
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print("Report: " + str(report_path), flush=True)
        if report["status"] == "PASS":
            print("Sysroot: " + report["sysroot"], flush=True)
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
