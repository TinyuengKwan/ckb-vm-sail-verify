#!/usr/bin/env python3
"""Produce and validate the runtime slot: Rust tests, corpus differential,
mutation matrix and byte-identical relocated replays.

``tests`` runs every workspace test (ignored engine tests included) into a new
Cargo target.  ``run`` builds the differential CLI into a new target, runs the
corpus with the mutation matrix, copies every artifact and replays each copy.
``check`` reopens every artifact and recomputes the comparison and all six
mutations; a summary field is never trusted on its own.  None of this is a
proof of the adapters or of the ISA model, and none of it is a clean room.
"""
import argparse
from collections import Counter
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ckb_source_baseline as baseline
import release_common as common

ROOT = common.ROOT
require, same, sha, read = common.require, common.same, common.sha, common.read
SAIL_BIN = "deps/sail-riscv/build/c_emulator/sail_riscv_sim"
CONFIG = "sail-model/build/ckb_vm_config.json"
FIELDS = ("order", "instruction", "pc_before", "pc_after", "register_writes", "memory", "trap", "halt")
MUTATIONS = {"pc_after": "pc_after", "register_index": "register_writes", "register_value": "register_writes",
             "trap": "trap", "trace_length": "trace_length", "termination": "termination"}
FAMILIES = {"ADD": (0xfe00707f, 0x33), "ADDI": (0x707f, 0x13), "BEQ": (0x707f, 0x63)}
MINIMUM_PER_FAMILY = 10
ENGINE_TESTS = {
    "every_corpus_case_agrees_step_by_step", "a_diverging_instruction_stream_is_located",
    "a_missing_final_event_is_detected", "the_packet_fixture_still_matches_the_live_emulator",
    "a_compressed_instruction_is_normalized_on_both_sides",
    "a_trapping_instruction_diverges_and_is_reported_not_hidden",
    "a_failing_engine_is_an_error_rather_than_a_pass",
    "every_mandatory_mutation_is_detected_and_located_on_real_traces",
    "a_mutation_matrix_over_no_cases_does_not_pass", "concurrent_sessions_survive_the_port_race"}
TEST_COMMAND = ["cargo", "test", "--workspace", "--locked", "--", "--include-ignored", "--test-threads=1"]


# ---- artifact validation ---------------------------------------------------

def integer(value, low, high):
    return type(value) is int and low <= value <= high


def first_difference(left, right):
    for i, (a, b) in enumerate(zip(left["events"], right["events"])):
        for field in FIELDS:
            if a[field] != b[field]:
                return field, i
    if len(left["events"]) != len(right["events"]):
        return "trace_length", min(len(left["events"]), len(right["events"]))
    if left["end"] != right["end"]:
        return "termination", None
    if not left["events"]:
        return "empty_trace", None
    return None, None


def mutated(trace, kind, focus):
    result = copy.deepcopy(trace)
    events = result["events"]
    if kind in ("register_index", "register_value"):
        index = focus if events[focus]["register_writes"] else next(
            (i for i, row in enumerate(events) if row["register_writes"]), None)
        if index is None:
            return None
        write = events[index]["register_writes"][0]
        if kind == "register_index":
            write["index"] = 1 if write["index"] >= 31 else write["index"] + 1
        else:
            write["value"] ^= 1
    elif kind == "pc_after":
        events[focus]["pc_after"] = (events[focus]["pc_after"] + 2) % 2 ** 64
    elif kind == "trap":
        events[focus]["trap"] = not events[focus]["trap"]
    elif kind == "trace_length":
        events.pop()
    elif kind == "termination":
        result["end"] = {"kind": "step_limit"}
    else:
        raise RuntimeError("unknown mutation")
    return result


