#!/usr/bin/env python3
"""Run the fixed Week6 clean-room controller inside a fresh local KVM guest.

Provider kind ``independent-ephemeral-vm`` is already admitted by the external
acceptance policy.  This host-side launcher makes that provider auditable
instead of self-asserted: it pins the Ubuntu 24.04 cloud image by SHA-256,
boots a throw-away qcow2 overlay under a recorded qemu argv with no shared
host filesystem, feeds the guest a public cloud-init seed plus a separate
secrets disk that is never hashed or copied into evidence, reads the evidence
back from a raw disk the guest wrote, extracts it into a fresh candidate
checkout without overwriting anything, and writes ``vm-provenance.json`` next
to the extracted clean-room report.  The overlay and the secrets disk are
destroyed before the record is written.

The record is operator-attested.  Nothing here is signed by a platform, so the
aggregator keeps ``clean_room`` incomplete until this record exists and never
treats it as GitHub-hosted provenance.  Running this launcher does not create
a release, push, dispatch a workflow or approve anything.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import uuid


BOOTSTRAP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "TinyuengKwan/ckb-vm-sail-verify"
CANONICAL = PurePosixPath("/home/clair/tinyueng_workplace/ckb-vm-sail-verify")
GUEST_USER = "clair"
GUEST_RUN = PurePosixPath("/home/clair/week6-run")
GUEST_BOOTSTRAP = PurePosixPath("/home/clair/week6-bootstrap")
IMAGE_NAME = "ubuntu-24.04-server-cloudimg-amd64.img"
IMAGE_RELEASE = "release-20260911"
IMAGE_SHA256 = "612b2c0cc1bc413a6cb8c38fd611794caf0f2b436c50013d8b3794db12ad7354"
IMAGE_URL = "https://cloud-images.ubuntu.com/releases/noble/" + IMAGE_RELEASE + "/" + IMAGE_NAME
PROVIDER_KIND = "independent-ephemeral-vm"
PROVIDER_IMAGE = IMAGE_NAME + "@sha256:" + IMAGE_SHA256
INSTALL_ARCHIVE_SHA = "c8e8ca2797aeabcbee3935949f6ad6b622a40468d77a7f5d79a50b1854a67ff4"
INSTALL_MANIFEST_SHA = "ac7b468e6715e6a4b956376a0ded0ee6e4d9cfc632d4323b439877916e74708e"
DECODER_ARCHIVE_SHA = "1a81921b12215a87106ac2080c05de3f2bf9d51b9bb14bdb80a90ac8c05c58d5"
REVIEW_POLICY = "docs/release/week6-review-policy-v1.json"
CLEAN_ROOM_OUT = "artifacts/boundary-check/week6-clean-room"
RECORD = "vm-provenance.json"
RECORD_KIND = "week6-ephemeral-vm-provenance-v1"
RECORD_STATUS = "guest_completed_evidence_extracted_overlay_destroyed"
SECRET_URLS = ["WEEK6_INSTALL_ARCHIVE_URL", "WEEK6_INSTALL_MANIFEST_URL", "WEEK6_DECODER_ARCHIVE_URL"]
PROXY_VARIABLES = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"]
# Apt names for the controller's twelve pinned host commands plus the C/GMP
# build inputs the Sail emulator and OCaml tools need.  This is the reviewed
# guest package list, not a proof that the host closure is complete.
GUEST_PACKAGES = ["git", "make", "bash", "python3", "cmake", "ninja-build", "build-essential",
                  "pkg-config", "z3", "opam", "rustup", "jq", "bsdutils", "ca-certificates", "libgmp-dev"]
# Stage producers that fail write their report outside week6-*; bring back
# their small diagnostic files so a failed run can be explained without a guest.
DIAGNOSTIC_SUFFIXES = (".json", ".log", ".stdout", ".stderr", ".txt")
RESTORED_ROOT_PREFIXES = ("isolated-", "aeneas-opam-")
SHARED_FILESYSTEM_FLAGS = ("-virtfs", "-fsdev", "virtio-9p", "virtiofs", "vhost-user-fs")
OID = re.compile(r"[0-9a-f]{40}")
HEX = re.compile(r"[0-9a-f]{64}")
SECRETS_BYTES = 1024 * 1024


def require(value, message):
    if not value:
        raise RuntimeError(message)


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def ref(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            "evidence reference outside/missing: " + str(path))
    return {"path": path.relative_to(root).as_posix(), "sha256": sha(path)}


def new_directory(path):
    path = Path(path).absolute()
    require(not path.exists() and not path.is_symlink() and path.parent.is_dir() and
            not any(parent.is_symlink() for parent in path.parents), "new launcher output directory required")
    path.mkdir()
    return path


def run_host(argv, cwd, timeout, stdout=None, stderr=None):
    with open(os.devnull, "rb") as stdin:
        result = subprocess.run([str(item) for item in argv], cwd=str(cwd), stdin=stdin,
                                stdout=stdout or subprocess.PIPE, stderr=stderr or subprocess.PIPE,
                                timeout=timeout)
    return result


GUEST_SCRIPT = r"""#!/bin/bash
# Week6 guest driver.  Written by the public cloud-init seed; secrets come only
# from the raw secrets disk and are never echoed; shell tracing stays off.
set -u
umask 022
RUN=@@GUEST_RUN@@
CANONICAL=@@CANONICAL@@
BOOTSTRAP=@@GUEST_BOOTSTRAP@@
EVIDENCE_DISK=/dev/disk/by-id/virtio-week6-evidence
SECRETS_DISK=/dev/disk/by-id/virtio-week6-secrets
mkdir -p "$RUN"
: > "$RUN/controller.stdout"
: > "$RUN/controller.stderr"
printf '%s\n' 255 > "$RUN/exit-code"
finish() {
    sync
    if [ -d "$CANONICAL/@@CLEAN_ROOM_OUT@@" ]; then
        mkdir -p "$CANONICAL/@@CLEAN_ROOM_OUT@@/replay-inputs"
        cp -f "$CANONICAL/deps/sail-riscv/build/c_emulator/sail_riscv_sim" \
              "$CANONICAL/@@CLEAN_ROOM_OUT@@/replay-inputs/sail_riscv_sim" 2>/dev/null || true
        cp -f "$CANONICAL/sail-model/build/ckb_vm_config.json" \
              "$CANONICAL/@@CLEAN_ROOM_OUT@@/replay-inputs/ckb_vm_config.json" 2>/dev/null || true
    fi
    rm -f "$RUN/secrets.env"
    {
        cd / && find "${RUN#/}" -mindepth 1 \( -type f -o -type d \) 2>/dev/null
        cd / && find "${CANONICAL#/}/artifacts/boundary-check" -mindepth 1 -maxdepth 1 -name 'week6-*' \
            -exec find {} \( -type f -o -type d \) \; 2>/dev/null
        cd / && find "${CANONICAL#/}/artifacts/boundary-check" -mindepth 1 -maxdepth 1 -type d \
            ! -name 'week6-*' ! -name 'isolated-*' ! -name 'aeneas-opam-*' \
            -exec find {} -type f \( -name '*.json' -o -name '*.log' -o -name '*.stdout' -o -name '*.stderr' \
            -o -name '*.txt' \) -size -8M \; 2>/dev/null
    } | sort -u > /root/week6-evidence-members.txt
    tar -C / --no-recursion --ignore-failed-read -cf "$EVIDENCE_DISK" -T /root/week6-evidence-members.txt \
        2>> "$RUN/controller.stderr"
    sync
    systemctl poweroff
}
trap finish EXIT
umask 077
tr -d '\0' < "$SECRETS_DISK" > "$RUN/secrets.env"
umask 022
set -a
. "$RUN/secrets.env"
set +a
export DEBIAN_FRONTEND=noninteractive
if [ -n "${HTTP_PROXY:-}" ]; then
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "$HTTP_PROXY" "${HTTPS_PROXY:-$HTTP_PROXY}" \
        > /etc/apt/apt.conf.d/90week6proxy
    chmod 600 /etc/apt/apt.conf.d/90week6proxy
