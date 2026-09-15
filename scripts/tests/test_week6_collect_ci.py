#!/usr/bin/env python3
import gzip
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("week6_collect_ci", HERE.parent / "week6_collect_ci.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CANDIDATE = "a" * 40
RUN_ID = 123


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.policy = MODULE.external.load_policy(MODULE.ROOT)
        self.run = {
            "id": RUN_ID, "head_sha": CANDIDATE, "event": "workflow_dispatch",
            "conclusion": "success", "path": ".github/workflows/week6-release.yml",
            "run_attempt": 1, "html_url": "https://example.invalid/run/123",
        }
        self.jobs = {"jobs": [
            {"id": i + 1, "name": name, "conclusion": "success"}
            for i, name in enumerate(self.policy["ci_download"]["required_jobs"])
        ]}
        self.artifacts = {"artifacts": [{
            "id": 77,
            "name": self.policy["ci_download"]["artifact_name_prefix"] + CANDIDATE,
            "expired": False,
        }]}

    def select(self):
        return MODULE.select_remote(self.run, self.jobs, self.artifacts,
                                    self.policy, RUN_ID, CANDIDATE)

    def test_selects_exact_run_jobs_and_artifact(self):
        jobs, artifact = self.select()
        self.assertEqual(list(jobs), self.policy["ci_download"]["required_jobs"])
        self.assertEqual(artifact["id"], 77)

    def test_rejects_wrong_workflow(self):
        self.run["path"] = ".github/workflows/ci.yml"
        with self.assertRaisesRegex(RuntimeError, "remote run"):
            self.select()

    def test_rejects_duplicate_or_extra_job(self):
        self.jobs["jobs"][-1] = dict(self.jobs["jobs"][0])
        with self.assertRaisesRegex(RuntimeError, "remote job"):
            self.select()

    def test_rejects_failed_job(self):
        self.jobs["jobs"][0]["conclusion"] = "failure"
        with self.assertRaisesRegex(RuntimeError, "remote job"):
            self.select()

    def test_rejects_expired_artifact(self):
        self.artifacts["artifacts"][0]["expired"] = True
        with self.assertRaisesRegex(RuntimeError, "artifact identity"):
            self.select()

    def test_unique_attestation_bundle(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            bundle = root / "sha256:test.jsonl"
            bundle.write_text("{}\n")
            self.assertEqual(MODULE.unique_bundle(root), bundle)
            (root / "second.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                MODULE.unique_bundle(root)

    def test_reads_one_archived_manifest(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "archive.tar.gz"
            data = json.dumps({"schema_version": 1}).encode()
            with path.open("xb") as raw:
                with gzip.GzipFile(filename="", mode="wb", mtime=0, fileobj=raw) as compressed:
                    with tarfile.open(fileobj=compressed, mode="w") as archive:
                        info = tarfile.TarInfo("MANIFEST.json")
                        info.size = len(data)
                        archive.addfile(info, io.BytesIO(data))
            self.assertEqual(MODULE.manifest_bytes(path), data)


if __name__ == "__main__":
    unittest.main()
