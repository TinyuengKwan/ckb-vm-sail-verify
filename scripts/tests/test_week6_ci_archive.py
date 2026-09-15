#!/usr/bin/env python3
import argparse
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("week6_ci_archive", HERE.parent / "week6_ci_archive.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CANDIDATE = "a" * 40
SNAPSHOT = "b" * 64


class ArchiveTests(unittest.TestCase):
    def prepare(self, root):
        clean = root / "clean"
        clean.mkdir()
        snapshot = clean / "source-snapshot.json"
        snapshot.write_text(json.dumps({"snapshot_sha256": SNAPSHOT}) + "\n")
        report = {
            "schema_version": 1,
            "kind": "clean-room-evidence-v1",
            "status": "passed",
            "candidate": CANDIDATE,
            "source_snapshot": {"path": "source-snapshot.json", "sha256": MODULE.sha(snapshot)},
        }
        (clean / "report.json").write_text(json.dumps(report) + "\n")
        (clean / "nested").mkdir()
        (clean / "nested/log.txt").write_text("recorded\n")
        inputs = {}
        for name, data in {
            "case.json": b"case\n", "diff": b"diff\n", "sail": b"sail\n", "config.json": b"{}\n"
        }.items():
            path = root / name
            path.write_bytes(data)
            inputs[name] = path
        return clean, inputs

    def args(self, root, suffix=""):
        clean, inputs = self.prepare(root)
        return argparse.Namespace(
            root=root, clean_room=clean / "report.json", candidate=CANDIDATE,
            replay_case="add-signed-overflow", replay_case_file=inputs["case.json"],
            diff_binary=inputs["diff"], sail_binary=inputs["sail"], sail_config=inputs["config.json"],
            out=root / ("archive" + suffix + ".tar.gz"),
            manifest_out=root / ("manifest" + suffix + ".json"),
        )

    def test_create_inventory_and_manifest_identity(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            args = self.args(root)
            result = MODULE.create(args)
            self.assertEqual(result["status"], "created_and_independently_stream_verified")
            manifest = json.loads(args.manifest_out.read_text())
            self.assertEqual(manifest["candidate"], CANDIDATE)
            self.assertEqual(manifest["source_snapshot_sha256"], SNAPSHOT)
            self.assertEqual(manifest["clean_room_report"], "clean/report.json")
            self.assertEqual(manifest["replay_case"], "cases/add-signed-overflow.json")
            with tarfile.open(args.out, "r:gz") as archive:
                archived = archive.extractfile("MANIFEST.json").read()
                names = archive.getnames()
            self.assertEqual(archived, args.manifest_out.read_bytes())
            self.assertEqual(len(names), len(set(names)))
            self.assertIn("bin/ckb-vm-sail-diff", names)
            self.assertIn("clean/nested/log.txt", names)

    def test_archive_is_deterministic(self):
        with tempfile.TemporaryDirectory() as first_name, tempfile.TemporaryDirectory() as second_name:
            first, second = Path(first_name), Path(second_name)
            a, b = self.args(first), self.args(second)
            MODULE.create(a)
            MODULE.create(b)
            self.assertEqual(MODULE.sha(a.out), MODULE.sha(b.out))
            self.assertEqual(a.manifest_out.read_bytes(), b.manifest_out.read_bytes())

    def test_rejects_wrong_candidate(self):
        with tempfile.TemporaryDirectory() as name:
            args = self.args(Path(name))
            args.candidate = "branch-name"
            with self.assertRaisesRegex(RuntimeError, "full Git OID"):
                MODULE.create(args)

    def test_rejects_linked_clean_room_member(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            args = self.args(root)
            (args.clean_room.parent / "linked.log").symlink_to("nested/log.txt")
            with self.assertRaisesRegex(RuntimeError, "non-regular input"):
                MODULE.create(args)

    def test_rejects_existing_output(self):
        with tempfile.TemporaryDirectory() as name:
            args = self.args(Path(name))
            args.out.write_bytes(b"occupied")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                MODULE.create(args)


if __name__ == "__main__":
    unittest.main()
