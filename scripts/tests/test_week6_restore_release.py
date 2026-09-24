"""Real SSH + offline Git + tar/xz restoration; tiny tool/decoder fixtures only.

Fixture decoder/CMake CLIs check their invocation and create ignored outputs;
their production admissions have dedicated tests and a real-material rehearsal.
No fixture key is accepted by the repository's production signer policy.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import week6_release_assets as assets
import week6_release_package as package
import week6_restore_release as restore
import test_week6_source_capsule as capsule_fixture


class RestoreTests(unittest.TestCase):
    git = capsule_fixture.CapsuleTests.git
    commit = capsule_fixture.CapsuleTests.commit

    def setUp(self):
        capsule_fixture.CapsuleTests.setUp(self)
        self.key = self.base / "fixture-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        policy = restore.external.load_policy()
        cfg = policy["release_package"]
        cfg.update(approved_version="fixture-v1", approved_signer_identity="fixture@example.invalid")
        signer = self.root / cfg["allowed_signers_path"]
        signer.parent.mkdir(parents=True)
        signer.write_text('fixture@example.invalid namespaces="ckb-vm-sail-release" ' +
                          self.key.with_suffix(".pub").read_text())
        (self.root / ".gitignore").write_text("artifacts/\n")
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "decoder_rebuilt_inputs.py").write_text(
            'import sys\nfrom pathlib import Path\n'
            'def require(value):\n if not value: raise RuntimeError("fixture input differs")\n'
            'if "--install" in sys.argv:\n'
            ' require(Path(sys.argv[sys.argv.index("--install")+1]).read_bytes()==b"fixture decoder")\n'
            ' Path(sys.argv[sys.argv.index("--destination")+1]).mkdir(parents=True)\n'
            'else:\n require(Path(sys.argv[sys.argv.index("--verify")+1]).is_dir())\n')
        (scripts / "stage_fixed_cmake_inputs.py").write_text(
            'import sys\nfrom pathlib import Path\n'
            'def require(value):\n if not value: raise RuntimeError("fixture input differs")\n'
            'require(Path(sys.argv[sys.argv.index("--archive")+1]).read_bytes()==b"fixture cmake")\n'
            'require(Path(sys.argv[sys.argv.index("--manifest")+1]).read_bytes()==b"fixture cmake manifest")\n'
            'Path(sys.argv[sys.argv.index("--out")+1]).mkdir(parents=True)\n')
        self.inputs = self.base / "inputs"
        self.inputs.mkdir()
        tiny = self.inputs / "tiny-tool"
        tiny.write_bytes(b"fixture tool")
        tiny.chmod(0o755)
        names = ["artifacts/boundary-check/" + name + "/bin/tool" for name in restore.fixed.INSTALL_ROOTS]
        entries = {name: restore.bundle.identity(tiny) for name in names}
        installation = {"schema_version": 1, "kind": "extra-fixed-prefix-installations-v1",
            "canonical_checkout": str(restore.fixed.CANONICAL), "inputs": {"fixture": "not production"},
            "required_external": ["host dependencies"], "boundaries": {key: False for key in
                ["clean_room", "release", "kernel_execution", "relocatable", "host_closure_complete"]}, "entries": entries}
        self.files = {}
        bodies = {"install/manifest.json": package.json_bytes(installation),
            "install/rebuilt-decoder-candidate.tar.gz": b"fixture decoder",
            "install/cmake-downloads.tar.gz": b"fixture cmake",
            "install/cmake-downloads-manifest.json": b"fixture cmake manifest",
            "docs/RESTORE.md": b"fixture guide", "docs/coverage.md": b"fixture coverage",
            "docs/non-goals.md": b"fixture limitations", "evidence/fixture.json": b"{}"}
        for index, (name, body) in enumerate(bodies.items()):
            p = self.inputs / str(index)
            p.write_bytes(body)
            self.files[name] = p
        tool = self.inputs / assets.ASSET_NAME
        restore.bundle.write_archive(tool, {name: tiny for name in names}, entries)
        cfg["external_assets"] = {assets.ASSET_NAME: {"size": tool.stat().st_size, "sha256": assets.sha(tool),
            "manifest": {"path": "install/manifest.json", "sha256": assets.sha(self.files["install/manifest.json"])}}}
        policy_path = self.root / restore.external.POLICY
        policy_path.write_bytes(package.json_bytes(policy))
        self.policy = policy
        pins = {name: assets.sha(self.files[name]) for name in assets.RESTORE_PINS}
        mock = patch.dict(assets.RESTORE_PINS, pins)
        mock.start()
        self.addCleanup(mock.stop)
        self.commit(self.root)
        self.candidate = self.git(self.root, "rev-parse", "HEAD").strip()
        self.snapshot = restore.source_snapshot.capture(self.root)
        source_out = self.inputs / "source"
        restore.capsule.create(self.root, self.candidate, source_out)
        self.files[assets.SOURCE_CAPSULE] = source_out / "source-capsule.tar.gz"
        (self.inputs / "snapshot.json").write_bytes(package.json_bytes(self.snapshot))
        self.descriptor = {"schema_version": 2, "kind": "release-package-inputs-v2", "candidate": self.candidate,
            "version": "fixture-v1", "delivery_profile": "A", "source_snapshot": {
                "path": "snapshot.json", "sha256": assets.sha(self.inputs / "snapshot.json")},
            "coverage": "docs/coverage.md", "non_goals": "docs/non-goals.md",
            "members": [{"path": n, "source": p.relative_to(self.inputs).as_posix(), "sha256": assets.sha(p)}
                        for n, p in self.files.items()],
            "external_assets": {assets.ASSET_NAME: {"source": tool.name, "sha256": assets.sha(tool)}}}
        (self.inputs / "descriptor.json").write_bytes(package.json_bytes(self.descriptor))
        import argparse
        args = argparse.Namespace(candidate=self.candidate, version="fixture-v1", delivery_profile="A",
            input_root=self.inputs, inputs=self.inputs / "descriptor.json", out=self.base / "built")
        with patch.object(package, "ROOT", self.root):
            report = package.build(args, self.policy)
        self.archive = args.out / report["archive"]["path"]
        self.tool = args.out / report["external_assets"][assets.ASSET_NAME]["path"]
        self.sign(self.archive)
        self.signature = Path(str(self.archive) + ".sig")

    def sign(self, path, namespace="ckb-vm-sail-release"):
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(self.key), "-n", namespace, str(path)],
                       check=True, capture_output=True)

    def run_restore(self, **changes):
        args = dict(archive=self.archive, signature=self.signature, tool=self.tool, candidate=self.candidate,
                    out=self.base / "restored", root=self.root)
        args.update(changes)
        return restore.restore(**args)

    def test_real_signature_offline_git_and_both_assets_roundtrip(self):
        result = self.run_restore()
        self.assertTrue(result["signature_verified"])
        self.assertEqual(restore.source_snapshot.capture(Path(result["checkout"])), self.snapshot)
        self.assertEqual(len(result["installation_roots"]), 5)
        self.assertEqual(len(result["stages"]), 3)
        for flag in ("publication_verified", "proofs_executed", "week6_closed", "release_claimed",
                     "operational_toolchain_claimed", "third_party_reproduced"):
            self.assertIs(result[flag], False)

    def test_changed_primary_tool_signature_or_candidate_rejected_before_output(self):
        for case in ("primary", "tool", "signature", "candidate"):
            with self.subTest(case=case):
                changes = {}
                if case == "candidate":
                    changes["candidate"] = "0" * 40
                else:
                    key = {"primary": "archive", "tool": "tool", "signature": "signature"}[case]
                    original = getattr(self, "archive" if case == "primary" else case)
                    bad = self.base / (case + ".bad")
                    bad.write_bytes(original.read_bytes() + b"tampered")
                    # Trailing whitespace can be valid SSH armor; corrupt its body.
                    if case == "signature": bad.write_bytes(b"not a signature")
                    changes[key] = bad
                with self.assertRaises(RuntimeError): self.run_restore(**changes)
                self.assertFalse((self.base / "restored").exists())

    def test_wrong_namespace_and_untrusted_key_fail(self):
        wrong = self.base / "wrong-namespace.tar.gz"
        wrong.write_bytes(self.archive.read_bytes())
        self.sign(wrong, "other-namespace")
        with self.assertRaisesRegex(RuntimeError, "signature"):
            self.run_restore(signature=Path(str(wrong) + ".sig"))
        signer = self.root / self.policy["release_package"]["allowed_signers_path"]
        signer.write_text("# no trusted signer\n")
        with self.assertRaisesRegex(RuntimeError, "signature"): self.run_restore()
        self.assertFalse((self.base / "restored").exists())

    def test_signed_cross_snapshot_or_missing_closure_fails(self):
        for case in ("snapshot", "capsule", "decoder", "tool-binding"):
            manifest = assets.primary_manifest(self.archive)
            files = {**self.files, "SHA256SUMS": self.archive.parent / "SHA256SUMS"}
            if case == "snapshot": manifest["source_snapshot_sha256"] = "0" * 64
            elif case == "tool-binding": manifest["external_assets"][assets.ASSET_NAME]["sha256"] = "0" * 64
            else:
                name = assets.SOURCE_CAPSULE if case == "capsule" else "install/rebuilt-decoder-candidate.tar.gz"
                files.pop(name)
                manifest["members"] = [row for row in manifest["members"] if row["path"] != name]
            bad = self.base / (case + ".tar.gz")
            package.archive(bad, files, package.json_bytes(manifest))
            self.sign(bad)
            with self.subTest(case=case), self.assertRaises(RuntimeError):
                self.run_restore(archive=bad, signature=Path(str(bad) + ".sig"))
            self.assertFalse((self.base / "restored").exists())

    def test_existing_canonical_and_aliased_output_are_never_overwritten(self):
        occupied = self.base / "occupied"
        occupied.mkdir()
        (occupied / "user-file").write_text("preserve")
        with patch.object(restore.fixed, "CANONICAL", occupied), self.assertRaises(RuntimeError):
            self.run_restore(mode="canonical")
        link = self.base / "link"
        link.symlink_to(occupied, target_is_directory=True)
        with self.assertRaises(RuntimeError): self.run_restore(out=link / "new")
        self.assertEqual((occupied / "user-file").read_text(), "preserve")
        self.assertFalse((self.base / "restored").exists())


if __name__ == "__main__":
    unittest.main()
