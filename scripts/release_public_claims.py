#!/usr/bin/env python3
"""Validate a complete, source-bound review of project public claims.

This component checks every Markdown file in the current project source
snapshot, its review classification, claim-paragraph identity, local links and
the exact evidence behind the release-level claim classes. Runtime evidence
references live in an ignored execution manifest so a tracked review manifest
does not hash a worktree report that recursively includes itself. It does not query
remote services, rerun kernels, approve a release, or replace the independent
third-party requirement.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.parse

import release_demo as demo
import release_evidence as common
import release_mismatch_evidence as mismatches
import release_rust_tests as rust_tests
import release_worktree_evidence as worktree
import source_snapshot as source


ROOT = common.ROOT
CLASSES = {
    "current_assurance",
    "technical_boundary",
    "normative_plan",
    "historical_record",
    "format_or_navigation",
}
CLAIMS = {
    "runtime_scope",
    "lean_scope",
    "rocq_no_go",
    "rust_test_scope",
    "mismatch_scope",
    "maintainer_demo_scope",
    "source_output_identity",
    "release_incomplete",
    "historical_scope",
    "normative_only",
}
COMPONENTS = {
    "runtime",
    "lean",
    "rocq",
    "rust_tests",
    "mismatches",
    "maintainer_demo",
    "worktree_audit",
    "aggregate",
}
BOUNDARIES = {
    "release_claimed",
    "week6_closed",
    "clean_room_claimed",
    "ci_download_verified",
    "release_package_built",
    "third_party_reproduced",
    "fresh_execution_claimed",
    "remote_state_queried",
}
CLAIM_PATTERN = re.compile(
    r"(?:通过|完成|验证|证明|一致|匹配|相同|成功|退出\s*[012]|"
    r"PASS|passed|verified|proved|matches|identical|successful|exit(?:ed)?\s*[012])",
    re.IGNORECASE,
)
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
STALE_EXACT = {
    "生产 wrapper 方法仍是 axiom，其五个委托合同虽已编译，尚无实例/连接证明",
    "共同 Lean 4.31.0 双侧 import 工程；state relation 与精化定理待实现",
    "提取不需要修改 `deps/ckb-vm`，因此本轮不需要上游 patch/PR",
    "当前 submodule 固定为 sail-riscv `27224ccb`",
    "`audit-release` 已有 [当前 v10 readiness 清单]",
}


def require(value, message):
    common.require(value, message)


def same(left, right):
    return common.same(left, right)


def sha(path):
    return common.sha(Path(path))


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fields(value, expected, message):
    require(type(value) is dict and set(value) == set(expected), message)


def text(value, message):
    require(isinstance(value, str) and value.strip(), message)


def markdown_files(snapshot):
    files = snapshot["repositories"]["."]["files"]
    return sorted(name for name in files if name.lower().endswith((".md", ".markdown")))


def claim_paragraphs(document):
    without_code = re.sub(r"```.*?```", "", document, flags=re.DOTALL)
    return [
        re.sub(r"\s+", " ", paragraph.strip())
        for paragraph in re.split(r"\n\s*\n", without_code)
        if paragraph.strip() and CLAIM_PATTERN.search(paragraph)
    ]


def paragraph_digest(paragraphs):
    payload = json.dumps(paragraphs, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def safe_reference(root, row, label):
    fields(row, {"path", "sha256"}, "invalid " + label + " reference")
    return common.linked(root, row["path"], row["sha256"])


EVIDENCE_ROOT = "artifacts"


def local_links(root, name, body, source_files):
    """Classify one document's links deterministically across host and clean-room checkouts.

    Links to files in the source snapshot must resolve.  Links into the ignored
    evidence root that are not in the snapshot are evidence references: they are
    syntactically checked and counted, but their existence is not required, so a
    fresh checkout (which never contains local evidence directories) and the
    producing host classify every link identically.  Everything else must exist.
    """
    checked = []
    external = []
    evidence = []
    for raw in LINK_PATTERN.findall(body):
        target = raw.strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme or target.startswith("#"):
            external.append(target)
            continue
        decoded = urllib.parse.unquote(parsed.path)
        require(decoded and not Path(decoded).is_absolute(), "absolute/empty public link: " + name)
        resolved = ((root / name).parent / decoded).resolve()
        require(resolved.is_relative_to(root.resolve()), "escaping public link: " + name + " -> " + target)
        relative = resolved.relative_to(root.resolve()).as_posix()
        if relative not in source_files and relative.split("/", 1)[0] == EVIDENCE_ROOT:
            evidence.append(target)
            continue
        require(resolved.exists(), "missing public link: " + name + " -> " + target)
        checked.append(target)
    return checked, external, evidence


def validate_documents(root, manifest, snapshot):
    documents = manifest["documents"]
    expected = markdown_files(snapshot)
    require(sorted(documents) == expected, "public Markdown inventory is incomplete or has extras")
    counts = {name: 0 for name in CLASSES}
    claim_paragraph_count = 0
    links = 0
    external_links = 0
    evidence_links = 0
    source_files = set(snapshot["repositories"]["."]["files"])
    for name in expected:
        row = documents[name]
        fields(row, {"sha256", "classification", "claims", "claim_paragraphs",
                     "claim_paragraphs_sha256", "review"}, "invalid public document review: " + name)
        path = root / name
        require(sha(path) == row["sha256"], "public document changed: " + name)
        require(row["classification"] in CLASSES, "unknown public document class: " + name)
        require(type(row["claims"]) is list and len(row["claims"]) == len(set(row["claims"])) and
                set(row["claims"]) <= CLAIMS, "invalid document claim classes: " + name)
        if row["classification"] == "current_assurance":
            require(row["claims"] and set(row["claims"]) != {"historical_scope"},
                    "current assurance document lacks current claim mapping: " + name)
        if row["classification"] == "normative_plan":
            require(row["claims"] == ["normative_only"], "plan must not be accepted as execution evidence: " + name)
        text(row["review"], "missing document review rationale: " + name)
        body = path.read_text()
        paragraphs = claim_paragraphs(body)
        require(same(row["claim_paragraphs"], len(paragraphs)) and
                row["claim_paragraphs_sha256"] == paragraph_digest(paragraphs),
                "claim paragraph inventory changed: " + name)
        checked, external, evidence = local_links(root, name, body, source_files)
        links += len(checked)
        external_links += len(external)
        evidence_links += len(evidence)
        counts[row["classification"]] += 1
        claim_paragraph_count += len(paragraphs)
    combined = "\n".join((root / name).read_text() for name in expected)
    for phrase in STALE_EXACT:
        require(phrase not in combined, "known stale public statement remains: " + phrase)
    return {
        "documents": len(expected),
        "class_counts": counts,
        "claim_paragraphs": claim_paragraph_count,
        "local_links_checked": links,
        "external_links_not_queried": external_links,
        # Evidence directories are ignored by Git and never ship with the source;
        # these references are honest pointers to local records, not verified links.
        "evidence_links_not_shipped_with_source": evidence_links,
    }


def validate_components(root, references, candidate):
    fields(references, COMPONENTS, "public claim evidence component inventory")
    paths = {name: safe_reference(root, row, name) for name, row in references.items()}
    results = {
        "runtime": common.check_runtime(paths["runtime"]),
        "lean": common.check_lean(paths["lean"]),
        "rocq": common.check_rocq(paths["rocq"]),
        "rust_tests": rust_tests.check(paths["rust_tests"]),
        "mismatches": mismatches.check_inventory(paths["mismatches"]),
        "maintainer_demo": demo.check(paths["maintainer_demo"]),
    }
    checked_worktree = worktree.check(paths["worktree_audit"], candidate, root=root)
    results["worktree_audit"] = worktree.connect_formal_execution(checked_worktree, {
        name: {"status": "verified_existing_evidence", "reference": references[name]}
        for name in ["lean", "rocq"]
    }, root=root)
    aggregate = common.read(paths["aggregate"])
    require(aggregate.get("status") == "incomplete" and aggregate.get("release_claimed") is False and
            aggregate.get("week6_closed") is False, "public review linked a successful/invalid aggregate")
    worktree_row = aggregate["checks"]["worktree_audit"]
    expected_outstanding = {"clean_room", "ci_download", "release_package", "third_party", "public_claims"}
    if worktree_row["status"] == "incomplete":
        expected_outstanding.add("worktree_audit")
        require(results["worktree_audit"]["remaining"] == ["final_delivery_scope_and_semantic_approval"] and
                results["worktree_audit"]["worktree_audit_closed"] is False,
                "partial worktree public boundary changed")
    elif worktree_row["status"] == "verified_existing_evidence":
        require(results["worktree_audit"]["remaining"] == [] and
                results["worktree_audit"]["worktree_audit_closed"] is True and
                results["worktree_audit"]["delivery_approval_verified"] is True,
                "approved worktree public boundary changed")
    else:
        raise RuntimeError("public review worktree status changed")
    require(type(aggregate.get("outstanding")) is list and
            len(aggregate["outstanding"]) == len(expected_outstanding) and
            set(aggregate["outstanding"]) == expected_outstanding and
            aggregate["checks"]["public_claims"]["status"] == "missing",
            "public review aggregate boundary changed")
    for name in ["runtime", "lean", "rocq", "rust_tests", "mismatches", "maintainer_demo"]:
        require(aggregate["checks"][name]["status"] == "verified_existing_evidence" and
                aggregate["checks"][name]["reference"] == references[name],
                "aggregate/component evidence mismatch: " + name)
    require(worktree_row["reference"] == references["worktree_audit"],
            "aggregate/worktree evidence mismatch")
    require(worktree_row["details"] == results["worktree_audit"],
            "aggregate/worktree connected details mismatch")
    require(same(results["runtime"]["cases"], 33) and
            same(results["runtime"]["mutations"]["applied"], 194) and
            same(results["runtime"]["replays"], 33), "runtime public claim counts")
    require(same(results["lean"]["main_stages"], 28) and same(results["lean"]["tests"], 287) and
            same(results["lean"]["public_theorems"], 68), "Lean public claim counts")
    require(same(results["rocq"]["stages"], 11) and
            results["rocq"]["extra_proof_coverage"] is False, "Rocq public claim counts")
    require(same(results["rust_tests"]["tests_passed"], 78) and
            same(results["rust_tests"]["engine_tests"], 10), "Rust test public claim counts")
    results["aggregate"] = {
        "status": aggregate["status"],
        "outstanding": aggregate["outstanding"],
        "release_claimed": False,
        "week6_closed": False,
    }
    for name, path in paths.items():
        require(sha(path) == references[name]["sha256"], "public claim evidence changed during review: " + name)
    return results


def validate_manifest(path, root=None):
    root = ROOT if root is None else Path(root)
    path = Path(path)
    initial = sha(path)
    manifest = common.read(path)
    fields(manifest, {"schema_version", "kind", "candidate", "reviewer", "documents", "claim_classes",
                      "required_evidence_components", "forbidden_overclaims", "review_complete", "boundaries"},
           "public claim review manifest schema")
    require(same(manifest["schema_version"], 1) and manifest["kind"] == "public-claims-review-v1",
            "unknown public claim review manifest")
    text(manifest["candidate"], "missing public claim candidate")
    fields(manifest["reviewer"], {"name", "kind", "independent_third_party"}, "public claim reviewer")
    text(manifest["reviewer"]["name"], "missing public claim reviewer")
    require(manifest["reviewer"]["kind"] == "assistant_semantic_review" and
            manifest["reviewer"]["independent_third_party"] is False,
            "public claim review must not impersonate independent third party")
    require(type(manifest["claim_classes"]) is dict and set(manifest["claim_classes"]) == CLAIMS,
            "public claim class inventory")
    require(type(manifest["required_evidence_components"]) is list and
            set(manifest["required_evidence_components"]) == COMPONENTS and
            len(manifest["required_evidence_components"]) == len(COMPONENTS),
            "public claim required evidence component inventory")
    for name, row in manifest["claim_classes"].items():
        fields(row, {"summary", "limitations", "evidence_components"}, "invalid claim class: " + name)
        text(row["summary"], "missing claim summary: " + name)
        require(type(row["limitations"]) is list and row["limitations"] and
                all(isinstance(item, str) and item.strip() for item in row["limitations"]),
                "missing claim limitations: " + name)
        require(type(row["evidence_components"]) is list and
                set(row["evidence_components"]) <= COMPONENTS,
                "invalid claim evidence mapping: " + name)
    require(type(manifest["forbidden_overclaims"]) is list and manifest["forbidden_overclaims"] and
            all(isinstance(item, str) and item.strip() for item in manifest["forbidden_overclaims"]),
            "forbidden overclaim inventory")
    require(manifest["review_complete"] is True, "public claim review not marked complete")
    fields(manifest["boundaries"], BOUNDARIES, "public claim review boundaries")
    require(all(value is False for value in manifest["boundaries"].values()),
            "public claim review upgraded another release boundary")
    snapshot_before = source.capture(root)
    documents = validate_documents(root, manifest, snapshot_before)
    combined = "\n".join((root / name).read_text() for name in markdown_files(snapshot_before))
    for phrase in manifest["forbidden_overclaims"]:
        require(phrase not in combined, "forbidden public overclaim: " + phrase)
    snapshot_after = source.capture(root)
    require(snapshot_before == snapshot_after, "source changed during public claim validation")
    require(sha(path) == initial, "public claim manifest changed during validation")
    return {
        "scope": "all_project_markdown_in_current_source_snapshot_and_release_claim_classes",
        "candidate": manifest["candidate"],
        "source_snapshot_sha256": snapshot_before["snapshot_sha256"],
        "documents": documents,
        "reviewer": manifest["reviewer"],
        "public_claims_slot_closed": True,
        "release_claimed": False,
        "week6_closed": False,
        "fresh_execution_claimed": False,
        "remote_state_queried": False,
        "third_party_reproduced": False,
    }


def validate_evidence_manifest(path, review_path, candidate, root=None):
    root = ROOT if root is None else Path(root)
    path = Path(path)
    review_path = Path(review_path)
    initial = sha(path)
    value = common.read(path)
    fields(value, {"schema_version", "kind", "candidate", "review_manifest", "evidence", "boundaries"},
           "public claim execution evidence manifest schema")
    require(same(value["schema_version"], 1) and value["kind"] == "public-claims-execution-manifest-v1",
            "unknown public claim execution evidence manifest")
    require(value["candidate"] == candidate, "public claim execution candidate differs")
    linked_review = safe_reference(root, value["review_manifest"], "public claim review manifest")
    require(linked_review.resolve() == review_path.resolve(), "execution manifest links a different review manifest")
    fields(value["boundaries"], BOUNDARIES, "public claim execution boundaries")
    require(all(item is False for item in value["boundaries"].values()),
            "public claim execution manifest upgraded another release boundary")
    components = validate_components(root, value["evidence"], candidate)
    require(sha(path) == initial and sha(review_path) == value["review_manifest"]["sha256"],
            "public claim execution inputs changed during validation")
    return components


def validate(review_path, evidence_path, root=None, candidate=None):
    root = ROOT if root is None else Path(root)
    before = source.capture(root)
    review = validate_manifest(review_path, root=root)
    execution = common.read(evidence_path)
    execution_candidate = execution.get("candidate") if type(execution) is dict else None
    if candidate is not None:
        require(execution_candidate == candidate, "public claim report belongs to another release candidate")
    else:
        candidate = execution_candidate
    components = validate_evidence_manifest(evidence_path, review_path, candidate, root=root)
    after = source.capture(root)
    require(before == after and before["snapshot_sha256"] == review["source_snapshot_sha256"],
            "source changed across complete public claim validation")
    # The tracked review label is not a Git-commit assertion: embedding the
    # containing commit in that tracked file would be self-referential. The
    # execution manifest supplies the release candidate identity instead.
    return {**review, "candidate": candidate, "components": components}


def check(path, root=None, candidate=None):
    root = ROOT if root is None else Path(root)
    path = Path(path)
    initial = sha(path)
    report = common.read(path)
    fields(report, {"schema_version", "kind", "status", "started_at", "finished_at", "manifest",
                    "evidence_manifest",
                    "result", "release_claimed", "week6_closed", "fresh_execution_claimed",
                    "remote_state_queried", "third_party_reproduced"},
           "public claim evidence report schema")
    require(same(report["schema_version"], 1) and report["kind"] == "public-claims-evidence-v1" and
            report["status"] == "passed", "public claim evidence incomplete")
    for name in ["release_claimed", "week6_closed", "fresh_execution_claimed", "remote_state_queried",
                 "third_party_reproduced"]:
        require(report[name] is False, "public claim evidence assurance upgrade: " + name)
    manifest_path = safe_reference(root, report["manifest"], "public claim manifest")
    evidence_path = safe_reference(root, report["evidence_manifest"], "public claim execution manifest")
    result = validate(manifest_path, evidence_path, root=root, candidate=candidate)
    require(report["result"] == result and result["public_claims_slot_closed"] is True,
            "public claim report/result mismatch")
    require(sha(path) == initial, "public claim report changed during validation")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--evidence-manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1,
        "kind": "public-claims-evidence-v1",
        "status": "running",
        "started_at": stamp(),
        "release_claimed": False,
        "week6_closed": False,
        "fresh_execution_claimed": False,
        "remote_state_queried": False,
        "third_party_reproduced": False,
    }
    # The reviewed documentation may link to this exact report.  Materialize a
    # truthful running record before checking links; failure still overwrites it
    # with a terminal failed record in this new directory.
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    code = 1
    try:
        manifest_path = args.manifest.resolve()
        evidence_path = args.evidence_manifest.resolve()
        require(manifest_path.is_relative_to(ROOT) and manifest_path.is_file(), "manifest outside/missing")
        require(evidence_path.is_relative_to(ROOT) and evidence_path.is_file(), "evidence manifest outside/missing")
        relative = manifest_path.relative_to(ROOT).as_posix()
        report["manifest"] = {"path": relative, "sha256": sha(manifest_path)}
        report["evidence_manifest"] = {
            "path": evidence_path.relative_to(ROOT).as_posix(),
            "sha256": sha(evidence_path),
        }
        report["result"] = validate(manifest_path, evidence_path)
        report["status"] = "passed"
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["error"] = str(error)
        report["error_type"] = type(error).__name__
    report["finished_at"] = stamp()
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "report": str(out / "report.json")}))
    return code


if __name__ == "__main__":
    sys.exit(main())