def check_case(row, artifact, environment):
    require(same(artifact["schema_version"], 3), "old/unknown case schema")
    case = artifact["case"]
    words, focus = case["instructions"], case["focus_step"]
    require(isinstance(words, list) and words and all(integer(w, 0, 2 ** 32 - 1) for w in words), "invalid program words")
    require(integer(focus, 0, len(words) - 1), "invalid focus instruction")
    require(artifact["instructions_hex"] == [f"0x{w:08x}" for w in words], "program/hex mismatch")
    require(case["family"] in FAMILIES, "unapproved corpus family")
    mask, value = FAMILIES[case["family"]]
    require(words[focus] & mask == value, "focus opcode does not match declared family")
    require(artifact["initial_state"] == {"pc": 0x80000000, "integer_registers": "x0..x31 = 0"}, "unsupported initial state")
    require(same(artifact["environment"], environment), "mixed runtime environments")
    for key in ["id", "description", "family", "focus_step"]:
        require(same(row[key], case[key]), "case/report mismatch: " + key)
    require(type(row["instructions"]) is int and row["instructions"] == len(words), "instruction count mismatch")
    for evidence in [row, artifact]:
        require(evidence["passed"] is True and evidence["classification"] == "match" and evidence["error"] is None,
                "case is not a clean passing baseline")
        require(same(evidence["comparison"], {"compared_steps": len(words), "mismatch": None}),
                "comparison omitted events or reports mismatch")
    for name in ["ckb_trace", "sail_trace"]:
        trace = artifact[name]
        require(isinstance(trace, dict) and set(trace) == {"events", "end"}, "invalid trace schema")
        require(len(trace["events"]) == len(words) and trace["end"] == {"kind": "injection_complete"},
                "trace length/termination mismatch")
        pc = 0x80000000
        for i, event in enumerate(trace["events"]):
            require(set(event) == set(FIELDS), "unknown/missing observation field")
            require(type(event["order"]) is int and event["order"] == i and
                    type(event["instruction"]) is int and event["instruction"] == words[i],
                    "trace order/instruction not the input stream")
            require(integer(event["pc_before"], 0, 2 ** 64 - 1) and event["pc_before"] == pc and
                    integer(event["pc_after"], 0, 2 ** 64 - 1), "invalid PC sequence")
            require(event["trap"] is False and event["halt"] is False and event["memory"] == [],
                    "unexpected trap/halt/memory observation in corpus")
            writes = event["register_writes"]
            require(isinstance(writes, list) and all(set(w) == {"index", "value"} and integer(w["index"], 1, 31) and
                    integer(w["value"], 0, 2 ** 64 - 1) for w in writes), "invalid register write")
            indices = [w["index"] for w in writes]
            require(indices == sorted(set(indices)), "unnormalized register writes")
            pc = event["pc_after"]
    require(first_difference(artifact["ckb_trace"], artifact["sail_trace"]) == (None, None),
            "actual normalized engine traces differ")
    packets = artifact["sail_raw_packets"]
    require(len(packets) == len(words) + 1 and all(isinstance(p, str) and re.fullmatch("[0-9a-f]{176}", p) for p in packets),
            "missing/invalid raw RVFI-DII packets")
    require(isinstance(artifact["replay"]["from_artifact"], str) and artifact["replay"]["from_artifact"], "missing replay command")


