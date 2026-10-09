#!/usr/bin/env python3
"""Controller mechanics that need no toolchain: state identity, downloads,
environments, host preflight, stage inventory and the bootstrap retry."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("clean_room", HERE.parent / "clean_room.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CleanRoomTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="clean-room-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "checkout"
        self.out = self.root / MODULE.OUT_NAME
        self.out.mkdir(parents=True)
        self.state = {"schema_version": 1, "kind": "clean-room-state-v2", "repository": MODULE.REPOSITORY,
                      "candidate": "a" * 40, "canonical_checkout": str(self.root), "output": str(self.out)}

    def test_stage_inventory_is_the_policy_inventory(self):
        self.assertEqual(MODULE.STAGES, MODULE.POLICY["clean_room"]["stages"])
        self.assertEqual(len(MODULE.STAGES), 11)
        self.assertEqual(MODULE.STAGES[0], "checkout")
        self.assertEqual(set(MODULE.tool_paths(self.root)), set(MODULE.TOOLS))
        self.assertEqual(MODULE.tool_version_args("aeneas"), ["-version"])
        self.assertEqual(MODULE.tool_version_args("charon"), ["version"])

    def test_state_accepts_only_the_fixed_identity_and_output(self):
        with patch.object(MODULE, "CANONICAL", self.root):
            self.assertEqual(MODULE.checked_state(self.state), (self.root, self.out))
            for key, value in [("repository", "other/repo"), ("candidate", "short"), ("kind", "x"),
                               ("output", str(self.root / "artifacts/elsewhere"))]:
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    MODULE.checked_state({**self.state, key: value})

    def test_download_checks_hash_and_redacts_url(self):
        data = b"fixture input"
        digest = hashlib.sha256(data).hexdigest()

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False
        with patch.dict(MODULE.os.environ, {"WEEK6_INSTALL_MANIFEST_URL": "https://secret.invalid/t/x"}), \
                patch.object(MODULE.urllib.request, "urlopen", return_value=Response(data)):
            MODULE.download("WEEK6_INSTALL_MANIFEST_URL", self.out / "ok", digest)
            with self.assertRaisesRegex(RuntimeError, "hash differs"):
                MODULE.download("WEEK6_INSTALL_MANIFEST_URL", self.out / "bad", "0" * 64)
        with patch.dict(MODULE.os.environ, {"WEEK6_INSTALL_MANIFEST_URL": "https://secret.invalid/t/x"}), \
                patch.object(MODULE.urllib.request, "urlopen", side_effect=OSError("https://secret.invalid/t/x refused")):
            with self.assertRaises(RuntimeError) as caught:
                MODULE.download("WEEK6_INSTALL_MANIFEST_URL", self.out / "err", digest)
            self.assertNotIn("secret.invalid", str(caught.exception))
        with patch.dict(MODULE.os.environ, {"WEEK6_INSTALL_MANIFEST_URL": "http://plain.invalid/x"}):
            with self.assertRaisesRegex(RuntimeError, "non-HTTPS"):
                MODULE.download("WEEK6_INSTALL_MANIFEST_URL", self.out / "plain", digest)

    def test_environments_strip_injection_and_fix_proxy(self):
        base = MODULE.base_environment({"PATH": "/x", "LD_PRELOAD": "evil", "CARGO_HOME": "h", "HTTPS_PROXY": "http://p:1",
                                        "https_proxy": "", "WEEK6_INSTALL_ARCHIVE_URL": "https://s", "HOME": "/home/u"})
        self.assertEqual(base["PATH"], "/usr/bin:/bin")
        for key in ("LD_PRELOAD", "CARGO_HOME", "https_proxy", "WEEK6_INSTALL_ARCHIVE_URL"):
            self.assertNotIn(key, base)
        self.assertEqual((base["GIT_CONFIG_KEY_2"], base["GIT_CONFIG_VALUE_2"]), ("http.proxy", "http://p:1"))
        install = MODULE.stage_environment({"WEEK6_INSTALL_ARCHIVE_URL": "https://s", "WEEK6_DECODER_ARCHIVE_URL": "https://d"}, "install")
        self.assertEqual(install["WEEK6_INSTALL_ARCHIVE_URL"], "https://s")
        other = MODULE.stage_environment({"WEEK6_INSTALL_ARCHIVE_URL": "https://s"}, "regenerate")
        self.assertNotIn("WEEK6_INSTALL_ARCHIVE_URL", other)
        native = MODULE.stage_environment({}, "runtime")
        self.assertTrue(native["PATH"].startswith(str(MODULE.CANONICAL / "artifacts/boundary-check/isolated-rust-lean-ad7o1fsn")))
        self.assertIn("sail-install/bin", native["PATH"])
        self.assertEqual(native["RUSTUP_TOOLCHAIN"], MODULE.RUST_TOOLCHAIN)
        with self.assertRaises(RuntimeError):
            MODULE.stage_environment({}, "not-a-stage")

    def test_host_preflight_pins_binaries_and_rejects_network_probes(self):
        tool = self.out / "tool"
        tool.write_text("#!/bin/sh\necho fixture 1.0\n")
        tool.chmod(0o755)
        fetcher = self.out / "fetcher"
        fetcher.write_text("#!/bin/sh\necho 'info: syncing channel updates'\n")
        fetcher.chmod(0o755)
        release = self.out / "os-release"
        release.write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
        executables = {"tool": {"path": str(tool), "sha256": MODULE.sha(tool), "probe": ["--version"]}}
        report = MODULE.host_preflight(self.out, executables, release, "x86_64")
        self.assertEqual(report["executables"]["tool"]["version"], "fixture 1.0")
        (self.out / "host-preflight.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "network fetch"):
            MODULE.host_preflight(self.out, {"f": {"path": str(fetcher), "sha256": None, "probe": ["--version"]}}, release, "x86_64")
        with self.assertRaisesRegex(RuntimeError, "pinned host executable differs"):
            MODULE.host_preflight(self.out, {"tool": {**executables["tool"], "sha256": "0" * 64}}, release, "x86_64")
        with self.assertRaisesRegex(RuntimeError, "Ubuntu 24.04"):
            release.write_text("ID=debian\nVERSION_ID=12\n")
            MODULE.host_preflight(self.out, executables, release, "x86_64")

    def test_provider_requires_allowed_kind_digest_and_environment_id(self):
        good = {"CLEAN_ROOM_PROVIDER": "independent-ephemeral-vm", "CLEAN_ROOM_IMAGE": "img@sha256:" + "1" * 64,
                "CLEAN_ROOM_ENVIRONMENT_ID": "env-1"}
        with patch.dict(MODULE.os.environ, good, clear=True):
            row = MODULE.provider()
        self.assertEqual((row["kind"], row["image_digest"], row["ephemeral"]), ("independent-ephemeral-vm", "sha256:" + "1" * 64, True))
        for key, value in [("CLEAN_ROOM_PROVIDER", "laptop"), ("CLEAN_ROOM_IMAGE", "img"), ("CLEAN_ROOM_ENVIRONMENT_ID", "")]:
            with patch.dict(MODULE.os.environ, {**good, key: value}, clear=True), self.subTest(key=key), self.assertRaises(RuntimeError):
                MODULE.provider()

    def test_tree_digest_and_top_file_copy(self):
        tree = self.out / "gen"
        (tree / "a").mkdir(parents=True)
        (tree / "a/x.lean").write_text("x")
        first = MODULE.tree_digest(tree)
        (tree / "a/x.lean").write_text("y")
        self.assertNotEqual(first, MODULE.tree_digest(tree))
        source = self.out / "pc"
        source.mkdir()
        (source / "report.json").write_text("{}")
        (source / ".lock").write_text("")
        (source / "sub").mkdir()
        MODULE.copy_top_files(source, self.out / "lean")
        self.assertEqual(sorted(p.name for p in (self.out / "lean").iterdir()), ["report.json"])

    def test_new_output_creates_ignored_parents_in_a_fresh_checkout(self):
        root = self.root.parent / "fresh"
        root.mkdir()
        out = MODULE.new_output(root, root / MODULE.OUT_NAME)
        self.assertTrue(out.is_dir())
        for name in MODULE.IGNORED_EVIDENCE_PARENTS:
            self.assertTrue((root / "artifacts" / name).is_dir(), name)
        with self.assertRaises(RuntimeError):
            MODULE.new_output(root, root / MODULE.OUT_NAME)

    def test_bootstrap_checkout_retries_network_steps_only(self):
        calls = []

        def fake(argv, cwd, codes=(0,), env=None, timeout=21600):
            calls.append(argv[1] if argv[0].endswith("git") else argv[0])
            if argv[1:2] == ["clone"] and calls.count("clone") == 1:
                raise RuntimeError("command failed (exit 128): /usr/bin/git")
            return None
        canonical = self.root.parent / "canonical"
        canonical.mkdir()
        with patch.object(MODULE, "CANONICAL", canonical), patch.object(MODULE, "command", side_effect=fake):
            MODULE.bootstrap_checkout("a" * 40)
        self.assertEqual(calls.count("clone"), 2)
        self.assertEqual(calls.count("checkout"), 1)

    def test_parser_rejects_arbitrary_stages(self):
        with self.assertRaises(SystemExit):
            MODULE.parser().parse_args(["_stage", "--name", "worktree-audit", "--state", "x"])
        args = MODULE.parser().parse_args(["_stage", "--name", "tree-clean", "--state", "x"])
        self.assertEqual(args.name, "tree-clean")


if __name__ == "__main__":
    unittest.main()
