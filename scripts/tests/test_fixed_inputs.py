#!/usr/bin/env python3
"""Fixed-input package verification, staging, root installation and CMake staging."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fixed_inputs as inputs


def write_archive(path, sources, entries, compression="xz"):
    with tarfile.open(path, "x:" + compression, format=tarfile.PAX_FORMAT) as archive:
        for name, row in sorted(entries.items()):
            member = tarfile.TarInfo(name)
            member.uid = member.gid = member.mtime = 0
            if row["kind"] == "file":
                member.size, member.mode = row["bytes"], row["mode"]
                with Path(sources[name]).open("rb") as stream:
                    archive.addfile(member, stream)
            elif row["kind"] == "directory":
                member.type, member.mode = tarfile.DIRTYPE, row["mode"]
                archive.addfile(member)
            else:
                member.type, member.linkname, member.mode = tarfile.SYMTYPE, row["target"], 0o777
                archive.addfile(member)


class FixedInputsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fixed-inputs-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "tool"
        self.source.write_bytes(b"fixed tool bytes")
        self.source.chmod(0o755)
        self.names = ["artifacts/boundary-check/" + name + "/bin/tool" for name in inputs.INSTALL_ROOTS]
        self.entries = {name: inputs.identity(self.source) for name in self.names}
        self.manifest = {"schema_version": 1, "kind": "extra-fixed-prefix-installations-v1",
                         "canonical_checkout": "/canonical/checkout", "inputs": {"policy": "fixed"},
                         "required_external": ["host tools"],
                         "boundaries": {k: False for k in ["clean_room", "release", "kernel_execution", "relocatable", "host_closure_complete"]},
                         "entries": self.entries}
        self.path = self.root / "manifest.json"
        self.archive = self.root / "tools.tar.xz"

    def save(self, manifest=None):
        self.path.write_text(json.dumps(self.manifest if manifest is None else manifest))
        return inputs.sha(self.path)

    def build(self, compression="xz"):
        digest = self.save()
        write_archive(self.archive, {name: self.source for name in self.names}, self.entries, compression)
        return digest

    def test_verify_stage_and_install_roundtrip(self):
        digest = self.build()
        result = inputs.verify_archive(self.archive, self.path, digest)
        self.assertEqual((result["compression"], result["entries"]), ("xz", 5))
        staged = self.root / "staged"
        inputs.stage(self.archive, self.path, digest, staged)
        self.assertEqual((staged / self.names[0]).read_bytes(), b"fixed tool bytes")
        checkout = self.root / "checkout"
        roots = inputs.install_staged_roots(staged, checkout, self.entries)
        self.assertEqual(roots, sorted(inputs.INSTALL_ROOTS))
        self.assertTrue((checkout / self.names[0]).is_file())
        with self.assertRaisesRegex(RuntimeError, "occupied"):
            inputs.install_staged_roots(staged, checkout, self.entries)

    def test_gzip_container_also_verifies_by_magic(self):
        self.archive = self.root / "tools.tar.gz"
        digest = self.build("gz")
        self.assertEqual(inputs.verify_archive(self.archive, self.path, digest)["compression"], "gz")

    def test_wrong_manifest_digest_changed_bytes_and_extra_entry_fail(self):
        digest = self.build()
        with self.assertRaisesRegex(RuntimeError, "manifest digest"):
            inputs.verify_archive(self.archive, self.path, "0" * 64)
        self.source.write_bytes(b"changed")
        with tarfile.open(self.root / "bad.tar.xz", "x:xz") as archive:
            info = tarfile.TarInfo(self.names[0])
            info.size, info.mode = 7, 0o755
            archive.addfile(info, io.BytesIO(b"changed"))
        with self.assertRaises(RuntimeError):
            inputs.verify_archive(self.root / "bad.tar.xz", self.path, digest)

    def test_entries_reject_absolute_links_cycles_and_special_modes(self):
        for broken in [{"a/link": {"kind": "symlink", "target": "/etc/passwd"}},
                       {"a/x": {"kind": "symlink", "target": "y"}, "a/y": {"kind": "symlink", "target": "x"}},
                       {"a/f": {"kind": "file", "sha256": "0" * 64, "bytes": 1, "mode": 0o4755}},
                       {"../escape": {"kind": "directory", "mode": 0o755}}]:
            with self.subTest(broken=broken), self.assertRaises(RuntimeError):
                inputs.entries_valid(broken)

    def test_assurance_cannot_be_upgraded(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["boundaries"]["clean_room"] = True
        digest = self.save(manifest)
        with self.assertRaisesRegex(RuntimeError, "assurance"):
            inputs.load_manifest(self.path, digest)

    def test_installation_roots_are_exact(self):
        with self.assertRaisesRegex(RuntimeError, "outside fixed roots"):
            inputs.installation_roots({"artifacts/boundary-check/other/bin/x": self.entries[self.names[0]]})
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            inputs.installation_roots({self.names[0]: self.entries[self.names[0]]})

    def test_cmake_stage_checks_pins_and_declared_hashes(self):
        files = {"CLI11.hpp": b"// cli\n", "gmp-6.3.0.tar.xz": b"gmp", "v1.8.1.tar.gz": None, "asio-1.36.0.tar.bz2": None}
        for name, top, mode in [("v1.8.1.tar.gz", "jsoncons-1.8.1", "w:gz"), ("asio-1.36.0.tar.bz2", "asio-1.36.0", "w:bz2")]:
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode=mode) as archive:
                directory = tarfile.TarInfo(top)
                directory.type, directory.mode = tarfile.DIRTYPE, 0o755
                archive.addfile(directory)
                info = tarfile.TarInfo(top + "/README")
                info.size, info.mode = 2, 0o644
                archive.addfile(info, io.BytesIO(b"hi"))
            files[name] = buffer.getvalue()
        manifest = {"schema_version": 1, "kind": "fixed-cmake-download-inputs-v1", "files": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "mode": 0o644,
                   "declaration": {"hash_algorithm": "SHA256", "digest": hashlib.sha256(data).hexdigest()}}
            for name, data in files.items()}}
        manifest_path = self.root / "cmake-manifest.json"
        manifest_path.write_bytes(json.dumps(manifest).encode())
        archive = self.root / "cmake.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o644
                tar.addfile(info, io.BytesIO(data))
        policy = {"fixed_inputs": {"cmake-downloads.tar.gz": {"sha256": inputs.sha(archive)},
                                   "cmake-downloads-manifest.json": {"sha256": inputs.sha(manifest_path)}}}
        result = inputs.stage_cmake(archive, manifest_path, self.root / "cmake-out", policy)
        self.assertEqual(result["status"], "staged")
        self.assertTrue((self.root / "cmake-out/sources/jsoncons/jsoncons-1.8.1/README").is_file())
        self.assertTrue((self.root / "cmake-out/build/gmp-prefix/src/gmp-6.3.0.tar.xz").is_file())
        self.assertIn("-DFETCHCONTENT_FULLY_DISCONNECTED:BOOL=ON", result["configure_options"])
        policy["fixed_inputs"]["cmake-downloads.tar.gz"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "unreviewed"):
            inputs.stage_cmake(archive, manifest_path, self.root / "cmake-out-2", policy)


if __name__ == "__main__":
    unittest.main()
