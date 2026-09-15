#!/usr/bin/env python3
"""Exactly rescan one reviewed Week6 output observation.

The observation fixes the complete selected root set.  The review
materialization must bind three disjoint review reports for that observation.
This producer then captures the same roots again and accepts only byte- and
structure-identical inventory JSON.  It does not claim atomicity, output
semantics, delivery approval, clean-room execution or release completion.
"""

import argparse
import json
import os
from pathlib import Path
import sys

import generated_output_inventory as inventory
import record_generation as recording
import release_current_output_review as validator
import release_evidence as common
import source_snapshot


ROOT = Path(__file__).resolve().parents[1]
FLAGS = validator.CONFIRMATION_FLAGS


def require(value, message):
    if not value:
        raise RuntimeError(message)


def ref(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            "confirmation reference outside/missing")
    return {"path": path.relative_to(root).as_posix(), "sha256": common.sha(path)}


def regular(root, path, label):
    root = Path(root).resolve()
    path = Path(path)
    path = path if path.is_absolute() else root / path
    path = path.absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            label + " outside/missing")
    for parent in path.parents:
        if parent == root:
            break
        require(not parent.is_symlink(), label + " has linked parent")
    return path


def new_output(path, root=ROOT):
    root, path = Path(root).resolve(), Path(path).absolute()
    parent = root / "artifacts/boundary-check"
    require(parent.is_dir() and not parent.is_symlink() and path.parent == parent and
            path.name.startswith("week6-output-confirmation-") and
            path.name != "week6-output-confirmation-" and
            not path.exists() and not path.is_symlink(),
            "new Week6 output confirmation required")
    path.mkdir()
    return path


def copy_regular(source, destination):
    source, destination = Path(source), Path(destination)
    require(source.is_file() and not source.is_symlink() and
            all(not parent.is_symlink() for parent in source.parents),
            "missing/linked confirmation source")
    before = common.sha(source)
    data = source.read_bytes()
    with destination.open("xb") as stream:
        stream.write(data)
    require(common.sha(source) == before == common.sha(destination),
            "confirmation source changed while copying")


def load_inputs(observation, reviews, root=ROOT):
    root = Path(root).resolve()
    observation_path = regular(root, observation, "observation")
    reviews_path = regular(root, reviews, "output review materialization")
    observed = common.read(observation_path)
    materialized = common.read(reviews_path)
    require(observed.get("schema_version") == 1 and
            observed.get("kind") == "current-expanded-output-observation-v1" and
            observed.get("status") ==
            "current_output_observation_and_complete_formal_delta_recorded_pending_review" and
            observed.get("errors") == [] and
            all(observed.get(name) is False for name in validator.OBSERVATION_FLAGS),
            "output observation incomplete/unknown")
    require(type(materialized) is dict and set(materialized) == {
        "schema_version", "kind", "status", "source_snapshot_sha256",
        "observation", "policy", "reports", "counts", "remaining", "boundaries"
    } and materialized["schema_version"] == 1 and
            materialized["kind"] == "week6-output-review-materialization-v1" and
            materialized["status"] ==
            "all_additional_output_nodes_partitioned_pending_exact_rescan" and
            materialized["remaining"] == ["exact_current_output_rescan_confirmation"],
            "output review materialization incomplete/unknown")
    require(materialized["observation"] == ref(root, observation_path),
            "output reviews bind another observation")
    require(observed.get("source_snapshot_sha256") ==
            materialized["source_snapshot_sha256"],
            "observation/review source identity differs")
    require(type(materialized["reports"]) is dict and
            set(materialized["reports"]) == {"registry_review", "build_review", "record_review"},
            "output review report inventory differs")
    require(type(materialized["counts"]) is dict and
            set(materialized["counts"]) == {"registry", "build", "record"} and
            all(type(value) is int and value >= 0 for value in materialized["counts"].values()),
            "output review counts differ")
    report_paths = {}
    review_specs = {"registry_review": ("registry", "reviewed_nodes"),
                    "build_review": ("build", "new_reviewed_nodes"),
                    "record_review": ("record", "new_reviewed_nodes")}
    for name, row in materialized["reports"].items():
        require(type(row) is dict and set(row) == {"path", "sha256"},
                "invalid output review reference")
        report_paths[name] = common.linked(root, row["path"], row["sha256"])
        review_report = common.read(report_paths[name])
        require(review_report.get("source_snapshot_sha256") ==
                observed["source_snapshot_sha256"] and review_report.get("errors") == [],
                "output review report source/status differs")
        review_ref = review_report.get("review")
        require(type(review_ref) is dict and set(review_ref) == {"path", "sha256"},
                "output review member reference differs")
        review = common.read(common.linked(root, review_ref["path"], review_ref["sha256"]))
        count_name, rows_name = review_specs[name]
        require(type(review.get(rows_name)) is dict and
                len(review[rows_name]) == materialized["counts"].get(count_name),
                "output review materialized count differs")
    policy_ref = materialized["policy"]
    require(type(policy_ref) is dict and set(policy_ref) == {"path", "sha256"},
            "output review policy reference differs")
    common.linked(root, policy_ref["path"], policy_ref["sha256"])
    require(materialized["boundaries"] == {
        "semantic_correctness_proven": False, "generated_outputs_audited": False,
        "delivery_approved": False, "worktree_audit_closed": False,
        "release_claimed": False, "week6_closed": False,
    }, "output review assurance boundary differs")
    return observation_path, reviews_path, observed, materialized, report_paths


