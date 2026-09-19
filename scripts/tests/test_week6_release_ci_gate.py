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
from unittest.mock import patch


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
            # Replay members never touch the checkout root (they would alter the source snapshot).
            self.assertTrue((destination / GATE.REPLAY_ROOT / "bin/ckb-vm-sail-diff").is_file())
            self.assertTrue((destination / GATE.REPLAY_ROOT / "cases/add-signed-overflow.json").is_file())
            self.assertFalse((destination / "bin").exists())
            self.assertFalse((destination / "cases").exists())

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

    def test_archived_aggregate_mode_binds_host_provenance_without_recomputing(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            clean_dir = root / "artifacts/boundary-check/week6-clean-room"
            clean_dir.mkdir(parents=True)
            (clean_dir / "report.json").write_text('{"provider": {"kind": "independent-ephemeral-vm"}}\n')
            runtime = clean_dir / "runtime-report.json"
            runtime.write_text('{"fixture": "runtime"}\n')
            reference = {"path": "artifacts/boundary-check/week6-clean-room/runtime-report.json",
                         "sha256": ARCHIVE.sha(runtime)}
            absent = {"path": "artifacts/boundary-check/week6-native-clean-room/rust-tests/report.json",
                      "sha256": "a" * 64}
            verified_slots = ["runtime", "lean", "rocq", "rust_tests", "mismatches", "maintainer_demo", "public_claims"]
            audit_manifest = clean_dir / "audit-manifest.json"
            audit_manifest.write_text(json.dumps({"evidence": {
                slot: (absent if slot == "rust_tests" else reference) for slot in verified_slots}}) + "\n")
            checks = {slot: {"status": "missing", "reason": "x"} for slot in GATE.audit_release.SLOTS}
            for slot in verified_slots:
                checks[slot] = {"status": "verified_existing_evidence",
                                "reference": dict(absent if slot == "rust_tests" else reference)}
            checks["clean_room"] = {"status": "incomplete",
                                    "reason": "independent ephemeral VM host provenance record absent"}
            checks["worktree_audit"] = {"status": "incomplete", "reason": "partial"}
            expected = ["clean_room", "ci_download", "release_package", "third_party", "worktree_audit"]
            aggregate = {"status": "incomplete", "manifest_sha256": ARCHIVE.sha(audit_manifest),
                         "release_claimed": False, "week6_closed": False, "fresh_execution_claimed": False,
                         "outstanding": expected, "checks": checks}
            archived = clean_dir / "audit-result.json"
            archived.write_text(json.dumps(aggregate) + "\n")
            with patch.object(GATE.external, "check_vm_provenance", return_value={"operator_attested": True}) as prov, \
                    patch.object(GATE.audit_release, "aggregate") as recompute:
                result = GATE.validate_archived_aggregate(root, audit_manifest, archived, expected, clean_dir / "report.json")
            prov.assert_called_once_with(clean_dir / "report.json")
            recompute.assert_not_called()
            self.assertEqual(result["verified_slots"], 7)
            for mutate, pattern in [
                (lambda a: a.update(outstanding=expected[1:]), "boundary differs"),
                (lambda a: a.update(manifest_sha256="0" * 64), "identity"),
                (lambda a: a["checks"]["runtime"].update(status="invalid"), "not verified"),
                (lambda a: a["checks"]["clean_room"].update(reason="clean-room report invalid"), "deferred host record"),
                (lambda a: a["checks"]["runtime"]["reference"].update(sha256="1" * 64), "differs from manifest"),
                (lambda a: a.update(release_claimed=True), "boundary"),
            ]:
                broken = json.loads(json.dumps(aggregate)); mutate(broken)
                archived.write_text(json.dumps(broken) + "\n")
                with self.subTest(pattern=pattern), \
                        patch.object(GATE.external, "check_vm_provenance", return_value={"operator_attested": True}), \
                        self.assertRaisesRegex(RuntimeError, pattern):
                    GATE.validate_archived_aggregate(root, audit_manifest, archived, expected, clean_dir / "report.json")

    def test_rejects_occupied_target(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            source, output, destination = base / "source", base / "output", base / "destination"
            source.mkdir(); output.mkdir(); destination.mkdir()
            args = self.producer_args(source, output)
            ARCHIVE.create(args)
            (destination / GATE.REPLAY_ROOT / "bin").mkdir(parents=True)
            (destination / GATE.REPLAY_ROOT / "bin/ckb-vm-sail-diff").write_text("occupied")
            with self.assertRaisesRegex(RuntimeError, "occupied/aliased"):
                GATE.extract_and_validate(args.out, destination, CANDIDATE)


if __name__ == "__main__":
    unittest.main()
