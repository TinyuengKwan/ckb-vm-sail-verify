#!/usr/bin/env python3
"""Materialize the deterministic source portion of the Week6 review bundle.

The tracked policy names every permitted HEAD delta. The command captures the
complete current source identity and emits a byte-bound source review accepted
by the existing validator. It does not infer semantic approval, review
generated outputs, or create the separate profile-A maintainer approval.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import release_worktree_source as source_review
import release_worktree_evidence as worktree
import source_snapshot


ROOT = Path(__file__).resolve().parents[1]
OID = re.compile(r"[0-9a-f]{40}")
POLICY_BOUNDARIES = {
    "semantic_approval_claimed", "delivery_approval_claimed", "generated_outputs_audited",
    "clean_room_claimed", "release_claimed", "week6_closed",
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def regular(root, name):
    source_snapshot.safe(name)
    root, path = Path(root).resolve(), Path(root, name).absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            "missing/linked review evidence: " + name)
    current = root
    for part in Path(name).parts:
        current /= part
        require(not current.is_symlink(), "linked review evidence: " + name)
    return path


def read(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def reference(root, path):
    path = Path(path).absolute()
    require(path.is_relative_to(Path(root).resolve()), "review reference outside source root")
    return {"path": path.relative_to(Path(root).resolve()).as_posix(), "sha256": sha(path)}


def policy(path, root):
    root = Path(root).resolve()
    path = Path(path)
    path = path if path.is_absolute() else root / path
    require(path.absolute().is_relative_to(root), "review policy outside source root")
    path = regular(root, path.absolute().relative_to(root).as_posix())
    value = read(path)
    require(type(value) is dict and set(value) == {
        "schema_version", "kind", "reviewed_by", "require_root_repository_clean",
        "allowed_source_changes", "output_review", "boundaries",
    }, "review policy fields")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1 and
            value["kind"] == "week6-source-review-policy-v1" and
            value["require_root_repository_clean"] is True,
            "review policy identity/clean-root requirement")
    require(type(value["reviewed_by"]) is str and value["reviewed_by"].strip(),
            "review policy reviewer record")
    require(type(value["boundaries"]) is dict and set(value["boundaries"]) == POLICY_BOUNDARIES and
            all(item is False for item in value["boundaries"].values()),
            "review policy assurance upgrade")
    changes = value["allowed_source_changes"]
    require(type(changes) is dict and set(changes) == set(source_snapshot.REPOS),
            "review policy repository inventory")
    for repo, rows in changes.items():
        require(type(rows) is dict, "review policy change inventory: " + repo)
        for name, row in rows.items():
            source_snapshot.safe(name)
            require(type(row) is dict and set(row) == {
                "operation", "category", "rationale", "evidence",
            }, "review policy change fields: " + repo + "/" + name)
            require(row["operation"] in {"added", "modified", "deleted"} and
                    row["category"] in source_review.KINDS and
                    type(row["rationale"]) is str and row["rationale"].strip() and
                    type(row["evidence"]) is list and row["evidence"] and
                    len(row["evidence"]) == len(set(row["evidence"])),
                    "invalid review policy change: " + repo + "/" + name)
            for evidence in row["evidence"]:
                require(type(evidence) is str, "invalid review evidence path")
                regular(root, evidence)
    output = value["output_review"]
    require(type(output) is dict and set(output) == {
        "allowed_root_prefixes", "registry_marker", "build_markers"
    } and type(output["allowed_root_prefixes"]) is list and output["allowed_root_prefixes"] and
            len(output["allowed_root_prefixes"]) == len(set(output["allowed_root_prefixes"])) and
            all(type(item) is str and item.startswith("artifacts/boundary-check/") and item.endswith("-")
                for item in output["allowed_root_prefixes"]) and
            type(output["registry_marker"]) is str and output["registry_marker"] and
            type(output["build_markers"]) is list and output["build_markers"] and
            len(output["build_markers"]) == len(set(output["build_markers"])) and
            all(type(item) is str and item for item in output["build_markers"]),
            "invalid output review policy")
    return value, path


def new_output(path, root):
    root, path = Path(root).resolve(), Path(path).absolute()
    parent = root / "artifacts/boundary-check"
    require(path.parent == parent and path.name.startswith("week6-review-") and
            path.name != "week6-review-" and parent.is_dir() and not parent.is_symlink() and
            not path.exists() and not path.is_symlink(), "new Week6 review output required")
    path.mkdir()
    return path


def materialize(candidate, policy_path, out, root=ROOT):
    root = Path(root).resolve()
    require(type(candidate) is str and OID.fullmatch(candidate), "candidate must be a full Git commit")
    rules, policy_file = policy(policy_path, root)
    before = source_snapshot.capture(root)
    require(before["repositories"]["."]["head"] == candidate, "candidate differs from current root HEAD")
    require(before["repositories"]["."]["changes_from_head"] == {},
            "final candidate root repository is not clean")
    expected = rules["allowed_source_changes"]
    for repo in source_snapshot.REPOS:
        actual = before["repositories"][repo]["changes_from_head"]
        require(set(actual) == set(expected[repo]), "unlisted/missing source change: " + repo)
        for name, change in actual.items():
            require(change["operation"] == expected[repo][name]["operation"],
                    "source change operation differs: " + repo + "/" + name)

    out = new_output(out, root)
    snapshot_path = out / "source-snapshot.json"
    write(snapshot_path, before)
    reviews = {}
    for repo in source_snapshot.REPOS:
        reviews[repo] = {}
        for name, change in before["repositories"][repo]["changes_from_head"].items():
            rule = expected[repo][name]
            reviews[repo][name] = {
                "change_sha256": source_snapshot.digest(source_snapshot.canonical(change)),
                "category": rule["category"], "rationale": rule["rationale"],
                "reviewed_by": rules["reviewed_by"],
                "evidence": [reference(root, regular(root, item)) for item in rule["evidence"]],
            }
    report = {
        "schema_version": 1, "kind": "worktree-source-review-v1", "candidate": candidate,
        "snapshot": reference(root, snapshot_path), "reviews": reviews,
        "boundaries": {name: False for name in source_review.BOUNDARIES},
    }
    review_path = out / "source-review.json"
    write(review_path, report)
    checked = source_review.check(review_path, candidate, root=root)
    require(source_snapshot.capture(root) == before, "source changed during review materialization")
    result = {
        "schema_version": 1, "kind": "week6-review-materialization-v1",
        "status": "source_review_materialized_outputs_and_delivery_approval_pending",
        "candidate": candidate, "source_snapshot_sha256": before["snapshot_sha256"],
        "policy": reference(root, policy_file), "source_review": reference(root, review_path),
        "validated": checked,
        "remaining": ["fresh_formal_output_review", "explicit_profile_A_delivery_approval"],
        "boundaries": {"generated_outputs_audited": False, "delivery_approval_claimed": False,
                       "worktree_audit_closed": False, "release_claimed": False,
                       "week6_closed": False},
    }
    write(out / "report.json", result)
    return result


def linked_reference(root, row, label):
    require(type(row) is dict and set(row) == {"path", "sha256"}, label + " reference fields")
    require(type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
            label + " reference hash")
    path = regular(root, row["path"])
    require(sha(path) == row["sha256"], label + " reference differs")
    return dict(row)


def connect(candidate, inputs_path, out, root=ROOT):
    """Build a v4 envelope from independently produced, hash-bound records."""
    root = Path(root).resolve()
    require(type(candidate) is str and OID.fullmatch(candidate), "candidate must be a full Git commit")
    inputs_path = Path(inputs_path)
    inputs_path = inputs_path if inputs_path.is_absolute() else root / inputs_path
    inputs = read(regular(root, inputs_path.absolute().relative_to(root).as_posix()))
    require(type(inputs) is dict and set(inputs) == {
        "schema_version", "kind", "candidate", "source_review", "generation",
        "source_increment", "output_identity", "approval",
    }, "worktree envelope input fields")
    require(type(inputs["schema_version"]) is int and inputs["schema_version"] == 1 and
            inputs["kind"] == "week6-worktree-envelope-inputs-v1" and
            inputs["candidate"] == candidate, "worktree envelope input identity")
    source = linked_reference(root, inputs["source_review"], "source review")
    require(type(inputs["generation"]) is dict and set(inputs["generation"]) == {"producer", "review"},
            "generation input fields")
    generation = {name: linked_reference(root, inputs["generation"][name], "generation " + name)
                  for name in ["producer", "review"]}
    increment = None if inputs["source_increment"] is None else linked_reference(
        root, inputs["source_increment"], "source increment")
    require(type(inputs["output_identity"]) is dict and set(inputs["output_identity"]) == {
        "observation", "registry_review", "build_review", "record_review", "confirmation",
    }, "output identity input fields")
    output_identity = {name: linked_reference(root, inputs["output_identity"][name], "output " + name)
                       for name in ["observation", "registry_review", "build_review",
                                    "record_review", "confirmation"]}
    approval = linked_reference(root, inputs["approval"], "profile-A approval")
    out = new_output(out, root)
    envelope = {
        "schema_version": 4, "kind": "worktree-record-review-v4", "candidate": candidate,
        "source_review": source, "generation": generation, "source_increment": increment,
        "output_identity": output_identity, "approval": approval,
        "boundaries": {name: False for name in worktree.FLAGS},
    }
    envelope_path = out / "worktree-envelope.json"
    write(envelope_path, envelope)
    checked = worktree.check(envelope_path, candidate, root=root)
    require(checked.get("delivery_approval_verified") is True and
            checked.get("remaining") == [worktree.EXECUTION_LINKAGE] and
            checked.get("worktree_audit_closed") is False,
            "v4 envelope did not retain exactly the formal execution linkage obligation")
    result = {
        "schema_version": 1, "kind": "week6-worktree-envelope-materialization-v1",
        "status": "v4_envelope_validated_pending_aggregate_formal_execution_linkage",
        "candidate": candidate, "inputs": reference(root, Path(inputs_path).absolute()),
        "envelope": reference(root, envelope_path), "validated": checked,
        "remaining": [worktree.EXECUTION_LINKAGE],
        "boundaries": {"formal_execution_linked": False, "worktree_audit_closed": False,
                       "release_claimed": False, "week6_closed": False},
    }
    write(out / "report.json", result)
    return result


def connect_preapproval(candidate, inputs_path, out, root=ROOT):
    """Build the validated v3 envelope that precedes human profile-A approval."""
    root = Path(root).resolve()
    require(type(candidate) is str and OID.fullmatch(candidate), "candidate must be a full Git commit")
    inputs_path = Path(inputs_path)
    inputs_path = inputs_path if inputs_path.is_absolute() else root / inputs_path
    inputs = read(regular(root, inputs_path.absolute().relative_to(root).as_posix()))
    require(type(inputs) is dict and set(inputs) == {
        "schema_version", "kind", "candidate", "source_review", "generation",
        "source_increment", "output_identity",
    }, "worktree preapproval input fields")
    require(type(inputs["schema_version"]) is int and inputs["schema_version"] == 1 and
            inputs["kind"] == "week6-worktree-preapproval-inputs-v1" and
            inputs["candidate"] == candidate, "worktree preapproval input identity")
    source = linked_reference(root, inputs["source_review"], "source review")
    require(type(inputs["generation"]) is dict and set(inputs["generation"]) == {"producer", "review"},
            "generation input fields")
    generation = {name: linked_reference(root, inputs["generation"][name], "generation " + name)
                  for name in ["producer", "review"]}
    increment = None if inputs["source_increment"] is None else linked_reference(
        root, inputs["source_increment"], "source increment")
    require(type(inputs["output_identity"]) is dict and set(inputs["output_identity"]) == {
        "observation", "registry_review", "build_review", "record_review", "confirmation",
    }, "output identity input fields")
    output_identity = {name: linked_reference(root, inputs["output_identity"][name], "output " + name)
                       for name in ["observation", "registry_review", "build_review",
                                    "record_review", "confirmation"]}
    out = new_output(out, root)
    envelope = {
        "schema_version": 3, "kind": "worktree-record-review-v3", "candidate": candidate,
        "source_review": source, "generation": generation, "source_increment": increment,
        "output_identity": output_identity,
        "boundaries": {name: False for name in worktree.FLAGS},
    }
    envelope_path = out / "worktree-envelope.json"
    write(envelope_path, envelope)
    checked = worktree.check(envelope_path, candidate, root=root)
    expected = ["final_delivery_scope_and_semantic_approval", worktree.EXECUTION_LINKAGE]
    require(checked.get("delivery_approval_verified") is False and
            checked.get("remaining") == expected and
            checked.get("worktree_audit_closed") is False,
            "v3 envelope did not retain exactly approval and formal execution linkage")
    result = {
        "schema_version": 1, "kind": "week6-worktree-preapproval-materialization-v1",
        "status": "v3_envelope_validated_pending_profile_A_approval_and_formal_execution_linkage",
        "candidate": candidate, "inputs": reference(root, Path(inputs_path).absolute()),
        "envelope": reference(root, envelope_path), "validated": checked,
        "remaining": expected,
        "boundaries": {"delivery_approval_claimed": False, "formal_execution_linked": False,
                       "worktree_audit_closed": False, "release_claimed": False,
                       "week6_closed": False},
    }
    write(out / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--policy", type=Path)
    group.add_argument("--envelope-inputs", type=Path)
    group.add_argument("--preapproval-inputs", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.policy:
            result = materialize(args.candidate, args.policy, args.out)
        elif args.preapproval_inputs:
            result = connect_preapproval(args.candidate, args.preapproval_inputs, args.out)
        else:
            result = connect(args.candidate, args.envelope_inputs, args.out)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as error:
        print("week6 review materialization rejected: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
