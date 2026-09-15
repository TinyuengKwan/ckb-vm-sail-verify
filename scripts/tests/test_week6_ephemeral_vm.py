#!/usr/bin/env python3
"""Host-side tests for the independent ephemeral VM launcher with a fake hypervisor."""
import argparse
import importlib.util
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


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("week6_ephemeral_vm", HERE.parent / "week6_ephemeral_vm.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
sys.path.insert(0, str(HERE.parent))
import release_external_evidence as external

SECRET = "https://secret.invalid/bearer-token/extra-installations.tar.gz"
CANONICAL = MODULE.CANONICAL.relative_to("/").as_posix()
RUN = MODULE.GUEST_RUN.relative_to("/").as_posix()

FAKE_QEMU = r'''#!/usr/bin/env python3
import io, json, re, sys, tarfile
argv = sys.argv[1:]
if "--version" in argv:
    print("QEMU emulator version 8.2.2 (fixture)"); raise SystemExit(0)
def drive(marker):
    for item in argv:
        if item.startswith("file=") and marker in item:
            return item[len("file="):].split(",")[0]
    raise SystemExit(9)
evidence = drive("id=evidence")
secrets = drive("id=secrets")
seed = drive("seed.iso")
console = [item for item in argv if item.startswith("file:")][0][len("file:"):]
assert "accel=kvm" in argv[argv.index("-machine") + 1]
blob = open(secrets, "rb").read().rstrip(b"\0").decode()
assert "WEEK6_INSTALL_ARCHIVE_URL='" in blob, blob
user_data = open(seed).read()
environment_id = re.search(r"WEEK6_ENVIRONMENT_ID=([0-9a-fA-F-]+)", user_data).group(1)
provider_image = re.search(r"PROVIDER_IMAGE=(\S+)", user_data).group(1)
name, digest = provider_image.split("@")
open(console, "w").write("fixture console: booted, secrets not echoed\n")
import os
mode_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FAKE_QEMU_MODE")
mode = open(mode_file).read().strip() if os.path.exists(mode_file) else "ok"
report = {"provider": {"kind": "independent-ephemeral-vm", "environment_id": environment_id,
                       "image": name, "image_digest": digest, "created_at": "2026-09-14T00:00:00+00:00",
                       "ephemeral": True, "original_workspace_mounted": False}, "status": "passed"}
members = {
    "%(canonical)s/artifacts/boundary-check/week6-clean-room/report.json": json.dumps(report).encode(),
    "%(canonical)s/artifacts/boundary-check/week6-clean-room/stage.stdout": b"stage\n",
    "%(canonical)s/artifacts/boundary-check/week6-native-clean-room/runtime/report.json": b"{}\n",
    "%(run)s/exit-code": (b"0\n" if mode != "guest-failed" else b"1\n"),
    "%(run)s/controller.stdout": b"controller out\n",
    "%(run)s/controller.stderr": b"",
}
if mode == "link":
    members = dict(members)
with tarfile.open(evidence, "w") as tar:
    for member_name, data in members.items():
        info = tarfile.TarInfo(member_name); info.size = len(data); info.mode = 0o644
        tar.addfile(info, io.BytesIO(data))
    if mode == "link":
        link = tarfile.TarInfo("%(canonical)s/artifacts/boundary-check/week6-clean-room/evil")
        link.type = tarfile.SYMTYPE; link.linkname = "/etc/passwd"
        tar.addfile(link)
raise SystemExit(3 if mode == "hypervisor-failed" else 0)
''' % {"canonical": CANONICAL, "run": RUN}

FAKE_QEMU_IMG = "#!/usr/bin/env python3\nimport sys, pathlib\nassert sys.argv[1] == 'create'\npathlib.Path(sys.argv[-2]).write_bytes(b'fixture overlay')\n"
FAKE_LOCALDS = "#!/usr/bin/env python3\nimport sys, shutil\nshutil.copyfile(sys.argv[2], sys.argv[1])\n"


class EphemeralVmTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="week6-ephemeral-vm-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.tools = self.base / "tools"
        self.tools.mkdir()
        self.qemu = self.tool("qemu-system-x86_64", FAKE_QEMU)
        self.qemu_img = self.tool("qemu-img", FAKE_QEMU_IMG)
        self.localds = self.tool("cloud-localds", FAKE_LOCALDS)
        self.image = self.base / MODULE.IMAGE_NAME
        self.image.write_bytes(b"fixture cloud image")
        self.checkout = self.base / "candidate"
        self.checkout.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for argv in [["git", "init", "-q"], ["git", "commit", "-q", "--allow-empty", "-m", "candidate"]]:
            subprocess.run(argv, cwd=self.checkout, check=True, env=env, stdout=subprocess.PIPE)
        self.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.checkout, text=True).strip()
        self.environment = {"WEEK6_INSTALL_ARCHIVE_URL": SECRET,
                            "WEEK6_INSTALL_MANIFEST_URL": "https://secret.invalid/manifest.json",
                            "WEEK6_DECODER_ARCHIVE_URL": "https://secret.invalid/decoder.tar.gz",
                            "HTTP_PROXY": "http://user:pw@proxy.invalid:3128"}

    def tool(self, name, body):
        path = self.tools / name
        path.write_text(body)
        path.chmod(0o755)
        return path

    def args(self, out="launcher", **overrides):
        values = dict(mode="run", commit=self.commit, image=self.image, evidence_root=self.checkout,
                      out=self.base / out, qemu=self.qemu, qemu_img=self.qemu_img, cloud_localds=self.localds,
                      vcpus=4, memory_gb=8, disk_gb=48, evidence_gb=8, timeout_hours=1)
        values.update(overrides)
        return argparse.Namespace(**values)

    def launch(self, **overrides):
        with patch.object(MODULE, "IMAGE_SHA256", MODULE.sha(self.image)), \
                patch.object(MODULE, "PROVIDER_IMAGE", MODULE.IMAGE_NAME + "@sha256:" + MODULE.sha(self.image)):
            return MODULE.launch(self.args(**overrides), self.environment)

    def test_seed_is_public_fixed_and_free_of_secrets(self):
        text = MODULE.user_data("a" * 40, "env-1")
        self.assertIn("PROVIDER_KIND=" + MODULE.PROVIDER_KIND, text)
        self.assertIn("PROVIDER_IMAGE=" + MODULE.PROVIDER_IMAGE, text)
        self.assertIn("--commit " + "a" * 40, text)
        self.assertIn("--install-archive-sha256 " + MODULE.INSTALL_ARCHIVE_SHA, text)
        self.assertNotIn("@@", text)
        self.assertNotIn("set -x", text)
        self.assertNotIn("secret.invalid", text)
        self.assertIn("uid: 1000", text)
        blob = MODULE.secrets_blob(self.environment)
        self.assertEqual(len(blob), MODULE.SECRETS_BYTES)
        self.assertIn(b"WEEK6_INSTALL_ARCHIVE_URL='" + SECRET.encode() + b"'", blob)
        self.assertIn(b"HTTP_PROXY='http://user:pw@proxy.invalid:3128'", blob)
        for broken in [{**self.environment, "WEEK6_DECODER_ARCHIVE_URL": "http://plain.invalid/x"},
                       {**self.environment, "HTTP_PROXY": "http://x'y"},
                       {k: v for k, v in self.environment.items() if k != "WEEK6_INSTALL_MANIFEST_URL"}]:
            with self.subTest(broken=broken), self.assertRaises(RuntimeError):
                MODULE.secrets_blob(broken)

    def test_qemu_argv_has_kvm_serial_disks_and_no_shared_filesystem(self):
        argv = MODULE.qemu_argv("/usr/bin/qemu-system-x86_64", "o.qcow2", "e.raw", "s.raw", "seed.iso",
                                "console.log", 8, 16)
        self.assertEqual(argv[argv.index("-machine") + 1], "q35,accel=kvm")
        self.assertIn("virtio-blk-pci,drive=root,bootindex=0", argv)
        self.assertLess(argv.index("virtio-blk-pci,drive=root,bootindex=0"),
                        argv.index("virtio-blk-pci,drive=evidence,serial=week6-evidence"))
        self.assertIn("virtio-blk-pci,drive=evidence,serial=week6-evidence", argv)
        self.assertIn("virtio-blk-pci,drive=secrets,serial=week6-secrets", argv)
        self.assertIn("-no-reboot", argv)
        self.assertFalse(any(flag in item for item in argv for flag in MODULE.SHARED_FILESYSTEM_FLAGS))
        with patch.object(MODULE, "SHARED_FILESYSTEM_FLAGS", ("virtio-blk",)), self.assertRaisesRegex(
                RuntimeError, "shared host filesystem"):
            MODULE.qemu_argv("q", "o", "e", "s", "seed", "c", 1, 1)

    def test_evidence_members_reject_links_and_foreign_paths(self):
        def archive(name, members, link=None):
            path = self.base / name
            with tarfile.open(path, "w") as tar:
                for member_name, data in members.items():
                    info = tarfile.TarInfo(member_name); info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
                if link:
                    info = tarfile.TarInfo(link); info.type = tarfile.SYMTYPE; info.linkname = "/etc/passwd"
                    tar.addfile(info)
            return path
        good = archive("good.tar", {CANONICAL + "/artifacts/boundary-check/week6-clean-room/report.json": b"{}",
                                    RUN + "/exit-code": b"0\n"})
        self.assertEqual(set(MODULE.evidence_members(good).values()),
                         {("evidence", "artifacts/boundary-check/week6-clean-room/report.json"),
                          ("guest", "exit-code")})
        diagnostics = archive("diag.tar", {
            CANONICAL + "/artifacts/boundary-check/rebuilt-production-rust-abc/report.json": b"{}",
            CANONICAL + "/artifacts/boundary-check/week6-clean-room/report.json": b"{}",
            RUN + "/exit-code": b"1\n"})
        self.assertIn(("evidence", "artifacts/boundary-check/rebuilt-production-rust-abc/report.json"),
                      set(MODULE.evidence_members(diagnostics).values()))
        self.assertIn("rustup", MODULE.GUEST_PACKAGES)
        self.assertIn("jq", MODULE.GUEST_PACKAGES)
        for name, members, link, pattern in [
            ("foreign.tar", {CANONICAL + "/scripts/week6_clean_room.py": b"x"}, None, "outside allowed"),
            ("other-root.tar", {CANONICAL + "/artifacts/boundary-check/isolated-rust/bin/rustc": b"x"}, None,
             "restored installation root"),
            ("aeneas-root.tar", {CANONICAL + "/artifacts/boundary-check/aeneas-opam-x/report.json": b"x"}, None,
             "restored installation root"),
            ("binary-diag.tar", {CANONICAL + "/artifacts/boundary-check/rebuilt-production-rust-abc/x.llbc": b"x"},
             None, "outside allowed"),
            ("traversal.tar", {CANONICAL + "/artifacts/boundary-check/week6-x/../../../etc/passwd": b"x"}, None,
             "unsafe"),
            ("link.tar", {RUN + "/exit-code": b"0\n"}, CANONICAL + "/artifacts/boundary-check/week6-clean-room/l",
             "special/link"),
            ("empty.tar", {}, None, "empty"),
        ]:
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, pattern):
                MODULE.evidence_members(archive(name, members, link))

    def test_launch_extracts_binds_record_and_destroys_secret_bearing_disks(self):
        summary = self.launch()
        out = self.base / "launcher"
        clean = self.checkout / MODULE.CLEAN_ROOM_OUT
        record = json.loads((clean / MODULE.RECORD).read_text())
        self.assertEqual(summary["status"], MODULE.RECORD_STATUS)
        self.assertEqual(record["status"], MODULE.RECORD_STATUS)
        report = json.loads((clean / "report.json").read_text())
        self.assertEqual(record["provider"], {key: report["provider"][key]
                                              for key in ["kind", "environment_id", "image", "image_digest"]})
        self.assertEqual(record["report"]["sha256"], MODULE.sha(clean / "report.json"))
        self.assertEqual(record["hypervisor"]["version"], "QEMU emulator version 8.2.2 (fixture)")
        self.assertEqual(record["hypervisor"]["executable_sha256"], MODULE.sha(self.qemu))
        self.assertTrue(record["disks"]["overlay"]["destroyed"] and record["disks"]["secrets"]["destroyed"])
        self.assertFalse(record["boundaries"]["platform_signed_identity"])
        self.assertTrue(record["boundaries"]["operator_attested"])
        for name in ["overlay.qcow2", "evidence.raw", "secrets.raw"]:
            self.assertFalse((out / name).exists(), name)
        self.assertTrue((self.checkout / "artifacts/boundary-check/week6-native-clean-room/runtime/report.json").is_file())
        self.assertEqual((clean / "host/guest-exit-code").read_text().strip(), "0")
        for path in list(out.rglob("*")) + list(clean.rglob("*")):
            if path.is_file():
                self.assertNotIn(b"secret.invalid", path.read_bytes(), str(path))
                self.assertNotIn(b"user:pw@", path.read_bytes(), str(path))
        # The validator accepts the record only against the very report it was bound to.
        result = external.check_vm_provenance(clean / "report.json")
        self.assertTrue(result["operator_attested"])
        self.assertFalse(result["platform_signed_identity"])
        (clean / "report.json").write_text(json.dumps({**report, "status": "changed"}))
        with self.assertRaisesRegex(RuntimeError, "different clean-room report"):
            external.check_vm_provenance(clean / "report.json")
        # A second launch cannot overwrite the extracted evidence.
        with self.assertRaisesRegex(RuntimeError, "occupied|already exists"):
            self.launch(out="second")

    def test_launch_failures_destroy_secrets_and_record_the_error(self):
        for mode, pattern in [("hypervisor-failed", "qemu exited 3"), ("guest-failed", "guest controller failed"),
                              ("link", "special/link")]:
            (self.tools / "FAKE_QEMU_MODE").write_text(mode)
            out = self.base / ("fail-" + mode)
            root = self.base / ("root-" + mode)
            subprocess.run(["git", "clone", "-q", str(self.checkout), str(root)], check=True)
            with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, pattern):
                self.launch(out=out, evidence_root=root)
            report = json.loads((out / "report.json").read_text())
            self.assertEqual(report["status"], "launch_failed")
            self.assertTrue(report["boundaries"]["secrets_destroyed"])
            self.assertTrue(report["boundaries"]["overlay_destroyed"])
            self.assertFalse((out / "secrets.raw").exists())
            self.assertFalse((root / MODULE.CLEAN_ROOM_OUT / MODULE.RECORD).exists())
        (self.tools / "FAKE_QEMU_MODE").unlink()

    def test_launch_requires_pinned_image_and_candidate_checkout(self):
        with self.assertRaisesRegex(RuntimeError, "pinned"):
            MODULE.launch(self.args(), self.environment)
        with patch.object(MODULE, "IMAGE_SHA256", MODULE.sha(self.image)), \
                self.assertRaisesRegex(RuntimeError, "candidate commit"):
            MODULE.launch(self.args(commit="b" * 40), self.environment)
        self.assertFalse((self.base / "launcher").exists())

    def test_plan_mode_boots_nothing(self):
        with patch.object(MODULE.subprocess, "run") as run:
            summary = MODULE.plan(self.args(mode="plan", out="plan"))
        run.assert_not_called()
        self.assertEqual(summary["status"], "plan_only_nothing_booted")
        self.assertEqual(summary["image"]["sha256"], MODULE.IMAGE_SHA256)
        self.assertTrue((self.base / "plan/user-data").is_file())
        self.assertFalse(summary["boundaries"]["clean_room_claimed"])


if __name__ == "__main__":
    unittest.main()
