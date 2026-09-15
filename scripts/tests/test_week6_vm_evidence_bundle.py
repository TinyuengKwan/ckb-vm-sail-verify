#!/usr/bin/env python3
"""Pack/unpack tests for the ephemeral VM evidence bundle used by the CI intake job."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import week6_vm_evidence_bundle as bundle
import release_external_evidence as external


class VmEvidenceBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="week6-vm-bundle-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.git_checkout("source")
        clean = self.source / bundle.CLEAN
        clean.mkdir(parents=True)
        (clean / "report.json").write_text(json.dumps({"provider": {"kind": external.VM_PROVIDER}}))
        (clean / external.VM_RECORD).write_text("{}\n")
        (clean / "stage.stdout").write_text("stage\n")
        native = self.source / bundle.PREFIX / "week6-native-clean-room/runtime"
        native.mkdir(parents=True)
        (native / "report.json").write_text("{}\n")
        (native / "ckb-vm-sail-diff").write_bytes(b"\x7fELF fixture")
        (native / "ckb-vm-sail-diff").chmod(0o755)
        (self.source / bundle.PREFIX / "isolated-rust-lean-x").mkdir()
        (self.source / bundle.PREFIX / "isolated-rust-lean-x/rustc").write_text("not evidence\n")

    def git_checkout(self, name):
        path = self.base / name
        path.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for argv in [["git", "init", "-q"], ["git", "commit", "-q", "--allow-empty", "-m", "candidate"]]:
            subprocess.run(argv, cwd=path, check=True, env=env, stdout=subprocess.PIPE)
        self.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
        return path

    def test_pack_is_deterministic_and_limited_to_week6_evidence(self):
        first = bundle.pack(self.source, self.base / "a.tar.gz")
        second = bundle.pack(self.source, self.base / "b.tar.gz")
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(first["members"], 5)
        import tarfile
        with tarfile.open(self.base / "a.tar.gz") as tar:
            names = tar.getnames()
        self.assertNotIn(bundle.PREFIX + "/isolated-rust-lean-x/rustc", names)
        self.assertIn(bundle.CLEAN + "/vm-provenance.json", names)
        (self.source / bundle.CLEAN / external.VM_RECORD).unlink()
        with self.assertRaisesRegex(RuntimeError, "lacks"):
            bundle.pack(self.source, self.base / "c.tar.gz")

    def test_unpack_verifies_hash_refuses_overwrite_and_runs_both_validators(self):
        packed = bundle.pack(self.source, self.base / "bundle.tar.gz")
        target = self.git_checkout("target")
        with self.assertRaisesRegex(RuntimeError, "SHA-256 differs"):
            bundle.unpack(self.base / "bundle.tar.gz", "0" * 64, target, self.commit)
        with self.assertRaisesRegex(RuntimeError, "candidate commit"):
            bundle.unpack(self.base / "bundle.tar.gz", packed["sha256"], target, "b" * 40)
        with patch.object(external, "check_clean_room", return_value={"provider": external.VM_PROVIDER}) as clean, \
                patch.object(external, "check_vm_provenance", return_value={"operator_attested": True}) as prov:
            result = bundle.unpack(self.base / "bundle.tar.gz", packed["sha256"], target, self.commit)
        clean.assert_called_once_with(target / bundle.CLEAN / "report.json", self.commit, root=target)
        prov.assert_called_once_with(target / bundle.CLEAN / "report.json")
        self.assertEqual(result["members"], 5)
        self.assertFalse(result["boundaries"]["ci_download_verified"])
        binary = target / bundle.PREFIX / "week6-native-clean-room/runtime/ckb-vm-sail-diff"
        self.assertTrue(os.access(binary, os.X_OK))
        with patch.object(external, "check_clean_room", return_value={"provider": external.VM_PROVIDER}), \
                patch.object(external, "check_vm_provenance", return_value={}), \
                self.assertRaisesRegex(RuntimeError, "occupied"):
            bundle.unpack(self.base / "bundle.tar.gz", packed["sha256"], target, self.commit)
        with patch.object(external, "check_clean_room", return_value={"provider": "github-actions-ephemeral"}), \
                self.assertRaisesRegex(RuntimeError, "not an ephemeral VM run"):
            bundle.unpack(self.base / "bundle.tar.gz", packed["sha256"], self.git_checkout("other"), self.commit)

    def test_unpack_rejects_links_and_foreign_members(self):
        import io, tarfile
        for name, member, pattern in [
            ("foreign.tar.gz", tarfile.TarInfo("scripts/week6_clean_room.py"), "outside the Week6"),
            ("traversal.tar.gz", tarfile.TarInfo(bundle.PREFIX + "/week6-x/../../../etc/passwd"), "unsafe"),
        ]:
            path = self.base / name
            with tarfile.open(path, "w:gz") as tar:
                member.size = 1
                tar.addfile(member, io.BytesIO(b"x"))
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, pattern):
                bundle.unpack(path, bundle.sha(path), self.git_checkout("t-" + name), self.commit)
        path = self.base / "link.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            link = tarfile.TarInfo(bundle.CLEAN + "/report.json")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tar.addfile(link)
        with self.assertRaisesRegex(RuntimeError, "special/link"):
            bundle.unpack(path, bundle.sha(path), self.git_checkout("t-link"), self.commit)


if __name__ == "__main__":
    unittest.main()