def run(observation, reviews, output, root=ROOT, timeout=7200):
    root = Path(root).resolve()
    observation_path, reviews_path, observed, materialized, report_paths = \
        load_inputs(observation, reviews, root)
    reviews_anchor = ref(root, reviews_path)
    frozen = source_snapshot.capture(root)
    require(observed["source_snapshot_sha256"] == frozen["snapshot_sha256"],
            "observation source is not current")
    out = new_output(output, root)
    copy_regular(Path(__file__).resolve(), out / "run.py")
    report = {"schema_version": 1, "kind": "current-output-exact-rescan-confirmation-v1",
              "status": "running", "started_at": recording.now(), "stages": [], "errors": [],
              **dict.fromkeys(FLAGS, False)}
    recording.write(out / "started.json", report)
    try:
        recording.write(out / "source-before.json", frozen)
        current_ref = observed.get("current_inventory")
        require(type(current_ref) is dict and set(current_ref) == {"path", "sha256"},
                "observation current inventory reference")
        old_path = common.linked(root, current_ref["path"], current_ref["sha256"])
        old = common.read(old_path)
        inventory.validate(old)
        extras = [name for name in old["roots"] if name not in inventory.CANONICAL_ROOTS]
        argv = ["/usr/bin/python3", "-B", "-O", "scripts/generated_output_inventory.py",
                "capture", "--out", str(out / "current")]
        for name in extras:
            argv.extend(["--extra-root", name])
        stage = recording.command(out, "capture-current", argv, dict(os.environ), timeout, root)
        report["stages"].append(stage)
        require(stage["status"] == "completed" and common.same(stage["exit_code"], 0),
                "current output rescan failed")
        new_path = out / "current/snapshot.json"
        rescanned = common.read(new_path)
        inventory.validate(rescanned)
        require(common.sha(new_path) == common.sha(old_path) and common.same(rescanned, old),
                "current output identity differs from reviewed observation")
        after = source_snapshot.capture(root)
        recording.write(out / "source-after.json", after)
        require(after == frozen and common.sha(out / "run.py") == common.sha(Path(__file__).resolve()),
                "source or confirmation driver changed during rescan")
        # Recheck every external anchor after the potentially long capture.
        require(ref(root, observation_path) == materialized["observation"] and
                ref(root, reviews_path) == reviews_anchor,
                "observation or review materialization changed during rescan")
        for name, path in report_paths.items():
            require(ref(root, path) == materialized["reports"][name],
                    "output review report changed during rescan")
        report.update(
            status="current_24_root_snapshot_exactly_matches_reviewed_observation",
            source_snapshot_sha256=frozen["snapshot_sha256"],
            observation_report_sha256=common.sha(observation_path),
            observed_snapshot_sha256=old["snapshot_sha256"], snapshot=ref(root, new_path))
    except Exception as error:
        report["status"] = "failed"
        report["errors"].append({"error_type": type(error).__name__, "error": str(error)})
    report["finished_at"] = recording.now()
    report["record_files"] = {
        path.relative_to(out).as_posix(): common.sha(path)
        for path in sorted(out.rglob("*")) if path.is_file()
    }
    recording.write(out / "report.json", report)
    validation = None
    if not report["errors"]:
        component = {"observation": ref(root, observation_path),
                     **materialized["reports"], "confirmation": ref(root, out / "report.json")}
        validation = validator.check(component, frozen["snapshot_sha256"], root=root)
        require(validation["reviewed_additional_nodes"] == sum(materialized["counts"].values()),
                "validated output review count differs from materialization")
    return report, validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()
    try:
        report, validation = run(args.observation, args.reviews, args.out,
                                 timeout=args.timeout)
        print(json.dumps({"status": report["status"], "errors": report["errors"],
                          "composition": validation}, indent=2, sort_keys=True))
        return 1 if report["errors"] else 0
    except (Exception, KeyboardInterrupt) as error:
        print("week6 output confirmation rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
