"""Package integrity, extraction boundaries and fail-closed input tests."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decoder_input_bundle as bundle


def member(name="package.json", kind=tarfile.REGTYPE, size=0, mode=0o644):
    item = tarfile.TarInfo(name)
    item.type, item.size, item.mode = kind, size, mode
    return item


class ArchiveTests(unittest.TestCase):
    def test_regular_manifest_and_payload_allowed(self):
        bundle.check_members([member(), member("bin/tool", size=10, mode=0o755)])

    def test_path_escape_or_alias_rejected(self):
        for name in ["../outside", "/absolute", "a/../outside", "a//b", "./a", "a\\b", ""]:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                bundle.check_members([member(), member(name)])

    def test_links_directories_and_devices_rejected(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE,
                     tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE]:
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                bundle.check_members([member(), member("entry", kind=kind)])

    def test_duplicates_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            bundle.check_members([member(), member()])

    def test_missing_manifest_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "manifest missing"):
            bundle.check_members([member("other")])

    def test_privileged_or_writable_modes_rejected(self):
        for mode in [0o4755, 0o777, 0o666, 0o664]:
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                bundle.check_members([member(mode=mode)])

    def test_entry_count_and_size_limits(self):
        for entries in [[member(size=bundle.MAX_BYTES + 1)],
                        [member(size=bundle.MAX_BYTES), member("extra", size=1)],
                        [member(size=-1)],
                        [member()] + [member(str(i)) for i in range(256)]]:
            with self.subTest(entries=len(entries)), self.assertRaises(RuntimeError):
                bundle.check_members(entries)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="decoder-input-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root / "payload"
        self.payload.mkdir()
        (self.payload / "package.json").write_text("{}")
        (self.payload / "data").write_bytes(b"approved")
        (self.payload / "data").chmod(0o644)
        self.digest = hashlib.sha256(b"approved").hexdigest()
        self.expected = {"data": self.digest}
        self.metadata = {"data": {"sha256": self.digest, "bytes": 8, "mode": 0o644}}

    def test_exact_files_pass(self):
        bundle.check_files(self.payload, self.expected, self.metadata)

    def test_group_writable_manifest_fails_before_catalogue_lookup(self):
        (self.payload / "package.json").chmod(0o664)
        with patch.object(bundle, "catalogue") as catalogue:
            with self.assertRaisesRegex(RuntimeError, "manifest mode"):
                bundle.verify_payload(self.payload)
            catalogue.assert_not_called()

    def test_changed_file_rejected_even_with_self_consistent_manifest(self):
        (self.payload / "data").write_bytes(b"modified")
        self.metadata["data"]["sha256"] = bundle.sha(self.payload / "data")
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            bundle.check_files(self.payload, self.expected, self.metadata)

    def test_unknown_file_rejected(self):
        (self.payload / "extra").write_bytes(b"extra")
        with self.assertRaisesRegex(RuntimeError, "unexpected or missing"):
            bundle.check_files(self.payload, self.expected, self.metadata)

    def test_missing_file_rejected(self):
        (self.payload / "data").rename(self.root / "preserved")
        with self.assertRaisesRegex(RuntimeError, "unexpected or missing"):
            bundle.check_files(self.payload, self.expected, self.metadata)

    def test_symlink_is_not_a_materialized_input(self):
        (self.payload / "data").rename(self.root / "preserved")
        (self.payload / "data").symlink_to(self.root / "preserved")
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            bundle.check_files(self.payload, self.expected, self.metadata)

    def test_mode_or_size_drift_rejected(self):
        for field, value in [("mode", 0o755), ("bytes", 7)]:
            metadata = {"data": dict(self.metadata["data"], **{field: value})}
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                bundle.check_files(self.payload, self.expected, metadata)

    def test_unapproved_manifest_entry_rejected(self):
        self.metadata["unknown"] = self.metadata["data"]
        with self.assertRaisesRegex(RuntimeError, "catalogue"):
            bundle.check_files(self.payload, self.expected, self.metadata)

    def archive(self, entries):
        archive = self.root / "package.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for entry, data in entries:
                entry.size = len(data)
                tar.addfile(entry, io.BytesIO(data))
        return archive

    def test_bad_archive_hash_rejected_before_output_creation(self):
        archive = self.archive([(member(), b"{}")])
        output = self.root / "new"
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            bundle.unpack(archive, "0" * 64, output)
        self.assertFalse(output.exists())

    def test_explicit_digest_required(self):
        with self.assertRaisesRegex(RuntimeError, "explicit SHA"):
            bundle.unpack(self.root / "absent", "", self.root / "new")

    def test_unsafe_archive_rejected_before_output_creation(self):
        archive = self.archive([(member(), b"{}"), (member("../escape"), b"bad")])
        output = self.root / "new"
        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            bundle.unpack(archive, bundle.sha(archive), output)
        self.assertFalse(output.exists())
        self.assertFalse((self.root / "escape").exists())

    def test_existing_output_preserved(self):
        archive = self.archive([(member(), b"{}")])
        with self.assertRaises(FileExistsError):
            bundle.unpack(archive, bundle.sha(archive), self.payload)
        self.assertEqual((self.payload / "data").read_bytes(), b"approved")

    def test_unpack_calls_catalogue_verification(self):
        archive = self.archive([(member(), b"{}"), (member("data"), b"approved")])
        output = self.root / "new"
        with patch.object(bundle, "verify_payload", side_effect=RuntimeError("catalogue rejects")) as verify:
            with self.assertRaisesRegex(RuntimeError, "catalogue rejects"):
                bundle.unpack(archive, bundle.sha(archive), output)
            verify.assert_called_once_with(output)

    def test_git_environment_cannot_supply_external_object_store(self):
        with patch.dict(bundle.os.environ, {"GIT_ALTERNATE_OBJECT_DIRECTORIES": "/old",
                                          "GIT_OBJECT_DIRECTORY": "/old", "GIT_DIR": "/old"}):
            env = bundle.git_env()
        for key in ["GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_OBJECT_DIRECTORY", "GIT_DIR"]:
            self.assertNotIn(key, env)
        self.assertEqual(env["GIT_CONFIG_GLOBAL"], bundle.os.devnull)


if __name__ == "__main__":
    unittest.main()
