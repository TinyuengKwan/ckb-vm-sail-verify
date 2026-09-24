#!/usr/bin/env python3
"""Execute the workflow's staging commands in a real Git checkout.

The downloader, hashing and replay shell commands run unchanged, including
paths containing spaces. Small CLI stand-ins record producer/gate arguments;
they do not stand in for evidence acceptance (covered by the gate tests and
the separate real-bundle rehearsal). No network or proof toolchains needed.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import source_snapshot

WORKFLOW = (ROOT / ".github/workflows/week6-release.yml").read_text()
DOWNLOAD = "Download the independent-ephemeral-vm evidence bundle (URL never recorded)"
UNPACK = "Unpack into the candidate checkout and validate clean-room + VM provenance"
PACKAGE = "Package the evidence archive for the distinct download/replay job"
AUDIT = "Validate fresh component and expected pre-publication audit boundary"
REPLAY = "Verify archive bytes and replay only the downloaded case"


def step(name):
    """Read the fixed workflow's named step, failing if missing/ambiguous."""
    marker = "      - name: " + name
    lines = WORKFLOW.splitlines()
    positions = [i for i, line in enumerate(lines) if line == marker]
    if len(positions) != 1:
        raise ValueError("workflow step missing or ambiguous: " + name)
    result = []
    for line in lines[positions[0] + 1:]:
        if line.strip() and not line.startswith("        "):
            break
        result.append(line)
    return result


def field(name, key, indent):
    lines = step(name)
    marker = " " * indent + key + ":"
    matches = [(i, line[len(marker):].strip()) for i, line in enumerate(lines)
               if line.startswith(marker)]
    if len(matches) != 1:
        raise ValueError("workflow field missing or ambiguous: " + key)
    position, value = matches[0]
    if value != "|":
        return value
    body = []
    for line in lines[position + 1:]:
        if line.strip() and not line.startswith(" " * (indent + 2)):
            break
        body.append(line[indent + 2:])
    return "\n".join(body) + "\n"


RECORDER = '''import json, os, pathlib, sys
args = sys.argv[1:]
pathlib.Path(os.environ["RECORDED_ARGS"]).write_text(json.dumps(args))
if pathlib.Path(__file__).name == "week6_ci_archive.py":
    for flag, data in (("--out", b"fixture archive"), ("--manifest-out", b"{}\\n")):
        with pathlib.Path(args[args.index(flag) + 1]).open("xb") as stream:
            stream.write(data)
'''


class WorkflowPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="week6 workflow paths ")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "checkout with spaces"
        self.temp = self.base / "runner temp with spaces"
        self.root.mkdir()
        self.temp.mkdir()
        (self.root / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())
        scripts = self.root / "scripts"
        scripts.mkdir()
        for name in ("week6_vm_evidence_bundle", "week6_ci_archive", "week6_release_ci_gate"):
            (scripts / (name + ".py")).write_text(RECORDER)
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_CONFIG_SYSTEM": "/dev/null", "RUNNER_TEMP": str(self.temp),
                    "GITHUB_WORKSPACE": str(self.root),
                    "GITHUB_OUTPUT": str(self.temp / "github-output"),
                    "RECORDED_ARGS": str(self.temp / "recorded-args.json")}
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "path-isolation fixture only")
        self.env["EXPECTED_COMMIT"] = self.git("rev-parse", "HEAD").strip()
        self.before = source_snapshot.inventory(self.root)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, env=self.env,
                                       stderr=subprocess.PIPE, text=True)

    def run_step(self, name):
        return subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c",
                               field(name, "run", 8)], cwd=self.root, env=self.env,
                              capture_output=True, text=True, timeout=30)

    def passed(self, name):
        result = self.run_step(name)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(source_snapshot.inventory(self.root), self.before)
        return result

    def input_path(self, name, key="path"):
        value = field(name, key, 10).replace("${{ runner.temp }}", str(self.temp))
        path = Path(value)
        self.assertTrue(path.is_absolute())
        self.assertTrue(path.is_relative_to(self.temp))
        self.assertFalse(path.is_relative_to(self.root))
        return path

    def download(self):
        original = self.base / "original-bundle.tar.gz"
        original.write_bytes(b"path-test bundle bytes")
        self.env["WEEK6_VM_EVIDENCE_URL"] = original.as_uri()
        self.env["VM_EVIDENCE_BUNDLE_SHA256"] = hashlib.sha256(original.read_bytes()).hexdigest()
        self.passed(DOWNLOAD)
        return original

    def recorded(self):
        return json.loads(Path(self.env["RECORDED_ARGS"]).read_text())

    def test_old_checkout_staging_paths_change_real_source_inventory(self):
        for name in ("intake/vm-evidence.tar.gz", "downloaded/week6-evidence.tar.gz",
                     "week6-evidence.tar.gz", "MANIFEST.json"):
            with self.subTest(path=name):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"not source")
                try:
                    current = source_snapshot.inventory(self.root)
                    self.assertNotEqual(current, self.before)
                    self.assertEqual(current["changes_from_head"][name]["operation"], "added")
                finally:
                    path.unlink()

    def test_actual_download_and_unpack_arguments_preserve_checkout(self):
        original = self.download()
        self.passed(UNPACK)
        args = self.recorded()
        path = Path(args[args.index("--bundle") + 1])
        self.assertEqual(path, self.temp / "week6-intake/vm-evidence.tar.gz")
        self.assertEqual(path.read_bytes(), original.read_bytes())
        self.assertEqual(args[args.index("--root") + 1], str(self.root))
        self.assertEqual(args[args.index("--candidate") + 1], self.env["EXPECTED_COMMIT"])
        self.assertEqual(args[args.index("--bundle-sha256") + 1],
                         self.env["VM_EVIDENCE_BUNDLE_SHA256"])

    def test_download_rejects_bad_hash_and_does_not_overwrite(self):
        original = self.base / "input"
        original.write_bytes(b"fixture")
        self.env["WEEK6_VM_EVIDENCE_URL"] = original.as_uri()
        self.env["VM_EVIDENCE_BUNDLE_SHA256"] = "0" * 64
        first = self.run_step(DOWNLOAD)
        self.assertNotEqual(first.returncode, 0)
        self.assertIn("hash differs", first.stderr)
        second = self.run_step(DOWNLOAD)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual((self.temp / "week6-intake/vm-evidence.tar.gz").read_bytes(), b"fixture")
        self.assertEqual(source_snapshot.inventory(self.root), self.before)

    def test_download_failure_does_not_log_url(self):
        secret = (self.base / "absent-private-download-url").as_uri()
        self.env.update(WEEK6_VM_EVIDENCE_URL=secret, VM_EVIDENCE_BUNDLE_SHA256="0" * 64)
        result = self.run_step(DOWNLOAD)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("vm evidence download failed", result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertEqual(source_snapshot.inventory(self.root), self.before)

    def test_package_attestation_and_upload_paths_agree_outside_checkout(self):
        self.passed(PACKAGE)
        args = self.recorded()
        archive = Path(args[args.index("--out") + 1])
        manifest = Path(args[args.index("--manifest-out") + 1])
        self.assertEqual(archive, self.input_path(
            "Attest the exact tar archive (attests packaging on GitHub, not VM execution)",
            "subject-path"))
        uploaded = field("Upload archive, manifest and attestation bundle", "path", 10)
        paths = uploaded.replace("${{ runner.temp }}", str(self.temp)).splitlines()
        self.assertEqual(paths, [str(archive), str(manifest), "${{ steps.attest.outputs.bundle-path }}"])
        self.assertTrue(archive.is_relative_to(self.temp))
        self.assertTrue(manifest.is_relative_to(self.temp))
        output = Path(self.env["GITHUB_OUTPUT"]).read_text()
        self.assertIn("archive_sha256=" + hashlib.sha256(archive.read_bytes()).hexdigest(), output)

    def test_release_audit_download_and_archive_argument_agree(self):
        directory = self.input_path("Download the clean-room artifact")
        directory.mkdir()
        archive = directory / "week6-evidence.tar.gz"
        archive.write_bytes(b"fixture")
        self.env["EXPECTED_SHA256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.passed(AUDIT)
        args = self.recorded()
        self.assertEqual(args[args.index("--archive") + 1], str(archive))
        self.assertEqual(args[args.index("--archive-sha256") + 1], self.env["EXPECTED_SHA256"])
        self.assertEqual(args[args.index("--root") + 1], str(self.root))

    def replay_archive(self):
        directory = self.input_path("Download in a distinct job and new destination")
        directory.mkdir()
        archive = directory / "week6-evidence.tar.gz"
        executable = textwrap.dedent('''\
            #!/usr/bin/env python3
            import json, pathlib, sys
            args = sys.argv[1:]
            for flag in ('--sail-bin', '--sail-config', '--replay'):
                if not pathlib.Path(args[args.index(flag) + 1]).is_file():
                    raise SystemExit('replay input missing')
            out = pathlib.Path(args[args.index('--artifact-dir') + 1])
            out.mkdir()
            (out / 'path-test.json').write_text(json.dumps(args))
        ''').encode()
        with tarfile.open(archive, "w:gz") as tar:
            for name, content in {"bin/ckb-vm-sail-diff": executable,
                                  "bin/sail_riscv_sim": b"fixture",
                                  "config/ckb_vm_config.json": b"{}",
                                  "cases/add-signed-overflow.json": b"{}"}.items():
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(content), 0o755
                tar.addfile(member, io.BytesIO(content))
        self.env["EXPECTED_SHA256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        return archive

    def test_actual_replay_shell_keeps_all_inputs_and_outputs_outside_checkout(self):
        self.replay_archive()
        self.passed(REPLAY)
        args = json.loads((self.temp / "week6-replay/result/path-test.json").read_text())
        self.assertEqual(args[::2], ["--sail-bin", "--sail-config", "--replay", "--artifact-dir"])
        for value in args[1::2]:
            self.assertTrue(Path(value).is_relative_to(self.temp / "week6-replay"))

    def test_replay_rejects_wrong_digest_before_extraction(self):
        self.replay_archive()
        self.env["EXPECTED_SHA256"] = "0" * 64
        self.assertNotEqual(self.run_step(REPLAY).returncode, 0)
        self.assertFalse((self.temp / "week6-replay").exists())
        self.assertEqual(source_snapshot.inventory(self.root), self.before)

    def test_fast_job_runs_this_regression(self):
        self.assertIn("python3 scripts/tests/test_week6_workflow_paths.py",
                      field("Fast source and Rust checks", "run", 8))


if __name__ == "__main__":
    unittest.main()
