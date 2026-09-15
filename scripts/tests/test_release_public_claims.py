"""Fail-closed tests for the all-project public-claims evidence component."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_public_claims as claims


class PublicClaimsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="public-claims-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.doc = self.root / "README.md"
        self.target = self.root / "evidence.json"
        self.target.write_text("{}")
        self.doc.write_text("# Status\n\nThe bounded check passed; see [record](evidence.json).\n")
        self.snapshot = {
            "snapshot_sha256": "source-fixture",
            "repositories": {".": {"files": {"README.md": {}}}},
        }
        paragraphs = claims.claim_paragraphs(self.doc.read_text())
        self.manifest = {
            "schema_version": 1,
            "kind": "public-claims-review-v1",
            "candidate": "fixture-candidate",
            "reviewer": {
                "name": "Codex fixture",
                "kind": "assistant_semantic_review",
                "independent_third_party": False,
            },
            "documents": {
                "README.md": {
                    "sha256": claims.sha(self.doc),
                    "classification": "current_assurance",
                    "claims": ["release_incomplete"],
                    "claim_paragraphs": len(paragraphs),
                    "claim_paragraphs_sha256": claims.paragraph_digest(paragraphs),
                    "review": "Fixture scope and limitation reviewed.",
                }
            },
            "claim_classes": {
                name: {"summary": "Fixture " + name, "limitations": ["fixture only"],
                       "evidence_components": []}
                for name in claims.CLAIMS
            },
            "required_evidence_components": sorted(claims.COMPONENTS),
            "forbidden_overclaims": ["fixture forbidden assurance"],
            "review_complete": True,
            "boundaries": dict.fromkeys(claims.BOUNDARIES, False),
        }
        self.path = self.root / "manifest.json"
        self.write_manifest()

    def write_manifest(self):
        self.path.write_text(json.dumps(self.manifest))

    def validate(self):
        with patch.object(claims.source, "capture", return_value=copy.deepcopy(self.snapshot)):
            return claims.validate_manifest(self.path, root=self.root)

    def test_complete_fixture_passes_without_release_upgrade(self):
        result = self.validate()
        self.assertTrue(result["public_claims_slot_closed"])
        self.assertFalse(result["release_claimed"])
        self.assertFalse(result["third_party_reproduced"])
        self.assertEqual(result["documents"]["documents"], 1)
        self.assertEqual(result["documents"]["local_links_checked"], 1)

    def test_missing_or_extra_document_rejected(self):
        for documents in [{}, {**self.manifest["documents"], "extra.md": self.manifest["documents"]["README.md"]}]:
            candidate = copy.deepcopy(self.manifest)
            candidate["documents"] = documents
            self.path.write_text(json.dumps(candidate))
            with self.subTest(documents=list(documents)), self.assertRaisesRegex(RuntimeError, "inventory"):
                self.validate()

    def test_changed_document_and_claim_paragraph_rejected(self):
        self.doc.write_text(self.doc.read_text() + "Another verification passed.\n")
        with self.assertRaisesRegex(RuntimeError, "document changed"):
            self.validate()
        self.manifest["documents"]["README.md"]["sha256"] = claims.sha(self.doc)
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, "claim paragraph"):
            self.validate()

    def test_current_assurance_requires_claim_mapping(self):
        self.manifest["documents"]["README.md"]["claims"] = []
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, "lacks current"):
            self.validate()

    def test_normative_document_cannot_claim_execution(self):
        row = self.manifest["documents"]["README.md"]
        row["classification"] = "normative_plan"
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, "plan must not"):
            self.validate()

    def test_missing_local_link_rejected(self):
        self.target.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing public link"):
            self.validate()

    def rewrite(self, body):
        self.doc.write_text(body)
        paragraphs = claims.claim_paragraphs(body)
        row = self.manifest["documents"]["README.md"]
        row.update(sha256=claims.sha(self.doc), claim_paragraphs=len(paragraphs),
                   claim_paragraphs_sha256=claims.paragraph_digest(paragraphs))
        self.write_manifest()

    def test_evidence_root_links_are_counted_not_required_and_cannot_escape(self):
        # A fresh checkout never contains the ignored evidence root, so links into it are
        # classified identically whether or not the local record exists.
        self.rewrite("The check passed; see [record](artifacts/boundary-check/run-x/report.json) "
                     "and [source](evidence.json).\n")
        result = self.validate()
        self.assertEqual(result["documents"]["local_links_checked"], 1)
        self.assertEqual(result["documents"]["evidence_links_not_shipped_with_source"], 1)
        (self.root / "artifacts/boundary-check/run-x").mkdir(parents=True)
        (self.root / "artifacts/boundary-check/run-x/report.json").write_text("{}")
        self.assertEqual(self.validate()["documents"], result["documents"])
        # A file under the evidence root that ships with the source must still exist.
        self.snapshot["repositories"]["."]["files"]["artifacts/index.json"] = {}
        self.rewrite("The check passed; see [index](artifacts/index.json).\n")
        with self.assertRaisesRegex(RuntimeError, "missing public link"):
            self.validate()
        (self.root / "artifacts/index.json").write_text("{}\n")
        self.assertEqual(self.validate()["documents"]["local_links_checked"], 1)
        for body in ["The check passed: [bad](artifacts/../../outside.json).\n",
                     "The check passed: [bad](artifacts-not-root/x.json).\n"]:
            self.rewrite(body)
            with self.subTest(body=body), self.assertRaisesRegex(RuntimeError, "escaping|missing public link"):
                self.validate()

    def test_absolute_and_escaping_links_rejected(self):
        for body in ["The check passed: [bad](/tmp/x).\n", "The check passed: [bad](../x).\n"]:
            self.doc.write_text(body)
            paragraphs = claims.claim_paragraphs(body)
            row = self.manifest["documents"]["README.md"]
            row.update(sha256=claims.sha(self.doc), claim_paragraphs=len(paragraphs),
                       claim_paragraphs_sha256=claims.paragraph_digest(paragraphs))
            self.write_manifest()
            with self.subTest(body=body), self.assertRaisesRegex(RuntimeError, "public link"):
                self.validate()

    def test_external_link_is_recorded_not_queried(self):
        body = "The bounded check passed; see [remote](https://example.invalid/a).\n"
        self.doc.write_text(body)
        paragraphs = claims.claim_paragraphs(body)
        row = self.manifest["documents"]["README.md"]
        row.update(sha256=claims.sha(self.doc), claim_paragraphs=len(paragraphs),
                   claim_paragraphs_sha256=claims.paragraph_digest(paragraphs))
        self.write_manifest()
        result = self.validate()
        self.assertEqual(result["documents"]["external_links_not_queried"], 1)

    def test_known_stale_statement_rejected(self):
        phrase = next(iter(claims.STALE_EXACT))
        self.doc.write_text(phrase)
        paragraphs = claims.claim_paragraphs(phrase)
        row = self.manifest["documents"]["README.md"]
        row.update(sha256=claims.sha(self.doc), claim_paragraphs=len(paragraphs),
                   claim_paragraphs_sha256=claims.paragraph_digest(paragraphs))
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, "known stale"):
            self.validate()

    def test_forbidden_overclaim_rejected(self):
        body = "fixture forbidden assurance"
        self.doc.write_text(body)
        paragraphs = claims.claim_paragraphs(body)
        row = self.manifest["documents"]["README.md"]
        row.update(sha256=claims.sha(self.doc), claim_paragraphs=len(paragraphs),
                   claim_paragraphs_sha256=claims.paragraph_digest(paragraphs))
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, "forbidden"):
            self.validate()

    def test_false_review_or_true_boundary_rejected(self):
        for mutate, pattern in [
            (lambda value: value.update(review_complete=False), "not marked complete"),
            (lambda value: value["boundaries"].update(release_claimed=True), "upgraded"),
        ]:
            candidate = copy.deepcopy(self.manifest)
            mutate(candidate)
            self.path.write_text(json.dumps(candidate))
            with self.subTest(pattern=pattern), self.assertRaisesRegex(RuntimeError, pattern):
                self.validate()

    def test_reviewer_cannot_impersonate_third_party(self):
        self.manifest["reviewer"]["independent_third_party"] = True
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, "impersonate"):
            self.validate()

    def test_unknown_schema_fields_rejected(self):
        self.manifest["skip"] = True
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, "schema"):
            self.validate()

    def test_evidence_component_inventory_is_exact(self):
        evidence = {name: {"path": "evidence.json", "sha256": claims.sha(self.target)}
                    for name in claims.COMPONENTS}
        del evidence["lean"]
        execution = {
            "schema_version": 1,
            "kind": "public-claims-execution-manifest-v1",
            "candidate": self.manifest["candidate"],
            "review_manifest": {"path": "manifest.json", "sha256": claims.sha(self.path)},
            "evidence": evidence,
            "boundaries": dict.fromkeys(claims.BOUNDARIES, False),
        }
        execution_path = self.root / "execution.json"
        execution_path.write_text(json.dumps(execution))
        with self.assertRaisesRegex(RuntimeError, "component inventory"):
            claims.validate_evidence_manifest(execution_path, self.path,
                                              self.manifest["candidate"], root=self.root)

    def test_execution_candidate_must_match_expected_release_candidate(self):
        execution = {
            "schema_version": 1,
            "kind": "public-claims-execution-manifest-v1",
            "candidate": "different-candidate",
            "review_manifest": {"path": "manifest.json", "sha256": claims.sha(self.path)},
            "evidence": {name: {"path": "evidence.json", "sha256": claims.sha(self.target)}
                         for name in claims.COMPONENTS},
            "boundaries": dict.fromkeys(claims.BOUNDARIES, False),
        }
        execution_path = self.root / "execution.json"
        execution_path.write_text(json.dumps(execution))
        with patch.object(claims.source, "capture", return_value=copy.deepcopy(self.snapshot)), \
                self.assertRaisesRegex(RuntimeError, "another release candidate"):
            claims.validate(self.path, execution_path, root=self.root,
                            candidate="expected-candidate")

    def component_validation_fixture(self, connected_worktree, worktree_status, outstanding):
        paths = {}
        references = {}
        for name in claims.COMPONENTS:
            path = self.root / (name + ".json")
            path.write_text("{}")
            paths[name] = path
            references[name] = {"path": path.name, "sha256": claims.sha(path)}
        final = "final_delivery_scope_and_semantic_approval"
        linkage = "final_generation_kernel_and_rocq_linkage"
        raw_worktree = {"remaining": [final, linkage]}
        aggregate = {
            "status": "incomplete",
            "release_claimed": False,
            "week6_closed": False,
            "outstanding": outstanding,
            "checks": {
                name: {"status": "verified_existing_evidence", "reference": references[name]}
                for name in ["runtime", "lean", "rocq", "rust_tests", "mismatches", "maintainer_demo"]
            },
        }
        aggregate["checks"].update(
            worktree_audit={"status": worktree_status, "reference": references["worktree_audit"],
                            "details": connected_worktree},
            public_claims={"status": "missing"},
        )
        paths["aggregate"].write_text(json.dumps(aggregate))
        references["aggregate"]["sha256"] = claims.sha(paths["aggregate"])
        runtime = {"cases": 33, "mutations": {"applied": 194}, "replays": 33}
        lean = {"main_stages": 28, "tests": 287, "public_theorems": 68}
        rocq = {"stages": 11, "extra_proof_coverage": False}
        rust = {"tests_passed": 78, "engine_tests": 10}
        with patch.object(claims.common, "check_runtime", return_value=runtime), \
                patch.object(claims.common, "check_lean", return_value=lean), \
                patch.object(claims.common, "check_rocq", return_value=rocq), \
                patch.object(claims.rust_tests, "check", return_value=rust), \
                patch.object(claims.mismatches, "check_inventory", return_value={}), \
                patch.object(claims.demo, "check", return_value={}), \
                patch.object(claims.worktree, "check", return_value=raw_worktree), \
                patch.object(claims.worktree, "connect_formal_execution",
                             return_value=connected_worktree) as connect:
            result = claims.validate_components(self.root, references, self.manifest["candidate"])
        connect.assert_called_once()
        return result

    def test_component_validation_uses_connected_partial_worktree_details(self):
        final = "final_delivery_scope_and_semantic_approval"
        connected = {"remaining": [final], "worktree_audit_closed": False}
        result = self.component_validation_fixture(
            connected, "incomplete", ["public_claims", "clean_room", "worktree_audit",
                                      "ci_download", "release_package", "third_party"])
        self.assertEqual(result["worktree_audit"]["remaining"], [final])

    def test_component_validation_accepts_explicitly_approved_worktree(self):
        connected = {"remaining": [], "worktree_audit_closed": True,
                     "delivery_approval_verified": True}
        result = self.component_validation_fixture(
            connected, "verified_existing_evidence",
            ["public_claims", "clean_room", "ci_download", "release_package", "third_party"])
        self.assertTrue(result["worktree_audit"]["worktree_audit_closed"])

    def test_report_checker_recomputes_manifest_and_rejects_upgrade(self):
        result = {"public_claims_slot_closed": True, "release_claimed": False}
        evidence_path = self.root / "execution.json"
        evidence_path.write_text("{}")
        report = {
            "schema_version": 1,
            "kind": "public-claims-evidence-v1",
            "status": "passed",
            "started_at": "fixture",
            "finished_at": "fixture",
            "manifest": {"path": "manifest.json", "sha256": claims.sha(self.path)},
            "evidence_manifest": {"path": "execution.json", "sha256": claims.sha(evidence_path)},
            "result": result,
            "release_claimed": False,
            "week6_closed": False,
            "fresh_execution_claimed": False,
            "remote_state_queried": False,
            "third_party_reproduced": False,
        }
        report_path = self.root / "report.json"
        report_path.write_text(json.dumps(report))
        with patch.object(claims, "validate", return_value=result):
            self.assertEqual(claims.check(report_path, root=self.root), result)
        report["release_claimed"] = True
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(RuntimeError, "assurance upgrade"):
            claims.check(report_path, root=self.root)


if __name__ == "__main__":
    unittest.main()
