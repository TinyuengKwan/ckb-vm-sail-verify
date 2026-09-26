#!/usr/bin/env python3
import gzip
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("week6_collect_ci", HERE.parent / "week6_collect_ci.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
import week6_ci_archive as ARCHIVE
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


class CollectorIntegrationTests(unittest.TestCase):
    """Real producer, extractor, collector replay and final validator.

    Only GitHub transport/signature verification and source capture use local
    fixtures. These tests do not create or certify real CI evidence.
    """

    def setUp(self):
        CollectorTests.setUp(self)
        temp = tempfile.TemporaryDirectory(prefix="collector integration with spaces ")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.out = self.base / "collected"
        self.package = self.base / "package"
        self.package.mkdir()
        source = self.base / "source"
        clean = source / "artifacts/boundary-check/week6-clean-room"
        clean.mkdir(parents=True)
        self.snapshot = {"snapshot_sha256": "b" * 64, "repositories": {".": {"head": CANDIDATE}}}
        snap = clean / "source-snapshot.json"
        snap.write_text(json.dumps(self.snapshot))
        (clean / "report.json").write_text(json.dumps({
            "schema_version": 1, "kind": "clean-room-evidence-v1", "status": "passed",
            "candidate": CANDIDATE,
            "source_snapshot": {"path": snap.name, "sha256": ARCHIVE.sha(snap)}}))
        inputs = {}
        for name in ("diff", "sail", "config", "case"):
            inputs[name] = source / name
            inputs[name].write_text('{"fixture":"' + name + '"}\n')
        inputs["diff"].write_text(
            '#!/usr/bin/env python3\n'
            'import json, pathlib, sys\n'
            'args = sys.argv[1:]\n'
            'for flag in ("--sail-bin", "--sail-config", "--replay"):\n'
            '    path = pathlib.Path(args[args.index(flag) + 1])\n'
            '    if not path.is_file(): raise SystemExit("missing replay input")\n'
            'case = pathlib.Path(args[args.index("--replay") + 1])\n'
            'if json.loads(case.read_text()) != {"fixture":"case"}: raise SystemExit("wrong case")\n'
            'out = pathlib.Path(args[args.index("--artifact-dir") + 1])\n'
            'out.mkdir()\n'
            '(out / "fixture-argv.json").write_text(json.dumps(args))\n')
        inputs["diff"].chmod(0o755)
        ARCHIVE.create(SimpleNamespace(
            root=source, clean_room=clean / "report.json", candidate=CANDIDATE,
            replay_case="add-signed-overflow", replay_case_file=inputs["case"],
            diff_binary=inputs["diff"], sail_binary=inputs["sail"], sail_config=inputs["config"],
            out=self.package / "week6-evidence.tar.gz", manifest_out=self.package / "MANIFEST.json"))
        self.labels = []
        self.corrupt_download = False
        self.original_command = MODULE.run_command
        self.original_subprocess = subprocess.run

    def fake_transport(self, out, label, argv, cwd):
        self.labels.append(label)
        if label == "replay":
            return self.original_command(out, label, argv, cwd)
        self.assertEqual(argv[0], "gh")
        values = {"remote-query": self.run, "jobs-query": self.jobs,
                  "artifacts-query": self.artifacts}
        if label in values:
            body = json.dumps(values[label]).encode()
        elif label in ("first-download", "external-download"):
            dest = Path(cwd) / argv[argv.index("--dir") + 1]
            dest.mkdir()
            for name in ("week6-evidence.tar.gz", "MANIFEST.json"):
                shutil.copyfile(self.package / name, dest / name)
            if label == "external-download" and self.corrupt_download:
                (dest / "week6-evidence.tar.gz").write_bytes(b"corrupt fixture download")
            body = b"fixture download, not GitHub evidence\n"
        elif label == "attestation-download":
            (Path(cwd) / "fixture.jsonl").write_text('{"fixture":"not a signature"}\n')
            body = b"fixture attestation\n"
        else:
            self.assertTrue(label.startswith("job-"), label)
            body = b"fixture job log\n"
        a, b = Path(out) / (label + ".stdout"), Path(out) / (label + ".stderr")
        a.write_bytes(body)
        b.write_bytes(b"")
        return {"argv": list(map(str, argv)), "exit_code": 0,
                "stdout": MODULE.ref(out, a), "stderr": MODULE.ref(out, b)}

    def verify_fixture_or_run(self, argv, *args, **kwargs):
        if argv[:3] == ["gh", "attestation", "verify"]:
            self.assertEqual(argv[argv.index("--source-digest") + 1], CANDIDATE)
            self.assertTrue(Path(argv[3]).is_file())
            return SimpleNamespace(returncode=0, stdout=b'[{"fixture":true}]', stderr=b"")
        return self.original_subprocess(argv, *args, **kwargs)

    def collect(self):
        with patch.object(MODULE, "run_command", side_effect=self.fake_transport), \
                patch.object(MODULE.external.source, "capture", return_value=self.snapshot), \
                patch.object(subprocess, "run", side_effect=self.verify_fixture_or_run):
            return MODULE.collect(SimpleNamespace(out=self.out, candidate=CANDIDATE,
                run_id=RUN_ID, repository=self.policy["repository"]))

    def test_full_collector_extracts_replays_and_validates_shared_layout(self):
        result = self.collect()
        self.assertTrue(result["ci_download_verified"])
        self.assertFalse(result["week6_closed"])
        report = json.loads((self.out / "report.json").read_text())
        expected = MODULE.gate.member_target(Path("downloaded"), "cases/add-signed-overflow.json")
        self.assertEqual(report["replay"]["source"], expected.as_posix())
        self.assertEqual(Path(report["replay"]["argv"][0]), MODULE.gate.member_target(
            self.out / "downloaded", "bin/ckb-vm-sail-diff"))
        self.assertFalse((self.out / "downloaded/bin").exists())
        self.assertFalse((self.out / "downloaded/cases").exists())
        executed = json.loads((self.out / "replay-result/fixture-argv.json").read_text())
        self.assertEqual(executed, report["replay"]["argv"][1:])
        self.assertEqual(result["jobs"], 5)
        self.assertIn("first-download", self.labels)
        self.assertIn("external-download", self.labels)

    def test_old_flat_command_fails_after_real_extraction(self):
        def old_command(downloaded, manifest, artifact_dir):
            source = downloaded / manifest["replay_case"]
            return source, [str(downloaded / "bin/ckb-vm-sail-diff"), "--replay", str(source)]
        with patch.object(MODULE, "replay_command", side_effect=old_command), \
                self.assertRaises(FileNotFoundError):
            self.collect()
        self.assertEqual(json.loads((self.out / "report.json").read_text())["status"], "failed")

    def test_corrupt_second_download_rejected_before_extraction(self):
        self.corrupt_download = True
        with self.assertRaisesRegex(RuntimeError, "independent artifact downloads differ"):
            self.collect()
        self.assertNotIn("replay", self.labels)
        self.assertFalse((self.out / "downloaded/artifacts").exists())

    def test_failed_remote_run_never_downloads_or_replays(self):
        self.run["conclusion"] = "failure"
        with self.assertRaisesRegex(RuntimeError, "remote run identity/result"):
            self.collect()
        self.assertNotIn("first-download", self.labels)
        self.assertNotIn("replay", self.labels)


if __name__ == "__main__":
    unittest.main()
