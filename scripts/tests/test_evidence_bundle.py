#!/usr/bin/env python3
"""Pack/extract/unpack of the clean-room evidence bundle."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_release as audit
import evidence_bundle as bundle


class EvidenceBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="evidence-bundle-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.git_checkout("source")
        clean = self.source / bundle.CLEAN
        (clean / "runtime/cargo-target/debug").mkdir(parents=True)
        (clean / "fixed-inputs").mkdir()
        (clean / "report.json").write_text(json.dumps({"provider": {"kind": "independent-ephemeral-vm"}}))
        (clean / bundle.VM_RECORD).write_text("{}\n")
        (clean / "stage.stdout").write_text("stage\n")
        (clean / "runtime/report.json").write_text("{}\n")
        (clean / "runtime/ckb-vm-sail-diff").write_bytes(b"\x7fELF fixture")
        (clean / "runtime/ckb-vm-sail-diff").chmod(0o755)
        (clean / "runtime/cargo-target/debug/big").write_bytes(b"cache")
        (clean / "fixed-inputs/extra-installations.tar.xz").write_bytes(b"not evidence")

    def git_checkout(self, name):
        path = self.base / name
        path.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for argv in [["git", "init", "-q"], ["git", "commit", "-q", "--allow-empty", "-m", "candidate"]]:
            subprocess.run(argv, cwd=path, check=True, env=env, stdout=subprocess.PIPE)
        self.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
        return path

    def test_pack_is_deterministic_and_excludes_inputs_and_caches(self):
        first = bundle.pack(self.source, self.base / "a.tar.gz")
        second = bundle.pack(self.source, self.base / "b.tar.gz")
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(first["members"], 5)
        with tarfile.open(self.base / "a.tar.gz") as tar:
            names = tar.getnames()
        self.assertNotIn(bundle.CLEAN + "/fixed-inputs/extra-installations.tar.xz", names)
        self.assertNotIn(bundle.CLEAN + "/runtime/cargo-target/debug/big", names)
        self.assertIn(bundle.CLEAN + "/" + bundle.VM_RECORD, names)
        (self.source / bundle.CLEAN / bundle.VM_RECORD).unlink()
        with self.assertRaisesRegex(RuntimeError, "lacks"):
            bundle.pack(self.source, self.base / "c.tar.gz")

    def test_unpack_verifies_hash_refuses_overwrite_and_validates(self):
        packed = bundle.pack(self.source, self.base / "bundle.tar.gz")
        target = self.git_checkout("target")
        with self.assertRaisesRegex(RuntimeError, "SHA-256 differs"):
            bundle.unpack(self.base / "bundle.tar.gz", "0" * 64, target, self.commit)
        with self.assertRaisesRegex(RuntimeError, "candidate commit"):
            bundle.unpack(self.base / "bundle.tar.gz", packed["sha256"], target, "b" * 40)
        with patch.object(audit, "check_vm_report", return_value={"provider": "independent-ephemeral-vm"}) as check:
            result = bundle.unpack(self.base / "bundle.tar.gz", packed["sha256"], target, self.commit)
        check.assert_called_once_with(target / bundle.CLEAN / "report.json", self.commit, target)
        self.assertEqual(result["members"], 5)
        self.assertTrue(os.access(target / bundle.CLEAN / "runtime/ckb-vm-sail-diff", os.X_OK))
        with patch.object(audit, "check_vm_report", return_value={}), self.assertRaisesRegex(RuntimeError, "occupied"):
            bundle.unpack(self.base / "bundle.tar.gz", packed["sha256"], target, self.commit)

    def test_extract_rejects_links_foreign_and_excluded_members(self):
        for name, member, pattern in [
            ("foreign.tar.gz", tarfile.TarInfo("scripts/clean_room.py"), "outside the clean-room"),
            ("traversal.tar.gz", tarfile.TarInfo(bundle.CLEAN + "/../../../etc/passwd"), "unsafe"),
            ("cache.tar.gz", tarfile.TarInfo(bundle.CLEAN + "/runtime/cargo-target/x"), "excluded"),
        ]:
            path = self.base / name
            with tarfile.open(path, "w:gz") as tar:
                member.size = 1
                tar.addfile(member, io.BytesIO(b"x"))
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, pattern):
                bundle.extract(path, bundle.sha(path), self.base / ("x-" + name))
        path = self.base / "link.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            link = tarfile.TarInfo(bundle.CLEAN + "/report.json")
            link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
            tar.addfile(link)
        with self.assertRaisesRegex(RuntimeError, "special/link"):
            bundle.extract(path, bundle.sha(path), self.base / "x-link")


if __name__ == "__main__":
    unittest.main()
