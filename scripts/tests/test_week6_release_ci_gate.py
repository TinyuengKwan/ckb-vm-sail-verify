#!/usr/bin/env python3
import argparse
import gzip
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ARCHIVE = load("week6_ci_archive")
GATE = load("week6_release_ci_gate")
CANDIDATE = "a" * 40
SNAPSHOT = "b" * 64


def raw_archive(path, rows):
    with Path(path).open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", mtime=0, fileobj=raw) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data, kind in rows:
                    info = tarfile.TarInfo(name)
                    info.uid = info.gid = info.mtime = 0
                    info.mode = 0o644
                    if kind == "symlink":
                        info.type = tarfile.SYMTYPE
                        info.linkname = "target"
                        archive.addfile(info)
                    else:
                        info.size = len(data)
                        archive.addfile(info, io.BytesIO(data))


class GateArchiveTests(unittest.TestCase):
    def producer_args(self, root, output):
        clean = root / "artifacts/boundary-check/week6-clean-room"
        clean.mkdir(parents=True)
        snapshot = clean / "source-snapshot.json"
        snapshot.write_text(json.dumps({"snapshot_sha256": SNAPSHOT}) + "\n")
        report = {
            "schema_version": 1, "kind": "clean-room-evidence-v1", "status": "passed",
            "candidate": CANDIDATE,
            "source_snapshot": {"path": "source-snapshot.json", "sha256": ARCHIVE.sha(snapshot)},
        }
        (clean / "report.json").write_text(json.dumps(report) + "\n")
        inputs = {}
        for name in ["case", "diff", "sail", "config"]:
            path = root / (name + ".input")
            path.write_text(name + "\n")
            inputs[name] = path
        return argparse.Namespace(
            root=root, clean_room=clean / "report.json", candidate=CANDIDATE,
            replay_case="add-signed-overflow", replay_case_file=inputs["case"],
            diff_binary=inputs["diff"], sail_binary=inputs["sail"], sail_config=inputs["config"],
            out=output / "archive.tar.gz", manifest_out=output / "MANIFEST.json")

    def test_extracts_only_manifested_allowlisted_files(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            source, output, destination = base / "source", base / "output", base / "destination"
            source.mkdir(); output.mkdir(); destination.mkdir()
            args = self.producer_args(source, output)
            ARCHIVE.create(args)
            manifest, digest = GATE.extract_and_validate(args.out, destination, CANDIDATE)
            self.assertEqual(digest, ARCHIVE.sha(args.out))
            self.assertEqual(manifest["clean_room_report"],
                             "artifacts/boundary-check/week6-clean-room/report.json")
            self.assertTrue((destination / manifest["clean_room_report"]).is_file())
            self.assertFalse((destination / "MANIFEST.json").exists())

    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); archive = root / "bad.tar.gz"; destination = root / "dest"; destination.mkdir()
            raw_archive(archive, [("../escape", b"bad", "file")])
            with self.assertRaisesRegex(RuntimeError, "unsafe archive name"):
                GATE.extract_and_validate(archive, destination, CANDIDATE)

    def test_rejects_unexpected_prefix(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); archive = root / "bad.tar.gz"; destination = root / "dest"; destination.mkdir()
            raw_archive(archive, [("scripts/overwrite.py", b"bad", "file")])
            with self.assertRaisesRegex(RuntimeError, "extra/duplicate"):
                GATE.extract_and_validate(archive, destination, CANDIDATE)

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); archive = root / "bad.tar.gz"; destination = root / "dest"; destination.mkdir()
            raw_archive(archive, [("bin/tool", b"", "symlink")])
            with self.assertRaisesRegex(RuntimeError, "unsafe CI archive metadata"):
                GATE.extract_and_validate(archive, destination, CANDIDATE)

    def test_rejects_occupied_target(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            source, output, destination = base / "source", base / "output", base / "destination"
            source.mkdir(); output.mkdir(); destination.mkdir()
            args = self.producer_args(source, output)
            ARCHIVE.create(args)
            (destination / "bin").mkdir()
            (destination / "bin/ckb-vm-sail-diff").write_text("occupied")
            with self.assertRaisesRegex(RuntimeError, "occupied/aliased"):
                GATE.extract_and_validate(args.out, destination, CANDIDATE)


if __name__ == "__main__":
    unittest.main()
