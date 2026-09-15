#!/usr/bin/env python3
"""Record fresh runtime/mutation/replay and Rust tests for one formal source.

The formal report is a source/model identity anchor, not proof that this native
run is clean-room.  Both existing production executors run with the admitted
private Rust toolchain and fresh output directories.  A separate process then
validates their complete reports.  No release or delivery approval is claimed.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import check_proof as proof
import record_generation as recording
import rebuilt_main_tools as tools
import release_evidence as evidence
import release_rust_tests
import source_snapshot


ROOT = Path(__file__).resolve().parents[1]
POLICY_SHA = "b5bdc4017628cb065f273a278c7d7458bb6d93b4572eaca0e4788e519e6ab2c3"
STABLE = "1.97.1-x86_64-unknown-linux-gnu"
MARKER = "WEEK6_NATIVE_CHECK_JSON="
FLAGS = ("clean_room_claimed", "kernel_acceptance_claimed", "release_claimed", "week6_closed")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def ref(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            "native reference outside/missing")
    return {"path": path.relative_to(root).as_posix(), "sha256": evidence.sha(path)}


def new_output(path, root=ROOT):
    root, path = Path(root).resolve(), Path(path).absolute()
    parent = root / "artifacts/boundary-check"
    require(parent.is_dir() and not parent.is_symlink() and path.parent == parent and
            path.name.startswith("week6-native-") and path.name != "week6-native-" and
            not path.exists() and not path.is_symlink(), "new Week6 native output required")
    path.mkdir()
    return path


def native_environment(env, installation, out):
    home = Path(installation["private_homes"]["RUSTUP_HOME"])
    require(env.get("RUSTUP_HOME") == str(home),
            "native Rust home differs from admitted installation")
    prefix = home / "toolchains" / STABLE / "bin"
    binaries = {}
    for name in ("rustc", "cargo", "rustdoc"):
        path = prefix / name
        expected = installation["installed_closures"]["rustup"]["files"].get(
            path.relative_to(home).as_posix())
        require(type(expected) is dict and path.is_file() and not path.is_symlink() and
                os.access(path, os.X_OK) and evidence.sha(path) == expected.get("sha256"),
                "native Rust binary differs: " + name)
        binaries[name] = {"path": str(path), "sha256": evidence.sha(path)}
    result = dict(env)
    result.update(PATH=str(prefix) + os.pathsep + env["PATH"], RUSTUP_TOOLCHAIN=STABLE,
                  CARGO_HOME=str(Path(out) / "cargo-home"))
    result.pop("CARGO_TARGET_DIR", None)
    return result, binaries


def parse_check(text):
    rows = [line[len(MARKER):] for line in text.splitlines() if line.startswith(MARKER)]
    require(len(rows) == 1, "missing or duplicate independent native check")
    value = json.loads(rows[0])
    require(set(value) == {"runtime", "rust_tests"}, "native check inventory differs")
    runtime = value["runtime"]
    require(runtime["cases"] == 33 and runtime["replays"] == 33 and
            runtime["mutations"]["applied"] == 194 and runtime["mutations"]["skipped"] == 4,
            "native corpus inventory differs")
    expected = {"test_binaries": 7, "tests_passed": 78, "engine_tests": 10,
                "doctest_targets": 5, "doctests_passed": 0, "ignored": 0, "filtered_out": 0}
    require(all(type(value["rust_tests"].get(name)) is int and
                value["rust_tests"][name] == count for name, count in expected.items()),
            "native Rust test inventory differs")
    return value


def formal_anchor(path, expected_sha, frozen, root=ROOT):
    root = Path(root).resolve()
    path = Path(path)
    path = path if path.is_absolute() else root / path
    path = path.absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink() and
            re.fullmatch(r"[0-9a-f]{64}", expected_sha or "") and
            evidence.sha(path) == expected_sha, "formal report reference differs")
    report = evidence.read(path)
    require(report.get("schema_version") == 1 and
            report.get("kind") == "formal-execution-with-output-delta-v1" and
            report.get("status") ==
            "formal_execution_and_delta_recorded_pending_worktree_review" and
            report.get("errors") == [] and report.get("kernel_and_rocq_records_validated") is True and
            report.get("source_snapshot_sha256") == frozen["snapshot_sha256"] and
            report.get("policy_sha256") == POLICY_SHA,
            "formal report failed or bound to another source/policy")
    files = report.get("record_files")
    require(type(files) is dict and "generated-after-rocq.json" in files,
            "formal record inventory differs")
    for name, digest in files.items():
        evidence.linked(path.parent, name, digest)
    generated = evidence.read(evidence.linked(
        path.parent, "generated-after-rocq.json", files["generated-after-rocq.json"]))
    return path, report, generated


def main(output, formal_report, formal_report_sha256, root=ROOT):
    root = Path(root).resolve()
    require(evidence.sha(root / proof.POLICY.relative_to(ROOT)) == POLICY_SHA,
            "formal source policy changed")
    frozen = source_snapshot.capture(root)
    formal_path, _, generated = formal_anchor(
        formal_report, formal_report_sha256, frozen, root)
    out = new_output(output, root)
    with (out / "run.py").open("xb") as stream:
        stream.write(Path(__file__).read_bytes())
    report = {"schema_version": 1, "kind": "week6-native-execution-v1",
              "status": "running", "started_at": recording.now(), "stages": [], "errors": [],
              "source_snapshot_sha256": frozen["snapshot_sha256"],
              "formal_report": ref(root, formal_path), **dict.fromkeys(FLAGS, False)}
    recording.write(out / "started.json", report)
    env = dict(os.environ)

    def stage(name, argv, timeout=3600):
        row = recording.command(out, name, argv, env, timeout, root)
        report["stages"].append(row)
        require(row["status"] == "completed" and evidence.same(row["exit_code"], 0),
                "native stage failed: " + name)
        return row

    try:
        recording.write(out / "source-before.json", frozen)
        policy = evidence.read(root / proof.POLICY.relative_to(ROOT))
        selected, _, _, _ = tools.resolve(root, policy)
        selected, binaries = native_environment(
            selected, evidence.read(tools.locations.RUST_REPORT), out)
        env = selected
        require(not (out / "cargo-home").exists(), "native Cargo home must initially be absent")
        report.update(cargo_home_initially_absent=True, native_binaries=binaries,
                      generated_before=proof.generated_evidence(policy))
        require(report["generated_before"] == generated,
                "current generated models differ from formal anchor")
        stage("runtime", ["/usr/bin/python3", "-B", "-O",
                          "scripts/probes/probe_release_runtime.py", "--out", str(out / "runtime")])
        stage("rust-tests", ["/usr/bin/python3", "-B", "-O",
                             "scripts/release_rust_tests.py", "--out", str(out / "rust-tests")])
        children = [out / name / "report.json" for name in ("runtime", "rust-tests")]
        before = {path.relative_to(root).as_posix(): evidence.sha(path) for path in children}
        code = ('import json,sys; from pathlib import Path; sys.path.insert(0,"scripts"); '
                'import release_evidence as e; import release_rust_tests as r; print(' + repr(MARKER) +
                '+json.dumps({"runtime":e.check_runtime(Path(sys.argv[1])), '
                '"rust_tests":r.check(Path(sys.argv[2]))},sort_keys=True))')
        checked = stage("independent-check", ["/usr/bin/python3", "-B", "-O", "-c", code,
                                               *map(str, children)])
        report["details"] = parse_check((out / checked["log"]).read_text())
        require(before == {path.relative_to(root).as_posix(): evidence.sha(path) for path in children},
                "native child report changed during independent check")
        current = source_snapshot.capture(root)
        recording.write(out / "source-after.json", current)
        report["generated_after"] = proof.generated_evidence(policy)
        require(current == frozen and report["generated_after"] == generated and
                ref(root, formal_path) == report["formal_report"] and
                evidence.sha(out / "run.py") == evidence.sha(Path(__file__)),
                "native source/model/formal/driver identity drift")
        report["status"] = "native_runtime_and_rust_independently_verified_pending_output_review"
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["errors"].append({"error_type": type(error).__name__, "error": str(error)})
    report["finished_at"] = recording.now()
    report["record_files"] = {path.relative_to(out).as_posix(): evidence.sha(path)
                              for path in sorted(out.rglob("*")) if path.is_file()}
    recording.write(out / "report.json", report)
    print(json.dumps({"status": report["status"], "errors": report["errors"]}, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-report", type=Path, required=True)
    parser.add_argument("--formal-report-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(main(args.out, args.formal_report, args.formal_report_sha256))
    except (Exception, KeyboardInterrupt) as error:
        print("week6 native recording rejected: " + str(error), file=sys.stderr)
        raise SystemExit(1)