fi
apt-get update >> "$RUN/apt.log" 2>&1 || { echo 'apt-get update failed' >> "$RUN/controller.stderr"; exit 1; }
apt-get install -y --no-install-recommends @@PACKAGES@@ >> "$RUN/apt.log" 2>&1 \
    || { echo 'apt-get install failed' >> "$RUN/controller.stderr"; exit 1; }
id -u @@GUEST_USER@@ >/dev/null 2>&1 || useradd --create-home --shell /bin/bash @@GUEST_USER@@
install -d -o @@GUEST_USER@@ -g @@GUEST_USER@@ "$(dirname "$CANONICAL")" "$RUN"
chown @@GUEST_USER@@:@@GUEST_USER@@ "$RUN"/*
runuser -u @@GUEST_USER@@ -- git clone --no-checkout https://github.com/@@REPOSITORY@@.git "$BOOTSTRAP" \
    >> "$RUN/controller.stdout" 2>> "$RUN/controller.stderr" || exit 1
runuser -u @@GUEST_USER@@ -- git -C "$BOOTSTRAP" checkout --detach @@COMMIT@@ \
    >> "$RUN/controller.stdout" 2>> "$RUN/controller.stderr" || exit 1
runuser -u @@GUEST_USER@@ -- env -i PATH=/usr/bin:/bin HOME=/home/@@GUEST_USER@@ LC_ALL=C LANG=C TZ=UTC \
    PROVIDER_KIND=@@PROVIDER_KIND@@ PROVIDER_IMAGE=@@PROVIDER_IMAGE@@ WEEK6_ENVIRONMENT_ID=@@ENVIRONMENT_ID@@ \
    WEEK6_INSTALL_ARCHIVE_URL="${WEEK6_INSTALL_ARCHIVE_URL:-}" \
    WEEK6_INSTALL_MANIFEST_URL="${WEEK6_INSTALL_MANIFEST_URL:-}" \
    WEEK6_DECODER_ARCHIVE_URL="${WEEK6_DECODER_ARCHIVE_URL:-}" \
    HTTP_PROXY="${HTTP_PROXY:-}" HTTPS_PROXY="${HTTPS_PROXY:-}" NO_PROXY="${NO_PROXY:-}" \
    http_proxy="${http_proxy:-}" https_proxy="${https_proxy:-}" no_proxy="${no_proxy:-}" \
    /usr/bin/python3 -B -O "$BOOTSTRAP/scripts/week6_clean_room.py" \
        --repository @@REPOSITORY@@ --commit @@COMMIT@@ --canonical-checkout "$CANONICAL" \
        --install-archive-sha256 @@INSTALL_ARCHIVE_SHA@@ --install-manifest-sha256 @@INSTALL_MANIFEST_SHA@@ \
        --decoder-archive-sha256 @@DECODER_ARCHIVE_SHA@@ --review-policy @@REVIEW_POLICY@@ \
        --out "$CANONICAL/@@CLEAN_ROOM_OUT@@" \
        >> "$RUN/controller.stdout" 2>> "$RUN/controller.stderr"
code=$?
printf '%s\n' "$code" > "$RUN/exit-code"
exit "$code"
"""


def guest_script(commit, environment_id):
    values = {"GUEST_RUN": str(GUEST_RUN), "CANONICAL": str(CANONICAL), "GUEST_BOOTSTRAP": str(GUEST_BOOTSTRAP),
              "CLEAN_ROOM_OUT": CLEAN_ROOM_OUT, "PACKAGES": " ".join(GUEST_PACKAGES), "GUEST_USER": GUEST_USER,
              "REPOSITORY": REPOSITORY, "COMMIT": commit, "PROVIDER_KIND": PROVIDER_KIND,
              "PROVIDER_IMAGE": PROVIDER_IMAGE, "ENVIRONMENT_ID": environment_id,
              "INSTALL_ARCHIVE_SHA": INSTALL_ARCHIVE_SHA, "INSTALL_MANIFEST_SHA": INSTALL_MANIFEST_SHA,
              "DECODER_ARCHIVE_SHA": DECODER_ARCHIVE_SHA, "REVIEW_POLICY": REVIEW_POLICY}
    text = GUEST_SCRIPT
    for key, value in values.items():
        require(re.fullmatch(r"[A-Za-z0-9 ./_:@-]+", value), "guest script value needs quoting: " + key)
        text = text.replace("@@" + key + "@@", value)
    require("@@" not in text, "unfilled guest script placeholder")
    return text


def user_data(commit, environment_id):
    script = guest_script(commit, environment_id)
    indented = "".join("      " + line + "\n" for line in script.splitlines())
    return ("#cloud-config\n"
            "hostname: week6-clean-room\n"
            "manage_etc_hosts: true\n"
            "users:\n"
            "  - name: " + GUEST_USER + "\n"
            "    uid: 1000\n"
            "    shell: /bin/bash\n"
            "    lock_passwd: true\n"
            "write_files:\n"
            "  - path: /usr/local/sbin/week6-guest.sh\n"
            "    permissions: '0755'\n"
            "    owner: root:root\n"
            "    content: |\n" + indented +
            "runcmd:\n"
            "  - [/usr/local/sbin/week6-guest.sh]\n"
            "power_state:\n"
            "  mode: poweroff\n"
            "  condition: true\n")


def meta_data(environment_id):
    return "instance-id: week6-" + environment_id + "\nlocal-hostname: week6-clean-room\n"


def secrets_blob(environment):
    lines = []
    for name in SECRET_URLS:
        value = environment.get(name, "")
        require(value.startswith("https://") and "\n" not in value and "'" not in value,
                "missing/non-HTTPS " + name)
        lines.append(name + "='" + value + "'")
    for name in PROXY_VARIABLES:
        value = environment.get(name, "")
        require("\n" not in value and "'" not in value, "unsafe proxy variable " + name)
        if value:
            lines.append(name + "='" + value + "'")
    blob = ("\n".join(lines) + "\n").encode()
    require(len(blob) < SECRETS_BYTES, "secrets blob too large")
    return blob + b"\0" * (SECRETS_BYTES - len(blob))


def qemu_argv(qemu, overlay, evidence, secrets, seed, console, vcpus, memory_gb):
    argv = [str(qemu), "-machine", "q35,accel=kvm", "-cpu", "host", "-smp", str(vcpus),
            "-m", str(memory_gb) + "G", "-display", "none", "-no-reboot",
            "-serial", "file:" + str(console),
            # SeaBIOS boots only the first hard disk it enumerates; without an
            # explicit bootindex the evidence disk wins and the guest never starts.
            "-drive", "file=" + str(overlay) + ",if=none,format=qcow2,cache=unsafe,id=root",
            "-device", "virtio-blk-pci,drive=root,bootindex=0",
            "-drive", "file=" + str(evidence) + ",if=none,format=raw,id=evidence",
            "-device", "virtio-blk-pci,drive=evidence,serial=week6-evidence",
            "-drive", "file=" + str(secrets) + ",if=none,format=raw,id=secrets,readonly=on",
            "-device", "virtio-blk-pci,drive=secrets,serial=week6-secrets",
            "-drive", "file=" + str(seed) + ",if=virtio,format=raw,readonly=on",
            "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0"]
    require(not any(flag in item for item in argv for flag in SHARED_FILESYSTEM_FLAGS),
            "shared host filesystem is not allowed")
    return argv


def evidence_members(archive):
    """Inventory the guest tar; only regular files/directories under the two allowed prefixes."""
    canonical = CANONICAL.relative_to("/").as_posix() + "/"
    run = GUEST_RUN.relative_to("/").as_posix() + "/"
    members = {}
    with tarfile.open(archive, "r:") as tar:
        for member in tar:
            name = member.name
            require(not name.startswith("/") and all(part not in ("", ".", "..") for part in name.split("/")),
                    "unsafe guest evidence member: " + name)
            require(member.isfile() or member.isdir(), "special/link guest evidence member: " + name)
            if member.isdir():
                continue
            boundary = canonical + CLEAN_ROOM_OUT.rsplit("/", 1)[0] + "/"
            if name.startswith(boundary):
                top = name[len(boundary):].split("/", 1)[0]
                require(not top.startswith(RESTORED_ROOT_PREFIXES),
                        "guest evidence member inside a restored installation root: " + name)
                require(top.startswith("week6-") or name.endswith(DIAGNOSTIC_SUFFIXES),
                        "guest evidence member outside allowed prefixes: " + name)
                target = ("evidence", name[len(canonical):])
            elif name.startswith(run):
                target = ("guest", name[len(run):])
            else:
                raise RuntimeError("guest evidence member outside allowed prefixes: " + name)
            require(name not in members, "duplicate guest evidence member")
            members[name] = target
    require(members, "empty guest evidence archive")
    return members


def extract_evidence(archive, evidence_root, host_dir):
    members = evidence_members(archive)
    evidence_root, host_dir = Path(evidence_root).resolve(), Path(host_dir).resolve()
    targets = {}
    for name, (kind, relative) in members.items():
        base = evidence_root if kind == "evidence" else host_dir / "guest"
        path = base / relative
        require(not path.exists() and not path.is_symlink() and
                not any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(base)),
                "extraction target occupied/linked: " + str(path))
        targets[name] = path
    clean = evidence_root / CLEAN_ROOM_OUT
    require(not clean.exists() and not clean.is_symlink(), "clean-room output already exists in evidence root")
    with tarfile.open(archive, "r:") as tar:
        for member in tar:
            if member.name not in targets:
                continue
            path = targets[member.name]
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = tar.extractfile(member)
            require(stream is not None, "unreadable guest evidence member")
            with path.open("xb") as output:
                shutil.copyfileobj(stream, output, 1024 * 1024)
            path.chmod(0o755 if member.mode & 0o100 else 0o644)
    return sorted(targets)


def destroy(path):
    path = Path(path)
    if path.is_file() and not path.is_symlink():
        size = path.stat().st_size
        with path.open("r+b") as stream:
            remaining = min(size, 64 * 1024 * 1024)
            while remaining > 0:
                block = min(remaining, 1024 * 1024)
                stream.write(b"\0" * block)
                remaining -= block
        path.unlink()
    return not path.exists()


def launch(args, environment=None):
    environment = dict(os.environ if environment is None else environment)
    require(OID.fullmatch(args.commit or ""), "candidate must be a full Git OID")
    image = Path(args.image).resolve()
    require(image.is_file() and sha(image) == IMAGE_SHA256, "base image is not the pinned " + IMAGE_NAME)
    for tool in [args.qemu, args.qemu_img, args.cloud_localds]:
        require(Path(tool).is_file() and os.access(tool, os.X_OK), "host tool missing: " + str(tool))
    evidence_root = Path(args.evidence_root).resolve()
    require(evidence_root.is_dir() and (evidence_root / ".git").exists() and
            evidence_root != BOOTSTRAP_ROOT.resolve(), "evidence root must be a distinct candidate checkout")
    head = run_host(["/usr/bin/git", "rev-parse", "HEAD"], evidence_root, 30)
    require(head.returncode == 0 and head.stdout.decode().strip() == args.commit,
            "evidence root is not at the candidate commit")
    out = new_directory(args.out)
    environment_id = str(uuid.uuid4())
    started = stamp()
    overlay, evidence, secrets = out / "overlay.qcow2", out / "evidence.raw", out / "secrets.raw"
    seed, console = out / "seed.iso", out / "console.log"
    (out / "user-data").write_text(user_data(args.commit, environment_id))
    (out / "meta-data").write_text(meta_data(environment_id))
    with secrets.open("xb") as stream:
        stream.write(secrets_blob(environment))
    secrets.chmod(0o600)
    record = {"schema_version": 1, "kind": RECORD_KIND, "status": "launch_failed",
              "provider": {"kind": PROVIDER_KIND, "environment_id": environment_id,
                           "image": IMAGE_NAME, "image_digest": "sha256:" + IMAGE_SHA256}}
    try:
        localds = run_host([args.cloud_localds, seed, out / "user-data", out / "meta-data"], out, 120)
        require(localds.returncode == 0, "cloud-init seed creation failed")
        created = run_host([args.qemu_img, "create", "-f", "qcow2", "-F", "qcow2", "-b", image, overlay,
                            str(args.disk_gb) + "G"], out, 120)
        require(created.returncode == 0, "overlay creation failed")
        with evidence.open("xb") as stream:
            stream.truncate(args.evidence_gb * 1024 ** 3)
        version = run_host([args.qemu, "--version"], out, 30)
        require(version.returncode == 0, "qemu version probe failed")
        argv = qemu_argv(args.qemu, overlay, evidence, secrets, seed, console, args.vcpus, args.memory_gb)
        with (out / "qemu.stdout").open("xb") as a, (out / "qemu.stderr").open("xb") as b:
            qemu = run_host(argv, out, args.timeout_hours * 3600, stdout=a, stderr=b)
        finished = stamp()
        require(destroy(secrets), "secrets disk not destroyed")
        require(qemu.returncode == 0, "qemu exited " + str(qemu.returncode))
        require(console.is_file(), "console log absent")
        host_dir = out / "host"
        host_dir.mkdir()
        extracted = extract_evidence(evidence, evidence_root, host_dir)
        exit_file = host_dir / "guest/exit-code"
        require(exit_file.is_file(), "guest exit code absent")
        guest_code = int(exit_file.read_text().strip())
        clean_dir = evidence_root / CLEAN_ROOM_OUT
        report = clean_dir / "report.json"
        require(guest_code == 0 and report.is_file(), "guest controller failed: exit " + str(guest_code))
        record_host = clean_dir / "host"
        record_host.mkdir()
        for name in ["console.log", "user-data", "meta-data"]:
            shutil.copyfile(out / name, record_host / name)
        for name in ["controller.stdout", "controller.stderr", "exit-code"]:
            shutil.copyfile(host_dir / "guest" / name, record_host / ("guest-" + name))
        evidence_sha = sha(evidence)
        require(destroy(overlay) and destroy(evidence), "overlay/evidence disk not destroyed")
        record.update({
            "status": RECORD_STATUS,
            "hypervisor": {"executable": str(args.qemu), "executable_sha256": sha(args.qemu),
                           "version": version.stdout.decode(errors="replace").strip().splitlines()[0],
                           "accelerator": "kvm"},
            "disks": {"base_image_sha256": IMAGE_SHA256,
                      "overlay": {"created_at": started, "virtual_size_bytes": args.disk_gb * 1024 ** 3,
                                  "destroyed": True},
                      "evidence": {"virtual_size_bytes": args.evidence_gb * 1024 ** 3,
                                   "archive_sha256": evidence_sha, "destroyed": True},
                      "secrets": {"destroyed": True}},
            "seed": {"user_data_sha256": sha(out / "user-data"), "meta_data_sha256": sha(out / "meta-data")},
            "launch": {"argv": argv, "started_at": started, "finished_at": finished,
                       "exit_code": qemu.returncode, "console_log": ref(clean_dir, record_host / "console.log")},
            "guest": {"controller_exit_code": guest_code,
                      "controller_stdout": ref(clean_dir, record_host / "guest-controller.stdout"),
                      "controller_stderr": ref(clean_dir, record_host / "guest-controller.stderr"),
                      "packages": GUEST_PACKAGES, "extracted_members": len(extracted)},
            "report": {"path": "report.json", "sha256": sha(report)},
            "boundaries": {"release_claimed": False, "week6_closed": False, "clean_room_claimed": False,
                           "platform_signed_identity": False, "operator_attested": True,
                           "overlay_destroyed": True, "secrets_destroyed": True,
                           "shared_filesystem_absent": True}})
        write_json(clean_dir / RECORD, record)
        summary = {"status": record["status"], "environment_id": environment_id,
                   "record": ref(evidence_root, clean_dir / RECORD),
                   "report": ref(evidence_root, report), "extracted_members": len(extracted)}
        write_json(out / "report.json", summary)
        return summary
    except BaseException as error:
        destroy(secrets); destroy(overlay)
        record.update({"finished_at": stamp(), "error": str(error), "error_type": type(error).__name__,
                       "boundaries": {"release_claimed": False, "week6_closed": False,
                                      "clean_room_claimed": False, "secrets_destroyed": not secrets.exists(),
                                      "overlay_destroyed": not overlay.exists()}})
        write_json(out / "report.json", record)
        raise


def plan(args):
    require(OID.fullmatch(args.commit or ""), "candidate must be a full Git OID")
    out = new_directory(args.out)
    environment_id = "PLAN-ONLY-" + str(uuid.uuid4())
    (out / "user-data").write_text(user_data(args.commit, environment_id))
    (out / "meta-data").write_text(meta_data(environment_id))
    argv = qemu_argv(args.qemu, out / "overlay.qcow2", out / "evidence.raw", out / "secrets.raw",
                     out / "seed.iso", out / "console.log", args.vcpus, args.memory_gb)
    summary = {"status": "plan_only_nothing_booted", "image": {"name": IMAGE_NAME, "release": IMAGE_RELEASE,
               "sha256": IMAGE_SHA256, "url": IMAGE_URL}, "provider_image": PROVIDER_IMAGE,
               "qemu_argv": argv, "guest_packages": GUEST_PACKAGES,
               "seed": {"user_data_sha256": sha(out / "user-data"), "meta_data_sha256": sha(out / "meta-data")},
               "secret_inputs_read_from_environment_at_launch": SECRET_URLS,
               "boundaries": {"clean_room_claimed": False, "release_claimed": False, "week6_closed": False}}
    write_json(out / "report.json", summary)
    return summary


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--mode", choices=["plan", "run"], default="plan")
    result.add_argument("--commit", required=True)
    result.add_argument("--image", type=Path, help="local copy of the pinned cloud image (run mode)")
    result.add_argument("--evidence-root", type=Path, help="fresh candidate checkout receiving the evidence")
    result.add_argument("--out", required=True, type=Path, help="new launcher output directory")
    result.add_argument("--qemu", type=Path, default=Path("/usr/bin/qemu-system-x86_64"))
    result.add_argument("--qemu-img", type=Path, default=Path("/usr/bin/qemu-img"))
    result.add_argument("--cloud-localds", type=Path, default=Path("/usr/bin/cloud-localds"))
    result.add_argument("--vcpus", type=int, default=16)
    result.add_argument("--memory-gb", type=int, default=24)
    result.add_argument("--disk-gb", type=int, default=96)
    result.add_argument("--evidence-gb", type=int, default=24)
    result.add_argument("--timeout-hours", type=int, default=12)
    return result


def main():
    args = parser().parse_args()
    try:
        require(args.vcpus > 0 and args.memory_gb > 0 and args.disk_gb >= 48 and args.evidence_gb >= 8 and
                args.timeout_hours > 0, "unreasonable guest sizing")
        if args.mode == "plan":
            print(json.dumps(plan(args), indent=2, sort_keys=True))
            return 0
        require(args.image is not None and args.evidence_root is not None,
                "--image and --evidence-root are required in run mode")
        print(json.dumps(launch(args), indent=2, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print("Week6 ephemeral VM launcher rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