def check_mutations(summary, cases):
    require(type(summary["cases"]) is int and summary["cases"] == len(cases), "mutation case count")
    require(summary["passed"] is True and all(summary[k] == [] for k in ["baseline_failures", "undetected", "mislocated"]),
            "mutation failures reported")
    rows = summary["reports"]
    expected = {(name, kind) for name in cases for kind in MUTATIONS}
    keys = [(r["case_id"], r["mutation"]) for r in rows]
    require(len(keys) == len(expected) and set(keys) == expected, "mutation matrix incomplete or duplicated")
    counts, located = Counter(), {kind: [] for kind in MUTATIONS}
    for row in rows:
        kind = row["mutation"]
        require(row["expected_field"] == MUTATIONS[kind], "mutation expected field changed")
        artifact = cases[row["case_id"]]
        result = mutated(artifact["ckb_trace"], kind, artifact["case"]["focus_step"])
        if result is None:
            require(row["applied"] is False and row["detected"] is False and row["passed"] is False and
                    row["located_field"] is None and row["located_step"] is None and
                    isinstance(row["skipped_because"], str) and row["skipped_because"], "invalid skipped mutation evidence")
            counts["skipped"] += 1
            continue
        field, step = first_difference(result, artifact["sail_trace"])
        require(field == MUTATIONS[kind], "recomputed mutation not localized")
        require(row["applied"] is True and row["detected"] is True and row["passed"] is True and
                row["skipped_because"] is None and row["located_field"] == field and same(row["located_step"], step),
                "mutation result disagrees with actual trace mutation")
        counts["applied"] += 1
        counts[kind] += 1
        located[kind].append(row["case_id"])
    require(all(type(summary[k]) is int and summary[k] == counts[k] for k in ["applied", "skipped"]), "mutation totals changed")
    coverage = summary["coverage"]
    require(len(coverage) == len(MUTATIONS) and {c["mutation"] for c in coverage} == set(MUTATIONS), "mutation coverage incomplete")
    for row in coverage:
        kind = row["mutation"]
        require(counts[kind] > 0 and row["expected_field"] == MUTATIONS[kind] and
                row["applied"] == row["located"] == counts[kind] and row["example_case"] in located[kind],
                "invalid coverage tally/example")
    return dict(counts)


def validate(report_path, artifact_directory, environment):
    """Revalidate one corpus report against its artifact directory."""
    report_path, artifact_directory = Path(report_path), Path(artifact_directory).resolve()
    report = read(report_path)
    require(same(report["schema_version"], 3) and report["mode"] == "corpus" and report["terminal_policy"] == "exact",
            "wrong runtime report schema/mode")
    require(same(report["environment"], environment), "runtime environment not approved")
    rows = report["results"]
    require(len(rows) >= MINIMUM_PER_FAMILY and len({r["id"] for r in rows}) == len(rows), "too few/duplicate corpus cases")
    require(same(report["summary"], {"total": len(rows), "failures": 0, "mutations_passed": True, "passed": True}),
            "runtime summary failure or inconsistent counts")
    cases, hashes = {}, {}
    for row in rows:
        require(isinstance(row["id"], str) and re.fullmatch("[a-z0-9][a-z0-9-]*", row["id"]), "unsafe case id")
        name = row["id"] + ".json"
        require(Path(row["artifact"]).name == name, "recorded artifact filename differs")
        path = artifact_directory / name
        require(not path.is_symlink(), "linked case artifact")
        artifact = read(path)
        check_case(row, artifact, environment)
        cases[row["id"]], hashes[name] = artifact, sha(path)
    families = Counter(a["case"]["family"] for a in cases.values())
    require(set(families) == set(FAMILIES), "missing required instruction family")
    require(all(count >= MINIMUM_PER_FAMILY for count in families.values()),
            "Week6 requires at least 10 cases per instruction family: " + str(dict(families)))
    mutation_file = artifact_directory / "mutations.json"
    require(not mutation_file.is_symlink(), "linked mutation artifact")
    recorded = read(mutation_file)
    require(same(recorded["schema_version"], 3) and same(recorded["environment"], environment) and
            same(recorded["seed"], report["seed"]) and same(recorded["summary"], report["mutations"]) and
            isinstance(recorded["replay"], str) and recorded["replay"], "mutation artifact/report mismatch")
    mutations = check_mutations(report["mutations"], cases)
    hashes["mutations.json"] = sha(mutation_file)
    require({p.name for p in artifact_directory.iterdir()} == set(hashes), "unexpected/missing artifact entry")
    return {"status": "runtime_evidence_verified", "report_sha256": sha(report_path), "artifact_sha256": hashes,
            "cases": len(cases), "families": dict(families), "mutations": mutations, "release_claimed": False}


