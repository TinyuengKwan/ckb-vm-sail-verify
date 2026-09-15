#!/usr/bin/env python3
"""Partition and record every node outside the fresh formal output scope.

The tracked policy admits only known producer-root prefixes. Registry, build
and remaining record nodes are disjoint and exhaustive. Classification records
never claim semantic correctness, delivery approval or release completion.
"""

import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import sys

import generated_output_inventory as inventory
import release_current_output_review as validator
import release_evidence as common
import source_snapshot
import week6_review_materialize as review_policy


ROOT = Path(__file__).resolve().parents[1]
FLAGS = validator.REVIEW_FALSE_FLAGS
SPECS = {
    "registry": ("partial_additional_registry_review_checked_other_nodes_pending",
                 "partial-additional-cargo-registry-review-v1", "reviewed_nodes"),
    "build": ("additional_build_and_directory_records_checked_other_files_pending",
              "partial-additional-build-and-directory-review-v1", "new_reviewed_nodes"),
    "record": ("all_additional_observed_nodes_record_reviewed_with_non_semantic_boundaries",
               "additional-record-and-cache-review-v1", "new_reviewed_nodes"),
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def ref(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            "output review reference outside/missing")
    return {"path": path.relative_to(root).as_posix(), "sha256": sha(path)}


def new_output(path, root=ROOT):
    root, path = Path(root).resolve(), Path(path).absolute()
    parent = root / "artifacts/boundary-check"
    require(parent.is_dir() and not parent.is_symlink() and path.parent == parent and
            path.name.startswith("week6-output-review-") and path.name != "week6-output-review-" and
            not path.exists() and not path.is_symlink(), "new Week6 output review required")
    path.mkdir()
    return path


def load_observation(path, root):
    path = Path(path)
    path = path if path.is_absolute() else Path(root) / path
    path = path.absolute()
    require(path.is_relative_to(Path(root).resolve()) and path.is_file() and not path.is_symlink(),
            "observation outside/missing")
    report = common.read(path)
    require(report.get("schema_version") == 1 and
            report.get("kind") == "current-expanded-output-observation-v1" and
            report.get("status") ==
            "current_output_observation_and_complete_formal_delta_recorded_pending_review" and
            report.get("errors") == [] and report.get("changed_historical_nodes") == 0 and
            report.get("change_operations") == {} and report.get("non_atomic_observation_only") is True,
            "output observation incomplete or historical output changed")
    require(all(report.get(name) is False for name in validator.OBSERVATION_FLAGS),
            "output observation assurance upgrade")
    files = report.get("record_files")
    require(type(files) is dict and
            {"additional-observed-nodes.json", "current-formal-scope.json"} <= set(files),
            "observation record inventory")
    additional_path = path.parent / "additional-observed-nodes.json"
    require(sha(additional_path) == files["additional-observed-nodes.json"],
            "additional-node record differs")
    additional = common.read(additional_path)
    inventory_path = common.linked(root, report["current_inventory"]["path"],
                                   report["current_inventory"]["sha256"])
    current_inventory = common.read(inventory_path)
    inventory.validate(current_inventory)
    projected_path = path.parent / "current-formal-scope.json"
    require(sha(projected_path) == files["current-formal-scope.json"],
            "formal projection record differs")
    projected = common.read(projected_path)
    inventory.validate(projected)
    require(additional.get("schema_version") == 1 and
            additional.get("observed_snapshot_sha256") == current_inventory["snapshot_sha256"] and
            additional.get("historical_absence_claimed") is False and
            additional.get("generated_outputs_audited") is False and
            type(additional.get("entries")) is dict and
            set(additional["entries"]) ==
            set(current_inventory["entries"]) - set(projected["entries"]) and
            all(common.same(node, current_inventory["entries"][name])
                for name, node in additional["entries"].items()),
            "additional-node record identity/boundary")
    return path, report, additional["entries"]


def classify(name, node, config):
    inventory.safe(name)
    require(any(name.startswith(prefix) for prefix in config["allowed_root_prefixes"]),
            "additional node outside approved producer roots: " + name)
    require(node is None or type(node) is dict, "invalid additional node")
    if config["registry_marker"] in name:
        return "registry", "cargo_registry_or_cache"
    if any(marker in name for marker in config["build_markers"]):
        return "build", "generated_build_or_compiler_cache"
    return "record", "execution_source_or_audit_record"


def review_row(node, category, policy_ref):
    return {"node_sha256": inventory.digest(node), "category": category,
            "evidence": {"policy": policy_ref, "classification_only": True},
            "semantic_correctness_proven": False, "delivery_approved": False}


def produce(observation, policy_path, output, root=ROOT):
    root = Path(root).resolve()
    policy, policy_file = review_policy.policy(policy_path, root)
    observation_path, observed, additional = load_observation(observation, root)
    current = source_snapshot.capture(root)
    require(observed["source_snapshot_sha256"] == current["snapshot_sha256"],
            "observation source is not current")
    policy_reference = ref(root, policy_file)
    groups = {name: {} for name in SPECS}
    for name, node in sorted(additional.items()):
        group, category = classify(name, node, policy["output_review"])
        groups[group][name] = review_row(node, category, policy_reference)
    require(set().union(*(set(rows) for rows in groups.values())) == set(additional) and
            not any(set(groups[a]) & set(groups[b]) for a, b in
                    [("registry", "build"), ("registry", "record"), ("build", "record")]),
            "output review partition is not disjoint and complete")

    out = new_output(output, root)
    reports = {}
    prior = 0
    order = ["registry", "build", "record"]
    for index, name in enumerate(order):
        directory = out / name
        directory.mkdir()
        status, kind, field = SPECS[name]
        remaining = set().union(*(set(groups[item]) for item in order[index + 1:]))
        review = {"schema_version": 1, "kind": kind,
                  "source_snapshot_sha256": current["snapshot_sha256"], field: groups[name],
                  "category_counts": dict(Counter(row["category"] for row in groups[name].values())),
                  "remaining_unreviewed_nodes": {item: True for item in sorted(remaining)},
                  **({"prior_reviewed_nodes": prior} if name != "registry" else {}),
                  **{flag: False for flag in FLAGS}}
        review_path = directory / "review.json"
        write(review_path, review)
        report = {"schema_version": 1, "kind": "week6-output-partition-report-v1",
                  "status": status, "started_at": stamp(), "finished_at": stamp(),
                  "errors": [], "source_snapshot_sha256": current["snapshot_sha256"],
                  "review": ref(root, review_path),
                  "record_files": {"review.json": sha(review_path)},
                  **{flag: False for flag in FLAGS}}
        report_path = directory / "report.json"
        write(report_path, report)
        reports[name + "_review"] = ref(root, report_path)
        prior += len(groups[name])
    require(prior == len(additional), "output review count differs")
    result = {"schema_version": 1, "kind": "week6-output-review-materialization-v1",
              "status": "all_additional_output_nodes_partitioned_pending_exact_rescan",
              "source_snapshot_sha256": current["snapshot_sha256"],
              "observation": ref(root, observation_path), "policy": policy_reference,
              "reports": reports, "counts": {name: len(rows) for name, rows in groups.items()},
              "remaining": ["exact_current_output_rescan_confirmation"],
              "boundaries": {"semantic_correctness_proven": False,
                             "generated_outputs_audited": False,
                             "delivery_approved": False, "worktree_audit_closed": False,
                             "release_claimed": False, "week6_closed": False}}
    write(out / "report.json", result)
    require(source_snapshot.capture(root) == current, "source changed during output review")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(produce(args.observation, args.policy, args.out), indent=2, sort_keys=True))
    except (Exception, KeyboardInterrupt) as error:
        print("week6 output review rejected: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
