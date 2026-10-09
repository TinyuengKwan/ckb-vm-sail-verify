#!/usr/bin/env python3
"""Build, sign (real SSH key), restore offline, and record against a faked
GitHub release with a real SSH-signed tag.  Fixture inputs only."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_release as audit
import fixed_inputs
import release_common as common
import release_package as package
import test_source_capsule as capsule_fixture

TOOL_ROOTS = ["artifacts/boundary-check/" + name + "/bin/tool" for name in fixed_inputs.INSTALL_ROOTS]


class ReleasePackageTests(unittest.TestCase):
    git = capsule_fixture.CapsuleTests.git
    commit = capsule_fixture.CapsuleTests.commit

    def setUp(self):
        capsule_fixture.CapsuleTests.setUp(self)
        self.key = self.base / "fixture-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        self.inputs = self.base / "inputs"
        self.inputs.mkdir()
        tiny = self.inputs / "tiny-tool"
        tiny.write_bytes(b"fixture tool")
        tiny.chmod(0o755)
        entries = {name: fixed_inputs.identity(tiny) for name in TOOL_ROOTS}
        canonical = self.base / "canonical-checkout"
        installation = {"schema_version": 1, "kind": "extra-fixed-prefix-installations-v1", "canonical_checkout": str(canonical),
                        "inputs": {"fixture": True}, "required_external": ["host"],
                        "boundaries": {k: False for k in ["clean_room", "release", "kernel_execution", "relocatable", "host_closure_complete"]},
                        "entries": entries}
        (self.inputs / "manifest.json").write_bytes(common.json_bytes(installation))
        (self.inputs / "rebuilt-decoder-candidate.tar.gz").write_bytes(b"fixture decoder")
        (self.inputs / "cmake-downloads.tar.gz").write_bytes(b"fixture cmake")
        (self.inputs / "cmake-downloads-manifest.json").write_bytes(b"fixture cmake manifest")
        tool = self.inputs / "extra-installations.tar.xz"
        with tarfile.open(tool, "x:xz", format=tarfile.PAX_FORMAT) as archive:
            for name in sorted(entries):
                info = tarfile.TarInfo(name)
                info.uid = info.gid = info.mtime = 0
                info.size, info.mode = 12, 0o755
                archive.addfile(info, io.BytesIO(b"fixture tool"))
        pins = {name: {"sha256": common.sha(self.inputs / name)} for name in package.INSTALL_MEMBERS.values()}
        pins["extra-installations.tar.xz"] = {"size": tool.stat().st_size, "sha256": common.sha(tool)}
        self.policy = {"schema_version": 2, "kind": "release-policy-v2", "repository": "fixture/repo", "version": "fixture-0.1.0",
                       "canonical_checkout": str(canonical),
                       "signer": {"identity": "fixture@example.invalid", "allowed_signers": "docs/release/release-allowed-signers",
                                  "namespace": "ckb-vm-sail-release"},
                       "fixed_inputs": pins, "clean_room": {"generated_roots": []},
                       "package": {"required_members": ["source/", "install/", "evidence/", "docs/", "SHA256SUMS", "MANIFEST.json"],
                                   "tool_asset": "extra-installations.tar.xz", "docs": ["README.md", "docs/coverage.md"]},
                       "public_claims": {"documents": ["README.md"], "coverage_status_values": [], "forbidden": ["x"]}}
        (self.root / "docs/release").mkdir(parents=True)
        (self.root / "docs/release/policy.json").write_bytes(common.json_bytes(self.policy))
        (self.root / "docs/release/release-allowed-signers").write_text(
            'fixture@example.invalid namespaces="ckb-vm-sail-release" ' + self.key.with_suffix(".pub").read_text())
        (self.root / "docs/coverage.md").write_text("fixture coverage\n")
        (self.root / ".gitignore").write_text("artifacts/\n")
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "decoder_rebuilt_inputs.py").write_text(
            'import sys\nfrom pathlib import Path\n'
            'if "--install" in sys.argv:\n'
            '    assert Path(sys.argv[sys.argv.index("--install")+1]).read_bytes() == b"fixture decoder"\n'
            '    Path(sys.argv[sys.argv.index("--destination")+1]).mkdir(parents=True)\n'
            'else:\n    assert Path(sys.argv[sys.argv.index("--verify")+1]).is_dir()\n')
        (scripts / "fixed_inputs.py").write_text(
            'import sys\nfrom pathlib import Path\n'
            'assert Path(sys.argv[sys.argv.index("--archive")+1]).read_bytes() == b"fixture cmake"\n'
            'Path(sys.argv[sys.argv.index("--out")+1]).mkdir(parents=True)\n')
        self.commit(self.root)
        self.candidate = self.git(self.root, "rev-parse", "HEAD").strip()
        self.evidence = self.base / "evidence"
        (self.evidence / "run").mkdir(parents=True)
        (self.evidence / "run/report.json").write_text("{}\n")
        self.out = self.base / "package"
        args = argparse.Namespace(candidate=self.candidate, inputs=self.inputs, evidence=self.evidence, out=self.out)
        self.build = package.build(args, root=self.root)
        self.archive = self.out / self.build["archive"]["path"]
        self.tool = self.out / self.build["tool_asset"]["path"]
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(self.key), "-n", "ckb-vm-sail-release", str(self.archive)],
                       check=True, capture_output=True)
        self.signature = Path(str(self.archive) + ".sig")

    def test_build_is_complete_and_deterministic(self):
        names, _ = common.tar_inventory(self.archive)
        for member in ["source/source-capsule.tar.gz", "install/manifest.json", "docs/README.md", "docs/coverage.md",
                       "evidence/run/report.json", "SHA256SUMS", "MANIFEST.json"]:
            self.assertIn(member, names)
        manifest = json.loads(common.archive_member_bytes(self.archive, "MANIFEST.json"))
        self.assertEqual(manifest["version"], "fixture-0.1.0")
        self.assertEqual(manifest["tool_asset"]["name"], "extra-installations.tar.xz")
        again = package.build(argparse.Namespace(candidate=self.candidate, inputs=self.inputs, evidence=self.evidence,
                                                 out=self.base / "package-2"), root=self.root)
        self.assertEqual(again["archive"]["sha256"], self.build["archive"]["sha256"])

    def test_restore_authenticates_and_restores_source_and_tools(self):
        result = package.restore(self.archive, self.signature, self.tool, self.candidate, self.base / "restored", "staging", self.root)
        self.assertEqual(result["status"], "inputs_restored")
        checkout = Path(result["checkout"])
        self.assertEqual(package.source_snapshot.capture(checkout), package.source_snapshot.capture(self.root))
        self.assertEqual(len(result["installation_roots"]), 5)
        self.assertEqual([row["name"] for row in result["stages"]], ["decoder-install", "decoder-verify", "cmake-stage"])

    def test_tampered_inputs_and_untrusted_key_are_refused_before_output(self):
        bad = self.base / "bad.tar.gz"
        bad.write_bytes(self.archive.read_bytes() + b"tampered")
        with self.assertRaises(RuntimeError):
            package.restore(bad, self.signature, self.tool, self.candidate, self.base / "r1", "staging", self.root)
        with self.assertRaises(RuntimeError):
            package.restore(self.archive, self.signature, self.tool, "0" * 40, self.base / "r2", "staging", self.root)
        (self.root / "docs/release/release-allowed-signers").write_text("# nobody\n")
        with self.assertRaisesRegex(RuntimeError, "signer|signature"):
            package.restore(self.archive, self.signature, self.tool, self.candidate, self.base / "r3", "staging", self.root)
        for name in ("r1", "r2", "r3"):
            self.assertFalse((self.base / name).exists())

    def test_record_with_signed_tag_and_faked_immutable_release(self):
        env = {**self.env, "GIT_AUTHOR_NAME": "o", "GIT_AUTHOR_EMAIL": "o@o", "GIT_COMMITTER_NAME": "o", "GIT_COMMITTER_EMAIL": "o@o"}
        subprocess.run(["git", "-c", "gpg.format=ssh", "-c", "user.signingkey=" + str(self.key.with_suffix(".pub")),
                        "tag", "-s", "-m", "release", "fixture-0.1.0", self.candidate], cwd=self.root, env=env, check=True)
        remote = {"id": 777, "tag_name": "fixture-0.1.0", "draft": False, "immutable": True, "html_url": "https://example.invalid/r",
                  "published_at": "2026-10-10T00:00:00Z", "assets": [
                      {"name": p.name, "state": "uploaded", "size": p.stat().st_size, "digest": "sha256:" + common.sha(p),
                       "id": i + 1, "browser_download_url": "https://example.invalid/" + p.name}
                      for i, p in enumerate([self.archive, self.signature, self.tool])]}
        real_run = common.run_command

        def fake_run(out, label, argv, cwd, env=None, timeout=1800):
            out = Path(out)
            if argv[0] == "git" and argv[1] == "fetch":
                body = b""
            elif argv[0] == "gh":
                body = json.dumps(remote).encode()
            elif argv[0] == "curl":
                target = Path(argv[argv.index("--output") + 1])
                source = {p.name: p for p in [self.archive, self.signature, self.tool]}[Path(argv[-1]).name]
                target.write_bytes(source.read_bytes())
                body = b""
            else:
                return real_run(out, label, argv, cwd, env=env, timeout=timeout)
            a, b = out / (label + ".stdout"), out / (label + ".stderr")
            a.write_bytes(body)
            b.write_bytes(b"")
            return {"name": label, "argv": [str(x) for x in argv], "cwd": str(cwd), "exit_code": 0,
                    "stdout": common.ref(out, a), "stderr": common.ref(out, b)}
        with patch.object(common, "run_command", side_effect=fake_run), patch.object(common, "query_json", return_value=remote):
            result = package.record(argparse.Namespace(package_dir=self.out, release_id=777), root=self.root)
        self.assertEqual((result["version"], result["release_id"], result["tag"]["verified"]), ("fixture-0.1.0", 777, True))
        self.assertEqual(result["source_snapshot_sha256"], self.build["source_snapshot_sha256"])
        # A tag signed by an unapproved key is refused by the validator.
        (self.root / "docs/release/release-allowed-signers").write_text("# nobody\n")
        with patch.object(common, "query_json", return_value=remote), self.assertRaisesRegex(RuntimeError, "signer|signature"):
            audit.check_release(self.out / "report.json", self.candidate, self.root)


if __name__ == "__main__":
    unittest.main()