def check_replay(report, artifact, original, environment):
    require(same(report["schema_version"], 3) and report["mode"] == "replay" and report["terminal_policy"] == "exact" and
            report["mutations"] is None and report["seed"] is None, "invalid replay envelope")
    require(same(report["environment"], environment) and
            same(report["summary"], {"total": 1, "failures": 0, "mutations_passed": None, "passed": True}), "replay did not pass")
    require(len(report["results"]) == 1, "replay case count")
    check_case(report["results"][0], artifact, environment)
    for key in ["case", "instructions_hex", "initial_state", "ckb_trace", "sail_trace", "sail_raw_packets"]:
        require(same(artifact[key], original[key]), "replay changed original evidence: " + key)


def check_test_log(text):
    """Every harness must finish with zero failures; the engine tests must have run."""
    passed, names = 0, set()
    for line in text.splitlines():
        ok = re.fullmatch(r"test (\S+) \.\.\. ok", line.strip())
        if ok:
            names.add(ok[1].rsplit("::", 1)[-1])
        finish = re.match(r"test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;", line.strip())
        if finish:
            require(finish[1] == "ok" and finish[3] == "0", "Rust test harness reported failures")
            passed += int(finish[2])
    require(passed > 0 and "test result:" in text, "no Rust test results recorded")
    require(ENGINE_TESTS <= names, "mandatory real-engine tests not executed: " + str(sorted(ENGINE_TESTS - names)))
    return passed


# ---- producers --------------------------------------------------------------

def environment(root=ROOT):
    env = dict(os.environ)
    cache = root / "deps/sail-riscv/build/CMakeCache.txt"
    settings = dict(line.split("=", 1) for line in cache.read_text().splitlines()
                    if "=" in line and not line.startswith(("#", "//")))
    require(Path(settings["CMAKE_HOME_DIRECTORY:INTERNAL"]).resolve() == root / "deps/sail-riscv", "wrong CMake source checkout")
    compiler = Path(settings["SAIL_BIN:FILEPATH"]).resolve(strict=True)
    env["PATH"] = str(compiler.parent) + os.pathsep + env["PATH"]
    env.update(SAIL_BIN=str(root / SAIL_BIN), SAIL_CONFIG=str(root / CONFIG), CARGO_TERM_COLOR="never")
    for key in ["RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "CARGO_BUILD_RUSTFLAGS", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER",
                "RUSTC", "RUSTDOC", "CARGO_TARGET_DIR", "RUST_TEST_THREADS", "RUST_TEST_NOCAPTURE", "RUST_TEST_SHUFFLE"]:
        env.pop(key, None)
    return env, compiler


def observed_environment(env, root=ROOT):
    def output(argv):
        return subprocess.check_output(argv, cwd=root, env=env, text=True, stderr=subprocess.PIPE, timeout=60).strip()
    source = baseline.check(root)
    return {"ckb_vm_commit": source["upstream_commit"], "ckb_vm_source_baseline": source,
            "sail_riscv_commit": output(["git", "-C", "deps/sail-riscv", "rev-parse", "HEAD"]),
            "sail_model_version": output([SAIL_BIN, "--version"]),
            "sail_bin": SAIL_BIN, "sail_config": CONFIG, "sail_config_sha256": sha(root / CONFIG),
            "ckb_vm_isa_bits": 1, "ckb_vm_isa": "IMC+B", "ckb_vm_version": 2,
            "rustc": output(["rustc", "--version"]).splitlines()[0],
            "cargo": output(["cargo", "--version"]).splitlines()[0],
            "sail_compiler": output(["sail", "--version"]).splitlines()[0]}


def new_output(path):
    out = Path(path).resolve()
    out.mkdir(parents=True, exist_ok=False)
    return out


def finish(out, report, code):
    report["finished_at"] = common.stamp()
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "report": str(out / "report.json")}), flush=True)
    return code


