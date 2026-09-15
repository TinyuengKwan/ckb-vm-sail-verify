#!/usr/bin/env python3
import argparse
from contextlib import redirect_stderr
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
SPEC = importlib.util.spec_from_file_location(
    "week6_clean_room", HERE.parent / "week6_clean_room.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CleanRoomTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="week6-clean-room-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "checkout"
        self.out = self.root / "artifacts/boundary-check/week6-clean-room"
        self.out.mkdir(parents=True)
        self.policy = self.root / "docs/release/week6-review-policy-v1.json"
        self.policy.parent.mkdir(parents=True)
        self.policy.write_text("{}\n")
        self.state = {
            "schema_version": 1, "kind": "week6-clean-room-state-v1",
            "repository": MODULE.REPOSITORY, "candidate": "a" * 40,
            "canonical_checkout": str(self.root),
            "install_archive_sha256": MODULE.INSTALL_ARCHIVE_SHA,
            "install_manifest_sha256": MODULE.INSTALL_MANIFEST_SHA,
            "decoder_archive_sha256": MODULE.DECODER_ARCHIVE_SHA,
            "review_policy": "docs/release/week6-review-policy-v1.json",
            "output": str(self.out),
        }

    def check_state(self, value=None):
        with patch.object(MODULE, "CANONICAL", self.root):
            return MODULE.checked_config(self.state if value is None else value)

    def test_fixed_stage_inventory_matches_external_contract(self):
        self.assertEqual(MODULE.REQUIRED_STAGES, [
            "recursive-checkout", "verify-source-snapshot", "install-rust", "install-sail",
            "install-aeneas-charon", "install-lean", "install-rocq", "rebuild-rust-model",
            "rebuild-sail-model", "rust-tests", "runtime-differential", "mutation-matrix",
            "lean-kernel", "rocq-spike", "worktree-audit", "public-claims",
        ])
        self.assertEqual(set(MODULE.TOOL_STAGE), {"rust", "sail", "aeneas", "charon", "lean", "rocq"})
        self.assertEqual(MODULE.tool_version_args("aeneas"), ["-version"])
        self.assertEqual(MODULE.tool_version_args("charon"), ["version"])
        self.assertEqual(MODULE.tool_version_args("lean"), ["--version"])
        self.assertEqual(MODULE.SECRET_URLS, {"WEEK6_INSTALL_ARCHIVE_URL",
                                             "WEEK6_INSTALL_MANIFEST_URL",
                                             "WEEK6_DECODER_ARCHIVE_URL"})
        environment = ({name: "secret" for name in MODULE.SECRET_URLS} |
                       {"PATH": "/attacker", "PYTHONPATH": "/attacker", "BASH_ENV": "/attacker",
                        "LD_PRELOAD": "/attacker.so", "RUSTC_WRAPPER": "/attacker", "HTTP_PROXY": "proxy"})
        rust = MODULE.stage_environment(environment, "install-rust")
        self.assertEqual({name for name in MODULE.SECRET_URLS if name in rust},
                         {"WEEK6_INSTALL_ARCHIVE_URL", "WEEK6_INSTALL_MANIFEST_URL"})
        aeneas = MODULE.stage_environment(environment, "install-aeneas-charon")
        self.assertEqual({name for name in MODULE.SECRET_URLS if name in aeneas},
                         {"WEEK6_DECODER_ARCHIVE_URL"})
        lean = MODULE.stage_environment(environment, "lean-kernel")
        self.assertFalse(MODULE.SECRET_URLS & set(lean))
        for name in ["PYTHONPATH", "BASH_ENV", "LD_PRELOAD", "RUSTC_WRAPPER"]:
            self.assertNotIn(name, lean)
        self.assertEqual(lean["PATH"], "/usr/bin:/bin")
        self.assertEqual(lean["HTTP_PROXY"], "proxy")
        self.assertEqual(lean["GIT_TERMINAL_PROMPT"], "0")
        with patch.object(MODULE, "CANONICAL", self.root):
            native = MODULE.stage_environment(environment, "runtime-differential")
        rustup = self.root / "artifacts/boundary-check/isolated-rust-lean-ad7o1fsn/rustup"
        self.assertEqual(native["RUSTUP_HOME"], str(rustup))
        self.assertEqual(native["RUSTUP_TOOLCHAIN"], MODULE.RUST_TOOLCHAIN)
        self.assertTrue(native["PATH"].startswith(str(rustup / "toolchains" / MODULE.RUST_TOOLCHAIN / "bin")))
        self.assertTrue(native["CARGO_HOME"].endswith("week6-native-clean-room/runtime-cargo-home"))
        host = self.root / "host"; host.mkdir()
        executable = host / "opam"
        executable.write_text("#!/bin/sh\nprintf 'fixture-opam 1.0\\n'\n")
        executable.chmod(0o755)
        release = host / "os-release"; release.write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
        preflight = MODULE.host_preflight(self.out, {"opam": {
            "path": str(executable), "sha256": MODULE.sha(executable), "probe": ["--version"]}},
            release, "x86_64")
        self.assertEqual(preflight["status"], "compatible_host_commands_verified")
        self.assertEqual(preflight["executables"]["opam"]["version"], "fixture-opam 1.0")
        self.assertFalse(preflight["boundaries"]["host_closure_complete"])
        sys.path.insert(0, str(HERE.parent))
        import release_public_claims
        self.assertEqual(MODULE.PUBLIC_BOUNDARIES, release_public_claims.BOUNDARIES)

    def test_state_accepts_only_fixed_identity_and_canonical_output(self):
        root, out, policy = self.check_state()
        self.assertEqual((root, out, policy), (self.root, self.out, self.policy))
        for mutate, pattern in [
            (lambda value: value.update(repository="attacker/repo"), "fixed identity"),
            (lambda value: value.update(install_archive_sha256="0" * 64), "fixed identity"),
            (lambda value: value.update(output=str(self.out.parent / "other")), "output identity"),
            (lambda value: value.update(skip=True), "state fields"),
        ]:
            candidate = dict(self.state)
            mutate(candidate)
            with self.subTest(pattern=pattern), self.assertRaisesRegex(RuntimeError, pattern):
                self.check_state(candidate)

    def test_provider_requires_allowed_kind_digest_and_environment_id(self):
        good = {"PROVIDER_KIND": "github-actions-ephemeral",
                "PROVIDER_IMAGE": "ubuntu:24.04@sha256:" + "1" * 64,
                "GITHUB_RUN_ID": "123"}
        with patch.dict(MODULE.os.environ, good, clear=True):
            result = MODULE.provider()
        self.assertEqual(result["image"], "ubuntu:24.04")
        self.assertEqual(result["image_digest"], "sha256:" + "1" * 64)
        self.assertFalse(result["original_workspace_mounted"])
        for env in [{**good, "PROVIDER_KIND": "self-hosted"},
                    {**good, "PROVIDER_IMAGE": "ubuntu:latest"},
                    {k: v for k, v in good.items() if k != "GITHUB_RUN_ID"}]:
            with self.subTest(env=env), patch.dict(MODULE.os.environ, env, clear=True), \
                    self.assertRaises(RuntimeError):
                MODULE.provider()

    def test_download_hash_checks_without_persisting_url(self):
        body = b"fixed input bytes"
        destination = self.out / "input.bin"
        class Source(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *_): return False
        with patch.dict(MODULE.os.environ, {"FIXTURE_URL": "https://secret.invalid/token"}, clear=True), \
                patch.object(MODULE.urllib.request, "urlopen", return_value=Source(body)) as opened:
            MODULE.download("FIXTURE_URL", destination, hashlib.sha256(body).hexdigest())
        self.assertEqual(destination.read_bytes(), body)
        self.assertNotIn("secret.invalid", destination.read_text(errors="ignore"))
        opened.assert_called_once()

    def test_download_error_redacts_secret_url(self):
        secret = "https://secret.invalid/bearer-token"
        with patch.dict(MODULE.os.environ, {"FIXTURE_URL": secret}, clear=True), \
                patch.object(MODULE.urllib.request, "urlopen",
                             side_effect=RuntimeError("failed at " + secret)), \
                self.assertRaisesRegex(RuntimeError, "fixed input download failed") as caught:
            MODULE.download("FIXTURE_URL", self.out / "missing.bin", "0" * 64)
        self.assertNotIn(secret, str(caught.exception))

    def test_stage_row_records_exact_argv_and_hash_bound_logs(self):
        with patch.object(MODULE, "CANONICAL", self.root):
            row = MODULE.stage_row(self.out, "fixture", ["/bin/sh", "-c", "printf ok"],
                                   self.root, dict(MODULE.os.environ))
        self.assertEqual(row["argv"], ["/bin/sh", "-c", "printf ok"])
        self.assertEqual(row["cwd"], ".")
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(row["stdout"]["sha256"], MODULE.sha(self.out / "fixture.stdout"))

    def test_formal_and_negative_stage_mapping_is_fixed_and_ordered(self):
        state = self.out / "state.json"
        state.write_text(json.dumps({"candidate": "a" * 40}) + "\n")
        formal = MODULE.product(self.root, "week6-formal-clean-room") / "report.json"
        formal.parent.mkdir()
        formal.write_text("{}\n")
        with patch.object(MODULE, "checked_config", return_value=(self.root, self.out, self.policy)), \
                patch.object(MODULE, "command") as command, \
                patch.object(MODULE, "produce_negatives") as negatives:
            MODULE.stage_action("mutation-matrix", state)
            negatives.assert_called_once_with(self.root)
            self.assertIn("release_evidence", command.call_args_list[0].args[0][4])
            command.reset_mock(); negatives.reset_mock()
            MODULE.stage_action("lean-kernel", state)
            self.assertEqual(command.call_args.args[0], ["/usr/bin/make", "proof-check", "BACKEND=lean"])
            command.reset_mock()
            MODULE.stage_action("rocq-spike", state)
            self.assertEqual(command.call_args_list[0].args[0][3], "scripts/week6_formal_record.py")
            self.assertEqual(command.call_args_list[1].args[0][3], "scripts/week6_formal_review.py")
            negatives.assert_not_called()

    def test_install_sail_stage_configures_cmake_with_the_fixed_compiler(self):
        state = self.out / "state.json"
        state.write_text(json.dumps({"candidate": "a" * 40}) + "\n")
        compiler = MODULE.tool_paths(self.root)["sail"]
        compiler.parent.mkdir(parents=True)
        compiler.write_text("#!/bin/sh\n")
        sys.path.insert(0, str(HERE.parent))
        import rebuilt_main_tools
        with patch.object(MODULE, "checked_config", return_value=(self.root, self.out, self.policy)), \
                patch.object(MODULE, "record_tool") as record_tool, \
                patch.object(MODULE, "command") as command, \
                patch.object(rebuilt_main_tools, "cmake_compiler") as cmake_compiler:
            MODULE.stage_action("install-sail", state)
        record_tool.assert_called_once_with(self.root, self.out, "sail")
        argv = command.call_args.args[0]
        self.assertEqual(argv[:5], ["/usr/bin/cmake", "-S", "deps/sail-riscv", "-B", "deps/sail-riscv/build"])
        self.assertIn("-DSAIL_BIN:FILEPATH=" + str(compiler), argv)
        self.assertIn("-DDOWNLOAD_GMP=TRUE", argv)
        self.assertEqual(command.call_args.args[1], self.root)
        cmake_compiler.assert_called_once_with(self.root, compiler)
        # A pre-existing build directory is not a fresh checkout and is refused before cmake runs.
        (self.root / "deps/sail-riscv/build").mkdir(parents=True)
        with patch.object(MODULE, "checked_config", return_value=(self.root, self.out, self.policy)), \
                patch.object(MODULE, "record_tool"), patch.object(MODULE, "command") as command, \
                self.assertRaisesRegex(RuntimeError, "already exists"):
            MODULE.stage_action("install-sail", state)
        command.assert_not_called()

    def test_decoder_stage_runs_the_admitted_source_installation(self):
        state = self.out / "state.json"
        state.write_text(json.dumps({"candidate": "a" * 40,
                                     "decoder_archive_sha256": MODULE.DECODER_ARCHIVE_SHA}) + "\n")
        destination = self.root / "artifacts/decoder-inputs/rebuilt-v2"
        receipt = {"archive_sha256": MODULE.DECODER_ARCHIVE_SHA,
                   "installation": {"payload": str(destination / "payload")}}
        sys.path.insert(0, str(HERE.parent))
        import decoder_rebuilt_inputs
        with patch.object(MODULE, "checked_config", return_value=(self.root, self.out, self.policy)), \
                patch.object(MODULE, "download") as download, \
                patch.object(decoder_rebuilt_inputs, "install", return_value=receipt) as install, \
                patch.object(MODULE, "record_tool") as record_tool:
            MODULE.stage_action("install-aeneas-charon", state)
        archive = self.out / "fixed-inputs/rebuilt-decoder-candidate.tar.gz"
        download.assert_called_once_with("WEEK6_DECODER_ARCHIVE_URL", archive,
                                         MODULE.DECODER_ARCHIVE_SHA)
        install.assert_called_once_with(archive, destination)
        self.assertEqual([call.args[2] for call in record_tool.call_args_list], ["aeneas", "charon"])

    def test_public_mode_rejects_reused_canonical_before_clone(self):
        args = argparse.Namespace(repository=MODULE.REPOSITORY, commit="a" * 40,
            canonical_checkout=self.root, install_archive_sha256=MODULE.INSTALL_ARCHIVE_SHA,
            install_manifest_sha256=MODULE.INSTALL_MANIFEST_SHA,
            decoder_archive_sha256=MODULE.DECODER_ARCHIVE_SHA,
            review_policy=Path("docs/release/week6-review-policy-v1.json"), out=self.out)
        with patch.object(MODULE, "CANONICAL", self.root), \
                patch.object(MODULE, "BOOTSTRAP_ROOT", self.root.parent / "bootstrap"), \
                patch.object(MODULE.subprocess, "run") as run, \
                self.assertRaisesRegex(RuntimeError, "must be fresh"):
            MODULE.public_run(args)
        run.assert_not_called()

    def test_parser_does_not_accept_an_arbitrary_stage(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            MODULE.parser().parse_args(["_stage", "--name", "run-shell", "--state", "x"])


if __name__ == "__main__":
    unittest.main()
