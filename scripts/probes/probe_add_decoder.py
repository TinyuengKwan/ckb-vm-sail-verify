#!/usr/bin/env python3
"""Read-only production-source extraction probe for the unresolved ADD decoder.

Outputs stay in a fresh evidence directory. A translation failure is NOT proof
coverage and returns a nonzero exit code. This does not refresh the source or
proof acceptance policy and never edits a generated production model.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline_command = ["python3", str(ROOT / "scripts/ckb_source_baseline.py")]
    baseline = json.loads(subprocess.check_output(baseline_command, text=True))
    config = json.loads((ROOT / "proof/lean/extraction/ckb-vm.json").read_text())
    aeneas_dir = Path(os.environ.get("AENEAS_HOME", str(Path.home() / ".local/share/aeneas")))
    charon, aeneas = aeneas_dir / "charon", aeneas_dir / "aeneas"
    versions = {
        "charon": subprocess.check_output([str(charon), "version"], text=True).strip(),
        "aeneas": subprocess.check_output([str(aeneas), "-version"], text=True).strip(),
    }
    if any(versions[key] != config[key] for key in versions):
        raise RuntimeError("probe tool versions differ from the adopted extraction configuration")
    parent = ROOT / "artifacts/boundary-check"
    parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="decoder-", dir=parent))
    llbc = evidence / "AddDecodeProbe.llbc"
    output = evidence / "generated"
    output.mkdir()
    report = {
        "status": "running", "source_baseline": baseline, "tools": versions,
        "tool_binaries": {"charon": digest(charon), "aeneas": digest(aeneas)},
        "scope": "real instructions/i.rs::factory; not DefaultDecoder fetch/cache/MOP",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "directory": str(evidence), "stages": [],
        "proof_coverage": False,
    }
    report_path = evidence / "report.json"

    def save():
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    save()
    print("Decoder probe: " + str(evidence), flush=True)
    commands = [
        ("charon", [str(charon), "cargo", "--preset=aeneas", "--start-from",
                    "ckb_vm::instructions::i::factory", "--include", "ckb_vm::instructions::_",
                    "--dest-file", str(llbc), "--", "--lib"]),
        ("aeneas", [str(aeneas), "-backend", "lean", "-abort-on-error", "-no-progress-bar",
                    "-dest", str(output), str(llbc)]),
    ]
    exit_code = 1
    try:
        for label, command in commands:
            log = evidence / (label + ".log")
            with log.open("w") as stream:
                result = subprocess.run(command, cwd=ROOT / "crates/proof-extract",
                                        stdout=stream, stderr=subprocess.STDOUT, timeout=600)
            record = {"stage": label, "command": command, "exit_code": result.returncode,
                      "log_sha256": digest(log)}
            record["internal_failure"] = bool(re.search(
                r"PANIC|uncaught exception|Stack overflow|Internal error, please file an issue",
                log.read_text(errors="replace"), re.IGNORECASE))
            report["stages"].append(record)
            save()
            if result.returncode or record["internal_failure"]:
                report["status"] = "extraction-failed"
                break
            if label == "charon" and json.loads(llbc.read_text())["has_errors"]:
                report["status"] = "extraction-failed"
                break
        else:
            if not list(output.rglob("*.lean")):
                raise RuntimeError("translator exited successfully without any Lean output")
            report["status"] = "translated-not-kernel-checked"
            exit_code = 0
        if llbc.exists():
            report["llbc_sha256"] = digest(llbc)
            report["charon_has_errors"] = json.loads(llbc.read_text())["has_errors"]
            if report["charon_has_errors"]:
                report["status"] = "extraction-failed"
                exit_code = 1
        after = json.loads(subprocess.check_output(baseline_command, text=True))
        if after != baseline:
            raise RuntimeError("production source identity changed during decoder probe")
    except BaseException as error:
        report["status"] = "probe-error"
        report["error"] = str(error)
        raise
    finally:
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save()
    print(json.dumps({"status": report["status"], "report": str(report_path)}), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