def tests(out, root=ROOT):
    out = new_output(out)
    report = {"schema_version": 1, "kind": "rust-tests-v1", "status": "running", "started_at": common.stamp(),
              "stages": [], "release_claimed": False, "clean_room_claimed": False}
    try:
        env, _ = environment(root)
        target = out / "cargo-target"
        env["CARGO_TARGET_DIR"] = str(target)
        report["environment"] = observed_environment(env, root)
        for name, argv in [("verify-environment", ["bash", "scripts/verify_environment.sh"]), ("cargo-test", TEST_COMMAND)]:
            row = common.run_command(out, name, argv, root, env=env, timeout=3600)
            report["stages"].append(row)
            require(row["exit_code"] == 0, "stage failed: " + name)
        report["tests_passed"] = check_test_log((out / "cargo-test.stdout").read_text())
        report["engine_tests"] = sorted(ENGINE_TESTS)
        require(observed_environment(env, root) == report["environment"], "environment changed during tests")
        report["status"] = "passed"
        return finish(out, report, 0)
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="failed", error=str(error), error_type=type(error).__name__)
        return finish(out, report, 1)


def run(out, tests_report, root=ROOT):
    out = new_output(out)
    report = {"schema_version": 1, "kind": "runtime-evidence-v1", "status": "running", "started_at": common.stamp(),
              "stages": [], "release_claimed": False, "clean_room_claimed": False, "sail_emulator_rebuilt": False}
    try:
        tests_report = Path(tests_report).resolve()
        tests_value = read(tests_report)
        require(tests_value.get("kind") == "rust-tests-v1" and tests_value.get("status") == "passed", "Rust tests did not pass")
        report["rust_tests"] = {"path": os.path.relpath(tests_report, out), "sha256": sha(tests_report)}
        env, _ = environment(root)
        target = out / "cargo-target"
        env["CARGO_TARGET_DIR"] = str(target)
        report["environment"] = expected = observed_environment(env, root)
        require(same(tests_value["environment"], expected), "Rust tests ran in a different environment")

        def stage(name, argv, timeout=1800):
            row = common.run_command(out, name, argv, root, env=env, timeout=timeout)
            report["stages"].append(row)
            require(row["exit_code"] == 0, "stage failed: " + name)
            return out / (name + ".stdout")
        stage("verify-environment", ["bash", "scripts/verify_environment.sh"])
        stage("build-cli", ["cargo", "build", "--locked", "-p", "ckb-vm-sail-diff"])
        binary = target / "debug/ckb-vm-sail-diff"
        report["binary_sha256"] = sha(binary)
        shutil.copyfile(binary, out / "ckb-vm-sail-diff")
        (out / "ckb-vm-sail-diff").chmod(0o755)
        common_args = [str(binary), "--json", "--sail-bin", SAIL_BIN, "--sail-config", CONFIG]
        corpus = stage("corpus-mutations", [*common_args, "--corpus", "--mutate", "--artifact-dir", str(out / "original")])
        report["runtime"] = validate(corpus, out / "original", expected)
        relocated = out / "relocated"
        relocated.mkdir()
        for name, digest in report["runtime"]["artifact_sha256"].items():
            shutil.copyfile(out / "original" / name, relocated / name)
            require(sha(relocated / name) == digest, "copy changed bytes")
        require(validate(corpus, relocated, expected) == report["runtime"], "relocated evidence changed")
        report["replays"] = []
        for row in read(corpus)["results"]:
            name = row["id"]
            source, directory = relocated / (name + ".json"), out / "replays" / name
            replay = stage("replay-" + name, [*common_args, "--replay", str(source), "--artifact-dir", str(directory)])
            artifact = directory / (name + ".json")
            require({p.name for p in directory.iterdir()} == {artifact.name}, "extra replay outputs")
            check_replay(read(replay), read(artifact), read(source), expected)
            report["replays"].append({"case_id": name, "artifact_sha256": sha(artifact), "input_sha256": sha(source)})
        require(observed_environment(env, root) == expected and sha(binary) == report["binary_sha256"],
                "environment/binary changed during run")
        report["status"] = "passed"
        return finish(out, report, 0)
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="failed", error=str(error), error_type=type(error).__name__)
        return finish(out, report, 1)


