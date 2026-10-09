#!/usr/bin/env python3
"""Hermetic runtime-slot checks over synthetic artifacts; not execution evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime_evidence as gate


def fixture(count=30):
    environment = {"test_fixture_only": True}
    cases, rows, mutations = {}, [], []
    for i in range(count):
        family, word = [("ADD", 0x33), ("ADDI", 0x13), ("BEQ", 0x63)][i % 3]
        name = f"fixture-{i}"
        case = {"id": name, "description": "synthetic validator fixture", "family": family,
                "instructions": [word], "focus_step": 0, "seed": None}
        event = dict(order=0, instruction=word, pc_before=0x80000000, pc_after=0x80000004,
                     register_writes=[] if i == 0 else [{"index": 31, "value": 4}], memory=[], trap=False, halt=False)
        trace = {"events": [event], "end": {"kind": "injection_complete"}}
        result = {"passed": True, "classification": "match", "error": None, "comparison": {"compared_steps": 1, "mismatch": None}}
        cases[name] = {"schema_version": 3, "case": case, "environment": environment, "instructions_hex": [f"0x{word:08x}"],
                       "initial_state": {"pc": 0x80000000, "integer_registers": "x0..x31 = 0"}, **copy.deepcopy(result),
                       "ckb_trace": copy.deepcopy(trace), "sail_trace": copy.deepcopy(trace),
                       "sail_raw_packets": ["0" * 176] * 2, "replay": {"from_artifact": "not executed"}}
        rows.append({**copy.deepcopy(case), **copy.deepcopy(result), "instructions": 1, "artifact": "/original/" + name + ".json"})
        for kind, field in gate.MUTATIONS.items():
            skip = i == 0 and kind.startswith("register_")
            mutations.append({"case_id": name, "mutation": kind, "description": "synthetic", "expected_field": field,
                              "applied": not skip, "detected": not skip, "passed": not skip,
                              "skipped_because": "no writes" if skip else None, "located_field": None if skip else field,
                              "located_step": None if skip or kind == "termination" else 0})
    applied = sum(1 for m in mutations if m["applied"])
    summary = {"cases": count, "passed": True, "baseline_failures": [], "undetected": [], "mislocated": [],
               "applied": applied, "skipped": len(mutations) - applied, "reports": mutations,
               "coverage": [{"mutation": kind, "expected_field": field,
                             "applied": count - (1 if kind.startswith("register_") else 0),
                             "located": count - (1 if kind.startswith("register_") else 0), "example_case": "fixture-1"}
                            for kind, field in gate.MUTATIONS.items()]}
    report = {"schema_version": 3, "mode": "corpus", "seed": 1, "terminal_policy": "exact", "environment": environment,
              "results": rows, "mutations": summary, "summary": {"total": count, "failures": 0, "mutations_passed": True, "passed": True}}
    return report, cases, environment


class RuntimeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.report, self.cases, self.env = fixture()
        temporary = tempfile.TemporaryDirectory(prefix="runtime-evidence-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.artifacts = self.root / "original"
        self.artifacts.mkdir()
        self.corpus = self.root / "corpus-mutations.stdout"

    def write(self):
        self.corpus.write_text(json.dumps(self.report))
        for name, artifact in self.cases.items():
            (self.artifacts / (name + ".json")).write_text(json.dumps(artifact))
        (self.artifacts / "mutations.json").write_text(json.dumps({
            "schema_version": 3, "environment": self.env, "seed": self.report["seed"],
            "summary": self.report["mutations"], "replay": "fixture replay"}))

    def test_valid_fixture_passes_with_per_family_counts(self):
        self.write()
        result = gate.validate(self.corpus, self.artifacts, self.env)
        self.assertEqual(result["cases"], 30)
        self.assertEqual(result["families"], {"ADD": 10, "ADDI": 10, "BEQ": 10})
        self.assertEqual(result["mutations"]["applied"], 178)

    def test_family_floor_is_enforced(self):
        self.report, self.cases, self.env = fixture(29)
        self.write()
        with self.assertRaisesRegex(RuntimeError, "at least 10 cases per instruction family"):
            gate.validate(self.corpus, self.artifacts, self.env)

    def test_summary_cannot_hide_a_differing_trace(self):
        self.cases["fixture-3"]["sail_trace"]["events"][0]["pc_after"] += 4
        self.write()
        with self.assertRaisesRegex(RuntimeError, "engine traces differ"):
            gate.validate(self.corpus, self.artifacts, self.env)

    def test_mutation_claim_is_recomputed(self):
        for row in self.report["mutations"]["reports"]:
            if row["case_id"] == "fixture-5" and row["mutation"] == "pc_after":
                row["located_field"] = "trap"
        self.write()
        with self.assertRaisesRegex(RuntimeError, "disagrees with actual trace mutation"):
            gate.validate(self.corpus, self.artifacts, self.env)

    def test_extra_or_missing_artifact_fails(self):
        self.write()
        (self.artifacts / "extra.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "unexpected/missing artifact"):
            gate.validate(self.corpus, self.artifacts, self.env)

    def test_rust_test_log_parsing(self):
        ok = "".join(f"test tests::{name} ... ok\n" for name in sorted(gate.ENGINE_TESTS))
        ok += "test result: ok. 10 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.0s\n"
        self.assertEqual(gate.check_test_log(ok), 10)
        with self.assertRaisesRegex(RuntimeError, "failures"):
            gate.check_test_log(ok.replace("0 failed", "1 failed"))
        with self.assertRaisesRegex(RuntimeError, "mandatory real-engine tests"):
            gate.check_test_log("test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.1s\n")


if __name__ == "__main__":
    unittest.main()
