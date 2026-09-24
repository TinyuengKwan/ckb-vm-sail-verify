#!/usr/bin/env python3
import argparse
import importlib.util
import json
import hashlib
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("week6_release_package", HERE.parent / "week6_release_package.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CANDIDATE = "a" * 40
VERSION = "v1.0.0-test"
TOOL = b"fixture standalone tool archive\n"
TOOL_MANIFEST = b"fixture installation manifest\n"


class PackageTests(unittest.TestCase):
    def setUp(self):
        # These tests isolate archive/publication mechanics; the real offline
        # Git and signed restoration chain is exercised in test_week6_restore_release.
        for target in ("week6_restore_release.validate_sources", "week6_restore_release.check_archived_source",
                       "week6_release_assets.restoration_members"):
            mock = patch(target)
            mock.start()
            self.addCleanup(mock.stop)

    def policy(self):
        return {"repository": "fixture/repository", "release_package": {
            "approved_version": VERSION,
            "approved_delivery_profile": "A",
            "approved_signer_identity": "fixture-signer",
            "allowed_signers_path": "docs/release/release-allowed-signers",
            "signature_namespace": "fixture-release",
            "required_members": list(MODULE.PREFIXES) + ["SHA256SUMS", "MANIFEST.json"],
            "require_immutable_publication": True,
            "external_assets": {MODULE.assets.ASSET_NAME: {
                "size": len(TOOL), "sha256": hashlib.sha256(TOOL).hexdigest(),
                "manifest": {"path": "install/manifest.json", "sha256": hashlib.sha256(TOOL_MANIFEST).hexdigest()}}},
        }}

    def prepare(self, root, suffix=""):
        inputs = root / ("inputs" + suffix)
        inputs.mkdir()
        snapshot = {"snapshot_sha256": "b" * 64}
        (inputs / "source-snapshot.json").write_text(json.dumps(snapshot) + "\n")
        members = []
        for i, name in enumerate([
            "source/source-capsule.tar.gz", "install/manifest.json",
            "evidence/ci-evidence.tar.gz", "docs/coverage.md", "docs/non-goals.md"
        ]):
            source = inputs / ("payload-" + str(i))
            source.write_bytes(TOOL_MANIFEST if name == "install/manifest.json" else (name + "\n").encode())
            members.append({"path": name, "source": source.name, "sha256": MODULE.sha(source)})
        descriptor = {
            "schema_version": 2, "kind": "release-package-inputs-v2",
            "candidate": CANDIDATE, "version": VERSION, "delivery_profile": "A",
            "source_snapshot": {"path": "source-snapshot.json",
                                "sha256": MODULE.sha(inputs / "source-snapshot.json")},
            "coverage": "docs/coverage.md", "non_goals": "docs/non-goals.md", "members": members,
            "external_assets": {MODULE.assets.ASSET_NAME: {"source": "tool.xz", "sha256": hashlib.sha256(TOOL).hexdigest()}},
        }
        (inputs / "tool.xz").write_bytes(TOOL)
        descriptor_path = inputs / "inputs.json"
        descriptor_path.write_text(json.dumps(descriptor) + "\n")
        args = argparse.Namespace(candidate=CANDIDATE, version=VERSION, delivery_profile="A",
                                  input_root=inputs, inputs=descriptor_path, out=root / ("out" + suffix))
        return args, descriptor

    def test_builds_required_deterministic_package(self):
        with tempfile.TemporaryDirectory() as first_name, tempfile.TemporaryDirectory() as second_name:
            first, second = Path(first_name), Path(second_name)
            a, _ = self.prepare(first)
            b, _ = self.prepare(second)
            ra = MODULE.build(a, self.policy(), verify_current=False)
            rb = MODULE.build(b, self.policy(), verify_current=False)
            self.assertEqual(ra["archive"]["sha256"], rb["archive"]["sha256"])
            archive = a.out / ra["archive"]["path"]
            with tarfile.open(archive, "r:gz") as stream:
                names = [member.name.rstrip("/") + "/" if member.isdir() else member.name
                         for member in stream.getmembers()]
                archived_manifest = stream.extractfile("MANIFEST.json").read()
            self.assertTrue(set(MODULE.PREFIXES) <= set(names))
            self.assertIn("SHA256SUMS", names)
            self.assertEqual(archived_manifest, (a.out / "built/MANIFEST.json").read_bytes())
            self.assertFalse(ra["boundaries"]["published"])
            self.assertNotIn("install/" + MODULE.assets.ASSET_NAME, names)
            self.assertEqual(json.loads(archived_manifest)["external_assets"], self.policy()["release_package"]["external_assets"])
            self.assertEqual((a.out / ra["external_assets"][MODULE.assets.ASSET_NAME]["path"]).read_bytes(), TOOL)

    def test_rejects_changed_external_tool(self):
        with tempfile.TemporaryDirectory() as name:
            args, _ = self.prepare(Path(name))
            (args.input_root / "tool.xz").write_bytes(b"x" * len(TOOL))
            with self.assertRaisesRegex(RuntimeError, "external tool asset bytes differ"):
                MODULE.build(args, self.policy(), verify_current=False)
            self.assertFalse(args.out.exists())

    def test_rejects_missing_extra_or_traversing_external_asset(self):
        for mode in ("missing", "extra", "traversal"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as name:
                args, descriptor = self.prepare(Path(name))
                if mode == "missing":
                    descriptor["external_assets"] = {}
                elif mode == "extra":
                    descriptor["external_assets"]["other.xz"] = descriptor["external_assets"][MODULE.assets.ASSET_NAME]
                else:
                    descriptor["external_assets"][MODULE.assets.ASSET_NAME]["source"] = "../tool.xz"
                args.inputs.write_text(json.dumps(descriptor))
                with self.assertRaises(RuntimeError):
                    MODULE.build(args, self.policy(), verify_current=False)
                self.assertFalse(args.out.exists())

    def test_rejects_unsigned_installation_manifest_substitution(self):
        with tempfile.TemporaryDirectory() as name:
            args, descriptor = self.prepare(Path(name))
            row = next(row for row in descriptor["members"] if row["path"] == "install/manifest.json")
            (args.input_root / row["source"]).write_bytes(b"another manifest")
            row["sha256"] = MODULE.sha(args.input_root / row["source"])
            args.inputs.write_text(json.dumps(descriptor))
            with self.assertRaisesRegex(RuntimeError, "installation manifest binding differs"):
                MODULE.build(args, self.policy(), verify_current=False)

    def test_exclusive_asset_size_limit(self):
        for size in (0, True, MODULE.assets.MAX_ASSET_BYTES, MODULE.assets.MAX_ASSET_BYTES + 1):
            with self.subTest(size=size), self.assertRaises(RuntimeError):
                MODULE.assets.size_ok(size)
        MODULE.assets.size_ok(MODULE.assets.MAX_ASSET_BYTES - 1)

    def test_rejects_incomplete_policy_approval(self):
        with tempfile.TemporaryDirectory() as name:
            args, _ = self.prepare(Path(name))
            policy = self.policy()
            policy["release_package"]["approved_version"] = None
            with self.assertRaisesRegex(RuntimeError, "approvals incomplete"):
                MODULE.build(args, policy, verify_current=False)

    def test_rejects_missing_required_prefix(self):
        with tempfile.TemporaryDirectory() as name:
            args, value = self.prepare(Path(name))
            value["members"] = [row for row in value["members"] if not row["path"].startswith("install/")]
            args.inputs.write_text(json.dumps(value) + "\n")
            with self.assertRaisesRegex(RuntimeError, "prefix absent"):
                MODULE.build(args, self.policy(), verify_current=False)

    def test_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as name:
            args, value = self.prepare(Path(name))
            value["members"][0]["source"] = "../outside"
            args.inputs.write_text(json.dumps(value) + "\n")
            with self.assertRaisesRegex(RuntimeError, "unsafe package path"):
                MODULE.build(args, self.policy(), verify_current=False)

    def test_rejects_changed_member(self):
        with tempfile.TemporaryDirectory() as name:
            args, value = self.prepare(Path(name))
            (args.input_root / value["members"][0]["source"]).write_text("changed\n")
            with self.assertRaisesRegex(RuntimeError, "input hash differs"):
                MODULE.build(args, self.policy(), verify_current=False)

    def test_rejects_existing_output(self):
        with tempfile.TemporaryDirectory() as name:
            args, _ = self.prepare(Path(name))
            args.out.mkdir()
            with self.assertRaisesRegex(RuntimeError, "new package output"):
                MODULE.build(args, self.policy(), verify_current=False)

    def test_records_but_does_not_publish_existing_immutable_release(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            args, _ = self.prepare(root)
            result = MODULE.build(args, self.policy(), verify_current=False)
            archive = args.out / result["archive"]["path"]
            signature = Path(str(archive) + ".sig")
            signature.write_text("fixture signature\n")
            remote = {
                "id": 99, "tag_name": VERSION, "draft": False, "immutable": True,
                "html_url": "https://example.invalid/release", "published_at": "2026-09-14T00:00:00Z",
                "assets": [
                    {"id": 1, "name": archive.name, "state": "uploaded",
                     "size": archive.stat().st_size, "digest": "sha256:" + MODULE.sha(archive),
                     "browser_download_url": "https://example.invalid/archive"},
                    {"id": 2, "name": signature.name, "state": "uploaded",
                     "size": signature.stat().st_size, "digest": "sha256:" + MODULE.sha(signature),
                     "browser_download_url": "https://example.invalid/signature"},
                    {"id": 3, "name": MODULE.assets.ASSET_NAME, "state": "uploaded",
                     "size": len(TOOL), "digest": "sha256:" + hashlib.sha256(TOOL).hexdigest(),
                     "browser_download_url": "https://example.invalid/tool"},
                ],
            }

            def command(directory, label, argv):
                stdout, stderr = directory / (label + ".stdout"), directory / (label + ".stderr")
                if label == "release-remote-query":
                    stdout.write_text(json.dumps(remote))
                else:
                    target = directory / argv[4]
                    target.write_bytes(TOOL if argv[-1] == "https://example.invalid/tool" else archive.read_bytes())
                    stdout.write_text("")
                stderr.write_text("")
                return {"argv": argv, "exit_code": 0,
                        "stdout": MODULE.ref(directory, stdout), "stderr": MODULE.ref(directory, stderr)}

            record_args = argparse.Namespace(package_dir=args.out, release_id=99)
            original_read_text = Path.read_text
            allowed = MODULE.ROOT / "docs/release/release-allowed-signers"

            def read_text(path, *read_args, **read_kwargs):
                if path == allowed:
                    return "fixture-signer ssh-ed25519 AAAAfixture\n"
                return original_read_text(path, *read_args, **read_kwargs)

            with patch.object(MODULE.external, "load_policy", return_value=self.policy()), \
                 patch.object(MODULE, "run_command", side_effect=command), \
                 patch.object(MODULE.external, "current_snapshot", return_value={
                     "snapshot_sha256": "b" * 64}), \
                 patch.object(MODULE.external, "query_json", return_value=remote), \
                 patch.object(MODULE.external, "verify_ssh_signature"), \
                 patch("pathlib.Path.read_text", new=read_text):
                accepted = MODULE.record(record_args)
            self.assertTrue(accepted["publication_verified"])
            self.assertTrue(accepted["download_verified"])
            self.assertTrue(accepted["external_assets_verified"])
            report = json.loads((args.out / "report.json").read_text())
            self.assertEqual(report["publication"]["remote_query"]["argv"], [
                "gh", "api", "--hostname", "github.com", "repos/fixture/repository/releases/99"])
            self.assertEqual(report["publication"]["signature_asset_url"],
                             "https://example.invalid/signature")
            self.assertEqual(report["download"]["argv"][:4],
                             ["curl", "--fail", "--location", "--output"])
            self.assertFalse(report["boundaries"]["release_claimed"])


if __name__ == "__main__":
    unittest.main()