# ---- validator ----------------------------------------------------------------

def check(path):
    """Revalidate a runtime report from its files alone; no toolchain is probed."""
    path = Path(path)
    out, report = path.parent, read(path)
    require(same(report["schema_version"], 1) and report["kind"] == "runtime-evidence-v1" and
            report["status"] == "passed" and report["release_claimed"] is False and
            report["sail_emulator_rebuilt"] is False, "runtime report incomplete/assurance changed")
    expected = report["environment"]
    tests_path = (out / report["rust_tests"]["path"]).resolve()
    require(tests_path.is_relative_to(out.resolve().parent) and tests_path.is_file() and not tests_path.is_symlink() and
            sha(tests_path) == report["rust_tests"]["sha256"], "Rust test report missing/outside/changed")
    tests_value = read(tests_path)
    require(tests_value["kind"] == "rust-tests-v1" and tests_value["status"] == "passed" and
            same(tests_value["environment"], expected), "Rust test report status/environment")
    common.check_stages(tests_path.parent, tests_value["stages"], ["verify-environment", "cargo-test"])
    require(tests_value["stages"][1]["argv"] == TEST_COMMAND, "Rust test command changed")
    tests_passed = check_test_log((tests_path.parent / "cargo-test.stdout").read_text())
    require(tests_passed == tests_value["tests_passed"], "Rust test count differs from log")
    corpus = common.member(out, "corpus-mutations.stdout")
    result = validate(corpus, out / "original", expected)
    require(same(result, report["runtime"]) and same(result, validate(corpus, out / "relocated", expected)),
            "runtime originals/copies no longer agree")
    ids = [row["id"] for row in read(corpus)["results"]]
    names = ["verify-environment", "build-cli", "corpus-mutations"] + ["replay-" + name for name in ids]
    common.check_stages(out, report["stages"], names)
    common.linked(out, "ckb-vm-sail-diff", report["binary_sha256"])
    binary = report["stages"][2]["argv"][0]
    for stage_row, name in zip(report["stages"][3:], ids):
        argv = stage_row["argv"]
        # The run may have happened under another root (a guest); compare the
        # command shape and the output-relative paths, not the absolute prefix.
        require(len(argv) == 10 and argv[:7] == [binary, "--json", "--sail-bin", SAIL_BIN, "--sail-config", CONFIG, "--replay"] and
                Path(argv[7]).parts[-2:] == ("relocated", name + ".json") and argv[8] == "--artifact-dir" and
                Path(argv[9]).parts[-2:] == ("replays", name), "replay command changed: " + name)
    require([r["case_id"] for r in report["replays"]] == ids, "replay inventory")
    for row in report["replays"]:
        name = row["case_id"]
        artifact = common.linked(out, f"replays/{name}/{name}.json", row["artifact_sha256"])
        original = common.linked(out, "relocated/" + name + ".json", row["input_sha256"])
        check_replay(read(out / ("replay-" + name + ".stdout")), read(artifact), read(original), expected)
    return {"scope": "corpus_differential_mutation_matrix_relocated_replays_and_workspace_tests",
            "cases": result["cases"], "families": result["families"], "mutations": result["mutations"],
            "replays": len(ids), "rust_tests_passed": tests_passed, "engine_tests": len(ENGINE_TESTS),
            "environment": {k: expected[k] for k in ("rustc", "cargo", "sail_compiler", "sail_model_version")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("tests", "run"):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True, type=Path, help="new directory")
        if name == "run":
            p.add_argument("--tests-report", required=True, type=Path)
    checker = sub.add_parser("check")
    checker.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.command == "tests":
        return tests(args.out)
    if args.command == "run":
        return run(args.out, args.tests_report)
    try:
        print(json.dumps(check(args.report), indent=2, sort_keys=True))
        return 0
    except Exception as error:
        print("runtime evidence rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
