#!/usr/bin/env python3
"""Execute the fixed clean-room chain in a fresh canonical checkout.

The public mode owns the checkout and the eleven-stage transcript.  The private
stage mode accepts only a stage name from the policy and a state file created
by the public mode.  Fixed-input URLs are read from the environment and are
never persisted in argv or JSON.  Every stage's stdout/stderr is hash-bound in
the report; the report plus the host launcher's provenance record form the
clean_room slot once the external CI record exists.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_common as common

BOOTSTRAP_ROOT = Path(__file__).resolve().parents[1]
require, sha, read, write, ref = common.require, common.sha, common.read, common.write, common.ref
POLICY = common.load_policy(BOOTSTRAP_ROOT)
REPOSITORY = POLICY["repository"]
CANONICAL = Path(POLICY["canonical_checkout"])
STAGES = POLICY["clean_room"]["stages"]
TOOLS = POLICY["clean_room"]["tools"]
GENERATED_ROOTS = POLICY["clean_room"]["generated_roots"]
FIXED = POLICY["fixed_inputs"]
OUT_NAME = "artifacts/boundary-check/clean-room"
SECRET_URLS = {"WEEK6_INSTALL_ARCHIVE_URL", "WEEK6_INSTALL_MANIFEST_URL", "WEEK6_DECODER_ARCHIVE_URL"}
INJECTION_ENV = {"BASH_ENV", "ENV", "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "MAKEFLAGS"}
TOOL_ENV_PREFIXES = ("CARGO", "RUST", "OPAM", "OCAML", "CHARON", "AENEAS", "ELAN", "LEAN", "SAIL", "MIRI", "SCCACHE", "CCACHE")
# These stages run cargo/the differential tool and must see the fixed toolchains
# directly, never the Ubuntu rustup proxy (which would honour rust-toolchain.toml
# and try to download a toolchain).
NATIVE_STAGES = {"rust-tests", "runtime"}
IGNORED_EVIDENCE_PARENTS = ["boundary-check", "generation-runs", "proof-check", "rocq-spike", "release-audit"]
RUST_TOOLCHAIN = "1.97.1-x86_64-unknown-linux-gnu"
# Every host command the fixed installations and build scripts call.  Unpinned
# entries must exist; pinned ones must match the reviewed Ubuntu 24.04 binary.
HOST_EXECUTABLES = {
    name: {"path": "/usr/bin/" + name, "sha256": None, "probe": None}
    for name in ["git", "make", "bash", "sh", "python3", "cmake", "ninja", "cc", "c++", "gcc", "g++", "ar", "ld", "ranlib",
                 "pkg-config", "z3", "awk", "sed", "sort", "head", "sha256sum", "nproc", "tar", "gzip", "bzip2", "xz", "patch",
                 "curl"]
}
HOST_EXECUTABLES["opam"] = {"path": "/usr/bin/opam", "sha256": "22222e47a7bbe31946500457a8e6da4fa789afc78bc0c7593b00a328a5b6f615",
                            "probe": ["--version"]}
HOST_EXECUTABLES["rustup"] = {"path": "/usr/bin/rustup", "sha256": "be178b5cdda17e6ab5027dcdd5262014a9e967f02f439b2da618942af5cbad27",
                              "probe": ["--version"]}
HOST_EXECUTABLES["jq"] = {"path": "/usr/bin/jq", "sha256": "59cfd58d7e470b103aede0e7589cfea929e45ee27f5471f08aa9676ac7bfc566",
                          "probe": ["--version"]}
HOST_EXECUTABLES["m4"] = {"path": "/usr/bin/m4", "sha256": "426fbab900b6c676038cf71da51c3ae45a6d546c9580fff9372bc5b1bb81d576",
                          "probe": ["--version"]}
OID = common.GIT_OID


def command(argv, cwd, codes=(0,), env=None, timeout=21600):
    result = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    require(result.returncode in codes, "command failed (exit " + str(result.returncode) + "): " + argv[0])
    return result


def checked_state(value):
    common.fields(value, {"schema_version", "kind", "repository", "candidate", "canonical_checkout", "output"}, "clean-room state")
    require(value["schema_version"] == 1 and value["kind"] == "clean-room-state-v2" and value["repository"] == REPOSITORY and
            OID.fullmatch(value["candidate"] or "") and Path(value["canonical_checkout"]) == CANONICAL, "clean-room state identity")
    root, out = Path(value["canonical_checkout"]), Path(value["output"])
    require(out == root / OUT_NAME and out.is_dir() and not out.is_symlink(), "clean-room output identity differs")
    return root, out


def download(variable, destination, expected):
    url = os.environ.get(variable, "")
    require(url.startswith("https://"), "missing/non-HTTPS " + variable)
    destination = Path(destination)
    require(not destination.exists() and not destination.is_symlink(), "download destination exists")
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=120) as source, destination.open("xb") as target:
            while block := source.read(1024 * 1024):
                digest.update(block)
                target.write(block)
    except Exception:
        # URL values may carry bearer material; never copy urllib's message into the log.
        raise RuntimeError("fixed input download failed: " + variable) from None
    require(digest.hexdigest() == expected and sha(destination) == expected, "downloaded input hash differs: " + variable)


def host_preflight(out, executables=None, os_release=Path("/etc/os-release"), machine=None):
    executables = HOST_EXECUTABLES if executables is None else executables
    machine = platform.machine() if machine is None else machine
    require(machine == "x86_64", "clean-room host architecture differs")
    values = {}
    for line in Path(os_release).read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    require(values.get("ID") == "ubuntu" and values.get("VERSION_ID") == "24.04", "clean-room host is not Ubuntu 24.04")
    observed = {}
    # Probe outside the checkout with throwaway Rust homes so the rustup proxy
    # cannot honour rust-toolchain.toml and fetch a toolchain from the network.
    probe_root = Path(tempfile.mkdtemp(prefix="clean-room-host-probe-"))
    probe_env = base_environment(os.environ)
    probe_env.update(RUSTUP_HOME=str(probe_root / "rustup-home"), CARGO_HOME=str(probe_root / "cargo-home"),
                     RUSTUP_NO_UPDATE_CHECK="1", RUSTUP_TOOLCHAIN="none")
    try:
        for name, spec in executables.items():
            path = Path(spec["path"])
            require(path.is_file() and os.access(path, os.X_OK), "required host executable missing: " + name)
            digest = sha(path.resolve())
            require(spec["sha256"] is None or digest == spec["sha256"], "pinned host executable differs: " + name)
            version = None
            if spec.get("probe") is not None:
                result = command([str(path), *spec["probe"]], probe_root, env=probe_env, timeout=30)
                version = (result.stdout + result.stderr).decode(errors="replace").strip()
                require(version and "syncing channel" not in version and "downloading" not in version,
                        "host executable probe attempted a network fetch: " + name)
            observed[name] = {"path": str(path), "sha256": digest, "version": version}
    finally:
        shutil.rmtree(probe_root, ignore_errors=True)
    report = {"schema_version": 1, "kind": "clean-room-host-preflight-v2", "architecture": machine,
              "os_release": {key: values[key] for key in ["ID", "VERSION_ID"]}, "executables": observed}
    write(Path(out) / "host-preflight.json", report)
    return report


def tool_paths(root):
    base = root / "artifacts/boundary-check"
    return {
        "rust": base / "isolated-rust-lean-ad7o1fsn/rustup/toolchains" / RUST_TOOLCHAIN / "bin/rustc",
        "sail": base / "isolated-sail-nrdi23ds/sail-install/bin/sail",
        "aeneas": root / "artifacts/decoder-inputs/rebuilt-v2/payload/bin/base/aeneas",
        "charon": root / "artifacts/decoder-inputs/rebuilt-v2/payload/bin/base/charon",
        "lean": base / "isolated-rust-lean-ad7o1fsn/elan/toolchains/leanprover--lean4---v4.31.0/bin/lean",
        "rocq": base / "isolated-rocq-ac54t6f8/opam-root/isolated-rocq/bin/rocq",
    }


def tool_version_args(name):
    return ["-version"] if name == "aeneas" else ["version"] if name == "charon" else ["--version"]


def record_tools(root, out):
    tools = {}
    for name in TOOLS:
        path = tool_paths(root)[name]
        require(path.is_file() and not path.is_symlink(), "fixed tool missing: " + name)
        result = command([str(path), *tool_version_args(name)], root)
        version = (result.stdout + result.stderr).decode(errors="replace").strip()
        require(version, "empty tool version: " + name)
        tools[name] = {"version": version, "executable_sha256": sha(path)}
    write(out / "tool-identities.json", tools)
    return tools


def configure_sail_build(root):
    """Configure the Sail emulator build with the fixed compiler, as build_sail_emulator.sh
    would, so the later ``make sail-emu`` only builds and the formal resolver finds it."""
    import rebuilt_main_tools as tools
    compiler = tool_paths(root)["sail"]
    require(compiler.is_file() and not compiler.is_symlink(), "fixed Sail compiler missing")
    build = root / "deps/sail-riscv/build"
    require(not build.exists() and not build.is_symlink(), "Sail CMake build already exists in the fresh checkout")
    command(["/usr/bin/cmake", "-S", "deps/sail-riscv", "-B", "deps/sail-riscv/build", "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
             "-DDOWNLOAD_GMP=TRUE", "-DSAIL_BIN:FILEPATH=" + str(compiler)], root, timeout=1800)
    tools.cmake_compiler(root, compiler)


def tree_digest(directory):
    """Digest of (path, mode, sha256) for every regular file below a generated root."""
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "generated root missing: " + str(directory))
    rows = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.is_symlink():
            rows.append([path.relative_to(directory).as_posix(), path.stat().st_mode & 0o777, sha(path)])
    return common.sha_bytes(json.dumps(rows, separators=(",", ":")).encode())


def copy_top_files(source, destination):
    destination.mkdir()
    for path in sorted(Path(source).iterdir()):
        if path.is_file() and not path.is_symlink() and not path.name.startswith("."):
            shutil.copyfile(path, destination / path.name)


def stage_action(name, state_path):
    state_path = Path(state_path).absolute()
    require(state_path.is_file() and not state_path.is_symlink(), "clean-room state file missing/linked")
    state = read(state_path)
    root, out = checked_state(state)
    require(state_path == out / "state.json", "clean-room state path differs")
    candidate = state["candidate"]
    sys.path.insert(0, str(root / "scripts"))
    python = ["/usr/bin/python3", "-B", "-O"]

    if name == "snapshot":
        import source_snapshot
        snapshot = source_snapshot.capture(root)
        require(snapshot["repositories"]["."]["head"] == candidate, "checkout head differs")
        write(out / "source-snapshot.json", snapshot)
    elif name == "install":
        import decoder_rebuilt_inputs as rebuilt
        import fixed_inputs
        host_preflight(out)
        inputs = out / "fixed-inputs"
        inputs.mkdir()
        archive, manifest = inputs / "extra-installations.tar.xz", inputs / "manifest.json"
        decoder = inputs / "rebuilt-decoder-candidate.tar.gz"
        download("WEEK6_INSTALL_ARCHIVE_URL", archive, FIXED["extra-installations.tar.xz"]["sha256"])
        download("WEEK6_INSTALL_MANIFEST_URL", manifest, FIXED["manifest.json"]["sha256"])
        download("WEEK6_DECODER_ARCHIVE_URL", decoder, FIXED["rebuilt-decoder-candidate.tar.gz"]["sha256"])
        for variable in SECRET_URLS:
            os.environ.pop(variable, None)
        require(archive.stat().st_size == FIXED["extra-installations.tar.xz"]["size"], "fixed install archive size differs")
        staged = out / "fixed-install-staging"
        fixed_inputs.stage(archive, manifest, FIXED["manifest.json"]["sha256"], staged)
        install_manifest = fixed_inputs.load_manifest(manifest, FIXED["manifest.json"]["sha256"])
        require(install_manifest["canonical_checkout"] == str(root), "fixed installation canonical checkout differs")
        fixed_inputs.install_staged_roots(staged, root, install_manifest["entries"])
        shutil.rmtree(staged)
        destination = root / "artifacts/decoder-inputs/rebuilt-v2"
        receipt = rebuilt.install(decoder, destination)
        require(receipt["archive_sha256"] == FIXED["rebuilt-decoder-candidate.tar.gz"]["sha256"] and
                receipt["installation"]["payload"] == str(destination / "payload"), "decoder installation identity differs")
        record_tools(root, out)
    elif name == "configure-sail":
        configure_sail_build(root)
    elif name == "regenerate":
        command([*python, "scripts/generate_rebuilt_rust.py"], root)
        command(["/usr/bin/make", "sail-config"], root)
        command(["/usr/bin/bash", "scripts/generate_proof_model.sh", "lean"], root)
    elif name == "rust-tests":
        command([*python, "scripts/runtime_evidence.py", "tests", "--out", str(out / "rust-tests")], root)
    elif name == "runtime":
        command([*python, "scripts/runtime_evidence.py", "run", "--out", str(out / "runtime"),
                 "--tests-report", str(out / "rust-tests/report.json")], root)
        replay = out / "replay-inputs"
        replay.mkdir()
        for source, target in [("deps/sail-riscv/build/c_emulator/sail_riscv_sim", "sail_riscv_sim"),
                               ("sail-model/build/ckb_vm_config.json", "ckb_vm_config.json")]:
            shutil.copyfile(root / source, replay / target)
            (replay / target).chmod(0o755 if target == "sail_riscv_sim" else 0o644)
    elif name == "lean-kernel":
        command(["/usr/bin/make", "proof-check", "BACKEND=lean"], root)
        copy_top_files(root / "artifacts/proof-check", out / "lean")
        require(read(out / "lean/report.json")["status"] == "passed", "Lean gate did not pass")
    elif name == "rocq-spike":
        import check_proof as proof
        import rebuilt_main_tools as tools
        env, _, _, _ = tools.resolve(root, read(proof.POLICY))
        for key in ["PROOF_BUILD_TIMEOUT", "BASH_ENV", "ENV", "ROCQ_SPIKE_SWITCH"]:
            env.pop(key, None)
        env["ROCQ_SPIKE_WORK"] = str(out / "rocq")
        command(["/usr/bin/make", "proof-spike"], root, env=env)
        require(read(out / "rocq/report.json")["verdict"] == "NO-GO", "Rocq spike verdict differs")
    elif name == "tree-clean":
        status = command(["/usr/bin/git", "status", "--porcelain", "--ignore-submodules=dirty"], root).stdout.decode()
        require(status.strip() == "", "tracked files changed during the clean-room chain:\n" + status)
        write(out / "generated-roots.json", {name: tree_digest(root / name) for name in GENERATED_ROOTS})
    elif name == "public-claims":
        command([*python, "scripts/public_claims.py", "--out", str(out / "public-claims.json")], root)
    else:
        raise RuntimeError("stage action is not internal: " + name)


def new_output(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    require(path == root / OUT_NAME and not path.exists() and not path.is_symlink(), "new canonical clean-room output required")
    require(not any(parent.is_symlink() for parent in (path.parent, *path.parent.parents)), "linked clean-room output ancestor")
    # Git ignores artifacts/*/; the generators insist their parents exist.
    for name in IGNORED_EVIDENCE_PARENTS:
        (root / "artifacts" / name).mkdir(parents=True, exist_ok=True)
    path.mkdir()
    return path


def stage_row(out, name, argv, cwd, env, timeout=21600):
    row = common.run_command(out, name, argv, cwd, env=env, timeout=timeout)
    row["cwd"] = Path(cwd).relative_to(CANONICAL).as_posix() or "."
    require(row["exit_code"] == 0, "clean-room stage failed: " + name)
    return row


def provider():
    kind = os.environ.get("CLEAN_ROOM_PROVIDER", "")
    image = os.environ.get("CLEAN_ROOM_IMAGE", "")
    match = re.fullmatch(r"(.+)@(sha256:[0-9a-f]{64})", image)
    environment_id = os.environ.get("CLEAN_ROOM_ENVIRONMENT_ID", "")
    require(kind in POLICY["clean_room"]["providers"] and match and environment_id, "approved provider/image/environment id absent")
    return {"kind": kind, "environment_id": environment_id, "image": match.group(1), "image_digest": match.group(2),
            "created_at": common.stamp(), "ephemeral": True, "original_workspace_mounted": False}


def base_environment(environment):
    result = {key: value for key, value in environment.items()
              if key not in SECRET_URLS | INJECTION_ENV and not key.startswith(TOOL_ENV_PREFIXES) and not key.startswith("GIT_")}
    result.update(PATH="/usr/bin:/bin", LC_ALL="C", LANG="C", TZ="UTC", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                  GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="core.hooksPath",
                  GIT_CONFIG_VALUE_0="/dev/null", GIT_CONFIG_KEY_1="core.fsmonitor", GIT_CONFIG_VALUE_1="false")
    # libcurl reads lower-case proxy variables first and treats an empty one as
    # "no proxy"; make git's proxy explicit and never pass an empty variant.
    for key in ["https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"]:
        if result.get(key):
            result.update(GIT_CONFIG_COUNT="3", GIT_CONFIG_KEY_2="http.proxy", GIT_CONFIG_VALUE_2=result[key])
            break
    for key in ["https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY", "no_proxy", "NO_PROXY"]:
        if key in result and not result[key]:
            del result[key]
    return result


def stage_environment(environment, name):
    require(name in STAGES[1:], "unknown stage environment")
    result = base_environment(environment)
    if name == "install":
        result.update({key: environment[key] for key in SECRET_URLS if key in environment})
    if name in NATIVE_STAGES:
        rustup = CANONICAL / "artifacts/boundary-check/isolated-rust-lean-ad7o1fsn/rustup"
        prefix = rustup / "toolchains" / RUST_TOOLCHAIN / "bin"
        result.update(PATH=str(prefix) + ":" + str(tool_paths(CANONICAL)["sail"].parent) + ":/usr/bin:/bin",
                      RUSTUP_HOME=str(rustup), RUSTUP_TOOLCHAIN=RUST_TOOLCHAIN, RUSTUP_NO_UPDATE_CHECK="1",
                      CARGO_HOME=str(CANONICAL / OUT_NAME / (name + "-cargo-home")), CARGO_TERM_COLOR="never")
    return result


NETWORK_ATTEMPTS = 3


def network_command(argv, cwd, reset=None):
    """Bounded retries for the network-bound git steps; pinned commits make retries safe."""
    for attempt in range(1, NETWORK_ATTEMPTS + 1):
        try:
            return command(argv, cwd, timeout=1800)
        except RuntimeError as error:
            print("network step attempt " + str(attempt) + " failed: " + str(error), file=sys.stderr)
            if attempt == NETWORK_ATTEMPTS:
                raise
            if reset is not None:
                reset()


def bootstrap_checkout(commit):
    require(OID.fullmatch(commit or "") and CANONICAL.is_dir() and not CANONICAL.is_symlink() and not any(CANONICAL.iterdir()),
            "bootstrap checkout target/candidate differs")

    def empty_canonical():
        for entry in CANONICAL.iterdir():
            shutil.rmtree(entry) if entry.is_dir() and not entry.is_symlink() else entry.unlink()

    network_command(["/usr/bin/git", "clone", "--no-checkout", "https://github.com/" + REPOSITORY + ".git", "."],
                    CANONICAL, reset=empty_canonical)
    command(["/usr/bin/git", "checkout", "--detach", commit], CANONICAL, timeout=1800)
    network_command(["/usr/bin/git", "submodule", "update", "--init", "--recursive"], CANONICAL)
    for argv in [["/usr/bin/make", "ckb-baseline-apply"], ["/usr/bin/git", "fsck", "--full"]]:
        command(argv, CANONICAL, timeout=1800)


def public_run(args):
    require(OID.fullmatch(args.commit or ""), "candidate must be a full commit OID")
    require(CANONICAL.resolve() != BOOTSTRAP_ROOT.resolve() and not CANONICAL.exists() and not CANONICAL.is_symlink(),
            "canonical checkout must be fresh and distinct from bootstrap")
    provider_row = provider()
    base_env = base_environment(os.environ)
    CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="clean-room-checkout-", dir=CANONICAL.parent))
    CANONICAL.mkdir(exist_ok=False)
    checkout_argv = ["/usr/bin/python3", "-B", "-O", str(Path(__file__).resolve()), "_bootstrap-recursive-checkout",
                     "--commit", args.commit]
    with (temporary / "stdout").open("xb") as a, (temporary / "stderr").open("xb") as b:
        result = subprocess.run(checkout_argv, cwd=CANONICAL, stdin=subprocess.DEVNULL, stdout=a, stderr=b, timeout=1800, env=base_env)
    require(result.returncode == 0, "recursive checkout failed")
    out = new_output(CANONICAL, args.out)
    shutil.move(temporary / "stdout", out / "checkout.stdout")
    shutil.move(temporary / "stderr", out / "checkout.stderr")
    temporary.rmdir()
    write(out / "state.json", {"schema_version": 1, "kind": "clean-room-state-v2", "repository": REPOSITORY,
                               "candidate": args.commit, "canonical_checkout": str(CANONICAL), "output": str(out)})
    require(sha(CANONICAL / "scripts/clean_room.py") == sha(Path(__file__)), "checked-out controller differs from bootstrap")
    stages = [{"name": "checkout", "argv": checkout_argv, "cwd": ".", "exit_code": 0,
               "stdout": ref(out, out / "checkout.stdout"), "stderr": ref(out, out / "checkout.stderr")}]
    for name in STAGES[1:]:
        argv = ["/usr/bin/python3", "-B", "-O", "scripts/clean_room.py", "_stage", "--name", name, "--state", str(out / "state.json")]
        stages.append(stage_row(out, name, argv, CANONICAL, stage_environment(os.environ, name)))
    sys.path.insert(0, str(CANONICAL / "scripts"))
    import source_snapshot
    snapshot = read(out / "source-snapshot.json")
    require(source_snapshot.capture(CANONICAL) == snapshot, "source changed after clean-room stages")
    status = command(["/usr/bin/git", "status", "--porcelain", "--ignore-submodules=dirty"], CANONICAL, env=base_env).stdout.decode().strip()
    report = {"schema_version": 2, "kind": "clean-room-evidence-v2", "status": "passed", "candidate": args.commit,
              "provider": provider_row,
              "checkout": {"repository": REPOSITORY, "head": args.commit,
                           "submodules": {name: snapshot["repositories"][name]["head"] for name in source_snapshot.REPOS[1:]},
                           "overlay_applied": True, "worktree_status": status, "log": stages[0]["stdout"]},
              "tools": read(out / "tool-identities.json"), "source_snapshot": ref(out, out / "source-snapshot.json"),
              "stages": stages, "generated_roots": read(out / "generated-roots.json"),
              "slots": {"runtime": ref(out, out / "runtime/report.json"), "lean": ref(out, out / "lean/report.json"),
                        "rocq": ref(out, out / "rocq/report.json"), "public_claims": ref(out, out / "public-claims.json")},
              "boundaries": {"release_claimed": False, "week6_closed": False, "fresh_execution_claimed": True}}
    write(out / "report.json", report)
    # The guest's own aggregate: the three local slots must verify now; clean_room
    # stays incomplete until the host writes its provenance record.
    command(["/usr/bin/python3", "-B", "-O", "scripts/audit_release.py", "--candidate", args.commit,
             "--runtime", str(out / "runtime/report.json"), "--lean", str(out / "lean/report.json"),
             "--rocq", str(out / "rocq/report.json"), "--clean-room", str(out / "report.json"),
             "--out", str(out / "audit")], CANONICAL, codes=(2,), env=base_env)
    audit = read(out / "audit/report.json")
    require(audit["status"] == "incomplete" and audit["invalid"] == [] and
            all(audit["slots"][name]["status"] == "verified" for name in ("runtime", "lean", "rocq")) and
            audit["slots"]["clean_room"]["status"] == "incomplete", "guest aggregate did not verify the local slots")
    return report


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="mode")
    internal = sub.add_parser("_stage", help=argparse.SUPPRESS)
    internal.add_argument("--name", required=True, choices=STAGES[1:])
    internal.add_argument("--state", required=True, type=Path)
    bootstrap = sub.add_parser("_bootstrap-recursive-checkout", help=argparse.SUPPRESS)
    bootstrap.add_argument("--commit", required=True)
    result.add_argument("--commit")
    result.add_argument("--out", type=Path)
    return result


def main():
    args = parser().parse_args()
    try:
        if args.mode == "_stage":
            stage_action(args.name, args.state.absolute())
            return 0
        if args.mode == "_bootstrap-recursive-checkout":
            bootstrap_checkout(args.commit)
            return 0
        require(args.commit and args.out, "--commit and --out are required")
        print(json.dumps(public_run(args), indent=2, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print("clean-room rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
