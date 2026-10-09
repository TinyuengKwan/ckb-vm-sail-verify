"""Real offline Git/archive round trips; only the CKB baseline is a toy fixture."""
import copy
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_capsule as capsule


class CapsuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="capsule with spaces ")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "project"
        self.env = capsule.environment()
        for label in ("ckb", "sail", "project"):
            root = self.base / label
            root.mkdir()
            self.git(root, "init", "-q")
            (root / "README.md").write_text("fixture " + label + "\n")
            self.commit(root)
        for label, name in (("ckb", "deps/ckb-vm"), ("sail", "deps/sail-riscv")):
            self.git(self.root, "submodule", "add", str(self.base / label), name)
        self.commit(self.root)
        self.candidate = self.git(self.root, "rev-parse", "HEAD").strip()
        mock = patch.object(capsule.source.baseline, "check", return_value={"fixture_only": True})
        mock.start()
        self.addCleanup(mock.stop)

    def git(self, cwd, *args):
        result = subprocess.run(["git", *args], cwd=cwd, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def commit(self, root):
        self.git(root, "add", ".")
        self.git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")

    def create(self):
        out = self.base / "capsule"
        report = capsule.create(self.root, self.candidate, out)
        return out / report["archive"]["path"], report["archive"]["sha256"]

    def test_exact_offline_restore_with_overlay_deletion_and_modes(self):
        (self.root / "README.md").unlink()
        executable = self.root / "new-script"
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        (self.root / "deps/ckb-vm/overlay").write_text("fixture CKB overlay\n")
        expected = capsule.source.capture(self.root)
        archive, digest = self.create()
        result = capsule.restore(archive, digest, self.candidate, self.base / "restore")
        checkout = Path(result["checkout"])
        self.assertEqual(capsule.source.capture(checkout), expected)
        self.assertEqual(capsule.source.capture(self.root), expected)
        self.assertFalse((checkout / "README.md").exists())
        self.assertEqual((checkout / "new-script").stat().st_mode & 0o777, 0o755)
        self.assertTrue(result["independent_git_objects"])
        self.assertEqual(result["status"], "exact_source_restored")

    def test_rejects_wrong_archive_digest_before_creating_output(self):
        archive, _ = self.create()
        out = self.base / "restore"
        with self.assertRaisesRegex(RuntimeError, "trusted digest"):
            capsule.restore(archive, "0" * 64, self.candidate, out)
        self.assertFalse(out.exists())

    def test_rejects_wrong_candidate_before_creating_output(self):
        archive, digest = self.create()
        out = self.base / "restore"
        with self.assertRaises(RuntimeError):
            capsule.restore(archive, digest, "0" * 40, out)
        self.assertFalse(out.exists())

    def test_rejects_existing_or_aliased_output(self):
        archive, digest = self.create()
        occupied = self.base / "occupied"
        occupied.mkdir()
        (occupied / "user-file").write_text("preserve")
        linked = self.base / "linked"
        linked.symlink_to(occupied, target_is_directory=True)
        for out in (occupied, linked / "new"):
            with self.subTest(out=out), self.assertRaises(RuntimeError):
                capsule.restore(archive, digest, self.candidate, out)
        self.assertEqual((occupied / "user-file").read_text(), "preserve")

    def test_rejects_snapshot_self_digest_and_cross_snapshot(self):
        archive, _ = self.create()
        snapshot = capsule.source.capture(self.root)
        altered = copy.deepcopy(snapshot)
        altered["snapshot_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "self-digest"):
            capsule.validate_snapshot(altered, self.candidate)
        with self.assertRaisesRegex(RuntimeError, "snapshot differs"):
            capsule.inspect(archive, self.candidate, altered)

    def test_rejects_archive_traversal_links_extra_files_and_mode_changes(self):
        archive, _ = self.create()
        for mutation in ("traversal", "link", "extra", "mode"):
            bad = self.base / (mutation + ".tar.gz")
            with tarfile.open(archive, "r:gz") as original, tarfile.open(bad, "w:gz") as target:
                for member in original:
                    if mutation == "mode" and member.name == "payload/README.md":
                        member.mode = 0o755
                    target.addfile(member, original.extractfile(member) if member.isfile() else None)
                if mutation != "mode":
                    extra = tarfile.TarInfo("../escape" if mutation == "traversal" else "extra")
                    if mutation == "link":
                        extra.type, extra.linkname = tarfile.SYMTYPE, "/tmp/outside"
                        target.addfile(extra)
                    else:
                        extra.size = 1
                        target.addfile(extra, io.BytesIO(b"x"))
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                capsule.inspect(bad, self.candidate)


if __name__ == "__main__":
    unittest.main()
