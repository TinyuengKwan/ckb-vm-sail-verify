#!/usr/bin/env python3
"""Execute the fixed Week6 clean-room chain in a fresh canonical checkout.

The public mode owns checkout and the exact sixteen-stage transcript.  The
private stage mode is deliberately non-extensible: it accepts only a stage
name from REQUIRED_STAGES and a state file created by the public mode.  Input
URLs are read from the environment and are never persisted in argv or JSON.
"""

import argparse
import datetime
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


BOOTSTRAP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "TinyuengKwan/ckb-vm-sail-verify"
CANONICAL = Path("/home/clair/tinyueng_workplace/ckb-vm-sail-verify")
INSTALL_ARCHIVE_SHA = "c8e8ca2797aeabcbee3935949f6ad6b622a40468d77a7f5d79a50b1854a67ff4"
INSTALL_MANIFEST_SHA = "ac7b468e6715e6a4b956376a0ded0ee6e4d9cfc632d4323b439877916e74708e"
DECODER_ARCHIVE_SHA = "1a81921b12215a87106ac2080c05de3f2bf9d51b9bb14bdb80a90ac8c05c58d5"
REQUIRED_STAGES = [
    "recursive-checkout", "verify-source-snapshot", "install-rust", "install-sail",
    "install-aeneas-charon", "install-lean", "install-rocq", "rebuild-rust-model",
    "rebuild-sail-model", "rust-tests", "runtime-differential", "mutation-matrix",
    "lean-kernel", "rocq-spike", "worktree-audit", "public-claims",
]
TOOL_STAGE = {"rust": "install-rust", "sail": "install-sail",
              "aeneas": "install-aeneas-charon", "charon": "install-aeneas-charon",
              "lean": "install-lean", "rocq": "install-rocq"}
PUBLIC_BOUNDARIES = {"ci_download_verified", "clean_room_claimed", "fresh_execution_claimed",
                     "release_claimed", "release_package_built", "remote_state_queried",
                     "third_party_reproduced", "week6_closed"}
SECRET_URLS = {"WEEK6_INSTALL_ARCHIVE_URL", "WEEK6_INSTALL_MANIFEST_URL", "WEEK6_DECODER_ARCHIVE_URL"}
INJECTION_ENV = {"BASH_ENV", "ENV", "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH",
                 "PYTHONSTARTUP", "MAKEFLAGS"}
TOOL_ENV_PREFIXES = ("CARGO", "RUST", "OPAM", "OCAML", "CHARON", "AENEAS", "ELAN", "LEAN",
                     "SAIL", "MIRI", "SCCACHE", "CCACHE")
NATIVE_STAGES = {"rust-tests", "runtime-differential", "mutation-matrix"}
RUST_TOOLCHAIN = "1.97.1-x86_64-unknown-linux-gnu"
HOST_EXECUTABLES = {
    name: {"path": "/usr/bin/" + name, "sha256": None, "probe": None}
    for name in ["git", "make", "bash", "python3", "cmake", "ninja", "cc", "c++",
                 "pkg-config", "z3", "script"]
}
HOST_EXECUTABLES["opam"] = {"path": "/usr/bin/opam",
                            "sha256": "22222e47a7bbe31946500457a8e6da4fa789afc78bc0c7593b00a328a5b6f615",
                            "probe": ["--version"]}
OID = re.compile(r"[0-9a-f]{40}")
HEX = re.compile(r"[0-9a-f]{64}")


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


def read(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)


def write(path, value, exclusive=True):
    mode = "x" if exclusive else "w"
    with Path(path).open(mode) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def ref(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            "evidence reference outside/missing: " + str(path))
    return {"path": path.relative_to(root).as_posix(), "sha256": sha(path)}


def command(argv, cwd, codes=(0,), env=None, timeout=21600):
    result = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    sys.stdout.flush(); sys.stderr.flush()
    require(result.returncode in codes, "command failed (exit " + str(result.returncode) + "): " + argv[0])
    return result


def checked_config(value):
    require(type(value) is dict and set(value) == {
        "schema_version", "kind", "repository", "candidate", "canonical_checkout",
        "install_archive_sha256", "install_manifest_sha256", "decoder_archive_sha256",
        "review_policy", "output",
    }, "clean-room state fields")
    require(value["schema_version"] == 1 and type(value["schema_version"]) is int and
            value["kind"] == "week6-clean-room-state-v1" and value["repository"] == REPOSITORY and
            OID.fullmatch(value["candidate"] or "") and
            Path(value["canonical_checkout"]) == CANONICAL and
            value["install_archive_sha256"] == INSTALL_ARCHIVE_SHA and
            value["install_manifest_sha256"] == INSTALL_MANIFEST_SHA and
            value["decoder_archive_sha256"] == DECODER_ARCHIVE_SHA,
            "clean-room fixed identity differs")
    root = Path(value["canonical_checkout"])
    policy = root / value["review_policy"]
    out = Path(value["output"])
    require(not Path(value["review_policy"]).is_absolute() and ".." not in Path(value["review_policy"]).parts and
            policy.is_file() and not policy.is_symlink(), "review policy outside/missing")
    require(out.parent == root / "artifacts/boundary-check" and out.name == "week6-clean-room" and
            out.is_dir() and not out.is_symlink(), "clean-room output identity differs")
    return root, out, policy


def download(variable, destination, expected):
    url = os.environ.get(variable, "")
    require(url and re.match(r"^https://", url), "missing/non-HTTPS " + variable)
    destination = Path(destination)
    require(not destination.exists() and not destination.is_symlink(), "download destination exists")
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=120) as source, destination.open("xb") as target:
            while block := source.read(1024 * 1024):
                digest.update(block); target.write(block)
    except Exception as error:
        # URL values may contain bearer material; never copy urllib's message
        # into the stage log.
        raise RuntimeError("fixed input download failed: " + variable) from None
    require(digest.hexdigest() == expected and sha(destination) == expected,
            "downloaded input hash differs: " + variable)


def host_preflight(out, executables=None, os_release=Path("/etc/os-release"), machine=None):
    executables = HOST_EXECUTABLES if executables is None else executables
    machine = platform.machine() if machine is None else machine
    require(machine == "x86_64", "clean-room host architecture differs")
    values = {}
    for line in Path(os_release).read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        require(key not in values, "duplicate os-release field")
        values[key] = value.strip().strip('"')
    require(values.get("ID") == "ubuntu" and values.get("VERSION_ID") == "24.04",
            "clean-room host is not Ubuntu 24.04")
    observed = {}
    for name, specification in executables.items():
        path = Path(specification["path"])
        require(path.is_file() and os.access(path, os.X_OK), "required host executable missing: " + name)
        digest = sha(path.resolve())
        require(specification["sha256"] is None or digest == specification["sha256"],
                "pinned host executable differs: " + name)
        version = None
        if specification.get("probe") is not None:
            result = command([str(path), *specification["probe"]], Path(out).parent,
                             env=base_environment(os.environ), timeout=30)
            version = (result.stdout + result.stderr).decode(errors="replace").strip()
            require(version, "empty host executable probe: " + name)
        observed[name] = {"path": str(path), "resolved_path": str(path.resolve()),
                          "sha256": digest, "version": version}
    report = {"schema_version": 1, "kind": "week6-clean-room-host-preflight-v1",
              "status": "compatible_host_commands_verified", "architecture": machine,
              "os_release": {key: values[key] for key in ["ID", "VERSION_ID"]},
              "executables": observed,
              "boundaries": {"container_identity_verified": False, "host_closure_complete": False,
                             "clean_room_claimed": False, "release_claimed": False,
                             "week6_closed": False}}
    write(Path(out) / "host-preflight.json", report)
    return report


def tool_paths(root):
    base = root / "artifacts/boundary-check"
    return {
        "rust": base / "isolated-rust-lean-ad7o1fsn/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu/bin/rustc",
        "sail": base / "isolated-sail-nrdi23ds/sail-install/bin/sail",
        "aeneas": root / "artifacts/decoder-inputs/rebuilt-v2/payload/bin/base/aeneas",
        "charon": root / "artifacts/decoder-inputs/rebuilt-v2/payload/bin/base/charon",
        "lean": base / "isolated-rust-lean-ad7o1fsn/elan/toolchains/leanprover--lean4---v4.31.0/bin/lean",
        "rocq": base / "isolated-rocq-ac54t6f8/opam-root/isolated-rocq/bin/rocq",
    }


def tool_version_args(name):
    require(name in TOOL_STAGE, "unknown fixed tool")
    return ["-version"] if name == "aeneas" else ["version"] if name == "charon" else ["--version"]


def record_tool(root, out, name):
    path = tool_paths(root)[name]
    require(path.is_file() and not path.is_symlink(), "fixed tool missing: " + name)
    result = command([str(path), *tool_version_args(name)], root)
    version = (result.stdout + result.stderr).decode(errors="replace").strip()
    require(version, "empty tool version: " + name)
    tools_path = out / "tool-identities.json"
    tools = read(tools_path) if tools_path.exists() else {}
    require(name not in tools, "tool identity already recorded: " + name)
    tools[name] = {"version": version, "executable_sha256": sha(path)}
    write(tools_path, tools, exclusive=not tools_path.exists())


def configure_sail_build(root):
    """Configure the Sail emulator CMake build with the fixed compiler.

    A fresh recursive checkout has no deps/sail-riscv/build.  The formal
    resolver requires that cache to name the fixed compiler before the Rust
    model is rebuilt, and sail-riscv's CMake would otherwise search PATH, which
    the stage environment restricts to /usr/bin:/bin.  Configure exactly as
    build_sail_emulator.sh does plus the explicit compiler, so the later
    ``make sail-emu`` only builds, then verify the cache the resolver will read.
    """
    sys.path.insert(0, str(root / "scripts"))
    import rebuilt_main_tools as tools
    compiler = tool_paths(root)["sail"]
    require(compiler.is_file() and not compiler.is_symlink(), "fixed Sail compiler missing")
    build = root / "deps/sail-riscv/build"
    require(not build.exists() and not build.is_symlink(),
            "Sail CMake build already exists in the fresh checkout")
    command(["/usr/bin/cmake", "-S", "deps/sail-riscv", "-B", "deps/sail-riscv/build",
             "-DCMAKE_BUILD_TYPE=RelWithDebInfo", "-DDOWNLOAD_GMP=TRUE",
             "-DSAIL_BIN:FILEPATH=" + str(compiler)], root, timeout=1800)
    tools.cmake_compiler(root, compiler)


def audit_manifest(root, candidate, evidence_rows, path):
    sys.path.insert(0, str(root / "scripts"))
    import audit_release as audit
    value = {"schema_version": 1, "candidate": candidate,
             "pins": {key: sha(root / name) for key, name in audit.PINS.items()},
             "evidence": {name: evidence_rows.get(name) for name in audit.SLOTS}}
    write(path, value)
    return value


def product(root, name):
    return Path(root) / "artifacts/boundary-check" / name


def evidence_rows(root, out, worktree=True, public=False, clean=False):
    native = product(root, "week6-native-clean-room")
    rows = {
        "runtime": ref(root, native / "runtime/report.json"),
        "lean": ref(root, product(root, "week6-formal-clean-room") / "main/report.json"),
        "rocq": ref(root, product(root, "week6-formal-clean-room") / "rocq/report.json"),
        "rust_tests": ref(root, native / "rust-tests/report.json"),
        "mismatches": ref(root, product(root, "week6-mismatch-clean-room") / "inventory.json"),
        "maintainer_demo": ref(root, product(root, "week6-maintainer-demo-clean-room") / "report.json"),
    }
    if worktree:
        rows["worktree_audit"] = ref(
            root, product(root, "week6-review-worktree-envelope") / "worktree-envelope.json")
    if public:
        rows["public_claims"] = ref(root, out / "public-claims/report.json")
    if clean:
        rows["clean_room"] = ref(root, out / "report.json")
    return rows


def produce_negatives(root):
    native = product(root, "week6-native-clean-room")
    command(["/usr/bin/python3", "-B", "-O", "scripts/paired_negative_evidence.py",
             "--out", str(product(root, "week6-paired-negatives-clean-room"))], root)
    binary = native / "runtime/cargo-target/debug/ckb-vm-sail-diff"
    trap = product(root, "week6-trap-clean-room"); trap.mkdir()
    replay = [str(binary), "--replay", "scripts/fixtures/trap-divergence-input.json", "--json",
              "--artifact-dir", str(trap / "original"), "--sail-bin",
              "deps/sail-riscv/build/c_emulator/sail_riscv_sim", "--sail-config",
              "sail-model/build/ckb_vm_config.json"]
    command(replay, root, codes=(1,))
    command(["/usr/bin/python3", "-B", "-O", "scripts/minimize_mismatch.py",
             "--artifact", str(trap / "original/candidate.json"), "--output", str(trap / "minimized"),
             "--classification", "unsupported", "--rationale",
             "The injected 0x0000107b word is outside the supported ADD/ADDI/BEQ scope.",
             "--differential-binary", str(binary)], root)
    mismatch = {"schema_version": 1,
                "runtime": ref(root, native / "runtime/report.json"),
                "rust_tests": ref(root, native / "rust-tests/report.json"),
                "semantic_negative_cases": {
                    "a_diverging_instruction_stream_is_located": ref(
                        root, product(root, "week6-paired-negatives-clean-room") / "report.json"),
                    "a_missing_final_event_is_detected": ref(
                        root, product(root, "week6-paired-negatives-clean-room") / "report.json"),
                    "a_trapping_instruction_diverges_and_is_reported_not_hidden":
                        ref(root, trap / "minimized/report.json")}}
    mismatch_dir = product(root, "week6-mismatch-clean-room"); mismatch_dir.mkdir()
    write(mismatch_dir / "inventory.json", mismatch)
    command(["/usr/bin/python3", "-B", "-O", "-c",
             "from pathlib import Path; import sys; sys.path.insert(0,'scripts'); import release_mismatch_evidence as m; print(m.check_inventory(Path(sys.argv[1])))",
             str(mismatch_dir / "inventory.json")], root)
    command(["/usr/bin/python3", "-B", "-O", "scripts/release_demo.py",
             "--runtime-report", str(native / "runtime/report.json"), "--trap-report",
             str(trap / "minimized/report.json"), "--out",
             str(product(root, "week6-maintainer-demo-clean-room"))], root)


def stage_action(name, state_path):
    state_path = Path(state_path).absolute()
    require(state_path.is_file() and not state_path.is_symlink(), "clean-room state file missing/linked")
    state = read(state_path)
    root, out, policy = checked_config(state)
    require(state_path == out / "state.json", "clean-room state path differs")
    candidate = state["candidate"]
    sys.path.insert(0, str(root / "scripts"))

    if name == "verify-source-snapshot":
        import source_snapshot
        snapshot = source_snapshot.capture(root)
        require(snapshot["repositories"]["."]["head"] == candidate, "checkout head differs")
        write(out / "source-snapshot.json", snapshot)
        command(["/usr/bin/python3", "-B", "-O", "scripts/week6_review_materialize.py",
                 "--candidate", candidate, "--policy", str(policy), "--out",
                 str(root / "artifacts/boundary-check/week6-review-source")], root)
    elif name == "install-rust":
        import fixed_install_bundle as bundle
        import restore_fixed_inputs as restore
        host_preflight(out)
        inputs = out / "fixed-inputs"; inputs.mkdir(exist_ok=False)
        archive, manifest = inputs / "extra-installations.tar.xz", inputs / "manifest.json"
        download("WEEK6_INSTALL_ARCHIVE_URL", archive, state["install_archive_sha256"])
        download("WEEK6_INSTALL_MANIFEST_URL", manifest, state["install_manifest_sha256"])
        os.environ.pop("WEEK6_INSTALL_ARCHIVE_URL", None)
        os.environ.pop("WEEK6_INSTALL_MANIFEST_URL", None)
        staged = out / "fixed-install-staging"
        checked = bundle.stage(archive, manifest, state["install_manifest_sha256"], staged)
        install_manifest = bundle.load_manifest(manifest, state["install_manifest_sha256"])
        require(install_manifest["canonical_checkout"] == str(root),
                "fixed installation canonical checkout differs")
        entries = install_manifest["entries"]
        roots = restore.install_staged_roots(staged, root, entries)
        require(len(roots) == 5 and checked["archive_sha256"] == state["install_archive_sha256"],
                "fixed installation restoration differs")
        record_tool(root, out, "rust")
    elif name == "install-sail":
        record_tool(root, out, "sail")
        configure_sail_build(root)
    elif name == "install-aeneas-charon":
        import decoder_rebuilt_inputs as rebuilt
        archive = out / "fixed-inputs/rebuilt-decoder-candidate.tar.gz"
        download("WEEK6_DECODER_ARCHIVE_URL", archive, state["decoder_archive_sha256"])
        os.environ.pop("WEEK6_DECODER_ARCHIVE_URL", None)
        destination = root / "artifacts/decoder-inputs/rebuilt-v2"
        receipt = rebuilt.install(archive, destination)
        require(receipt["archive_sha256"] == state["decoder_archive_sha256"] and
                receipt["installation"]["payload"] == str(destination / "payload"),
                "decoder installation identity differs")
        record_tool(root, out, "aeneas"); record_tool(root, out, "charon")
    elif name == "install-lean":
        record_tool(root, out, "lean")
    elif name == "install-rocq":
        record_tool(root, out, "rocq")
    elif name == "rebuild-rust-model":
        command(["/usr/bin/python3", "-B", "-O", "scripts/generate_rebuilt_rust.py"], root)
    elif name == "rebuild-sail-model":
        command(["/usr/bin/make", "sail-config"], root)
        command(["/usr/bin/bash", "scripts/generate_proof_model.sh", "lean"], root)
    elif name == "rust-tests":
        native = product(root, "week6-native-clean-room")
        command(["/usr/bin/python3", "-B", "-O", "scripts/release_rust_tests.py",
                 "--out", str(native / "rust-tests")], root)
    elif name == "runtime-differential":
        native = product(root, "week6-native-clean-room"); native.mkdir(exist_ok=True)
        command(["/usr/bin/python3", "-B", "-O", "scripts/probes/probe_release_runtime.py",
                 "--out", str(native / "runtime")], root)
    elif name == "mutation-matrix":
        code = ("from pathlib import Path; import sys; sys.path.insert(0,'scripts'); "
                "import release_evidence as e; r=e.check_runtime(Path(sys.argv[1])); "
                "e.require(r['cases']==33 and r['mutations']['applied']==194 and r['replays']==33,"
                "'clean-room runtime/mutation counts differ'); print(r)")
        command(["/usr/bin/python3", "-B", "-O", "-c", code,
                 str(product(root, "week6-native-clean-room") / "runtime/report.json")], root)
        produce_negatives(root)
    elif name == "lean-kernel":
        command(["/usr/bin/make", "proof-check", "BACKEND=lean"], root)
    elif name == "rocq-spike":
        command(["/usr/bin/python3", "-B", "-O", "scripts/week6_formal_record.py",
                 "--out", str(product(root, "week6-formal-clean-room"))], root)
        formal = product(root, "week6-formal-clean-room") / "report.json"
        command(["/usr/bin/python3", "-B", "-O", "scripts/week6_formal_review.py",
                 "--formal-report", str(formal), "--formal-report-sha256", sha(formal),
                 "--out", str(product(root, "week6-formal-review-clean-room"))], root)
    elif name == "worktree-audit":
        rows = evidence_rows(root, out, worktree=False)
        current_manifest = out / "current-evidence-manifest.json"
        audit_manifest(root, candidate, rows, current_manifest)
        source_review = root / "artifacts/boundary-check/week6-review-source/source-review.json"
        observation_inputs = {"schema_version": 1, "kind": "week6-current-output-input-v1",
            "candidate": candidate, "formal_report": ref(
                root, product(root, "week6-formal-clean-room") / "report.json"),
            "current_source_review": ref(root, source_review), "current_manifest": ref(root, current_manifest)}
        write(out / "output-observation-inputs.json", observation_inputs)
        command(["/usr/bin/python3", "-B", "-O", "scripts/week6_output_observe.py", "--inputs",
                 str(out / "output-observation-inputs.json"), "--out",
                 str(root / "artifacts/boundary-check/week6-output-observation-clean-room")], root)
        observation = root / "artifacts/boundary-check/week6-output-observation-clean-room/report.json"
        command(["/usr/bin/python3", "-B", "-O", "scripts/week6_output_review.py", "--observation",
                 str(observation), "--policy", str(policy), "--out",
                 str(root / "artifacts/boundary-check/week6-output-review-clean-room")], root)
        reviews = root / "artifacts/boundary-check/week6-output-review-clean-room/report.json"
        command(["/usr/bin/python3", "-B", "-O", "scripts/week6_output_confirm.py", "--observation",
                 str(observation), "--reviews", str(reviews), "--out",
                 str(root / "artifacts/boundary-check/week6-output-confirmation-clean-room")], root)
        materialized = read(reviews)
        preapproval = {"schema_version": 1, "kind": "week6-worktree-preapproval-inputs-v1",
            "candidate": candidate, "source_review": ref(root, source_review),
            "generation": {"producer": ref(
                                root, product(root, "week6-formal-clean-room") / "report.json"),
                           "review": ref(
                                root, product(root, "week6-formal-review-clean-room") / "report.json")},
            "source_increment": None,
            "output_identity": {"observation": ref(root, observation),
                **materialized["reports"], "confirmation": ref(root,
                    root / "artifacts/boundary-check/week6-output-confirmation-clean-room/report.json")}}
        write(out / "preapproval-inputs.json", preapproval)
        command(["/usr/bin/python3", "-B", "-O", "scripts/week6_review_materialize.py",
                 "--candidate", candidate, "--preapproval-inputs", str(out / "preapproval-inputs.json"),
                 "--out", str(root / "artifacts/boundary-check/week6-review-worktree-envelope")], root)
    elif name == "public-claims":
        rows = evidence_rows(root, out)
        pre = out / "pre-public-audit-manifest.json"
        audit_manifest(root, candidate, rows, pre)
        command(["/usr/bin/python3", "-B", "-O", "scripts/audit_release.py", "--manifest", str(pre),
                 "--out", str(out / "pre-public-audit")], root, codes=(2,))
        execution = {"schema_version": 1, "kind": "public-claims-execution-manifest-v1",
            "candidate": candidate,
            "review_manifest": ref(root, root / "docs/release/public-claims-current-v1.json"),
            "evidence": {**rows, "aggregate": ref(root, out / "pre-public-audit/report.json")},
            "boundaries": dict.fromkeys(PUBLIC_BOUNDARIES, False)}
        write(out / "public-claims-execution.json", execution)
        command(["/usr/bin/python3", "-B", "-O", "scripts/release_public_claims.py", "--manifest",
                 "docs/release/public-claims-current-v1.json", "--evidence-manifest",
                 str(out / "public-claims-execution.json"), "--out", str(out / "public-claims")], root)
    else:
        raise RuntimeError("stage action is not internal: " + name)


def new_output(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    require(path == root / "artifacts/boundary-check/week6-clean-room" and
            path.parent.is_dir() and not path.parent.is_symlink() and not path.exists() and not path.is_symlink(),
            "new canonical Week6 clean-room output required")
    path.mkdir()
    return path


def stage_row(out, name, argv, cwd, env, codes=(0,), timeout=21600):
    stdout, stderr = out / (name + ".stdout"), out / (name + ".stderr")
    with stdout.open("xb") as a, stderr.open("xb") as b:
        result = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=a, stderr=b, timeout=timeout)
    row = {"name": name, "argv": argv, "cwd": Path(cwd).relative_to(CANONICAL).as_posix(),
           "exit_code": result.returncode, "stdout": ref(out, stdout), "stderr": ref(out, stderr)}
    require(result.returncode in codes, "clean-room stage failed: " + name)
    return row


def provider():
    kind = os.environ.get("PROVIDER_KIND", "")
    image = os.environ.get("PROVIDER_IMAGE", "")
    match = re.fullmatch(r"(.+)@(sha256:[0-9a-f]{64})", image)
    require(kind in {"github-actions-ephemeral", "independent-ephemeral-vm"} and match,
            "approved ephemeral provider/image digest absent")
    environment_id = os.environ.get("GITHUB_RUN_ID") or os.environ.get("WEEK6_ENVIRONMENT_ID", "")
    require(environment_id, "provider environment id absent")
    return {"kind": kind, "environment_id": environment_id, "image": match.group(1),
            "image_digest": match.group(2), "created_at": stamp(), "ephemeral": True,
            "original_workspace_mounted": False}


def base_environment(environment):
    result = {key: value for key, value in environment.items()
              if key not in SECRET_URLS | INJECTION_ENV and
              not key.startswith(TOOL_ENV_PREFIXES) and not key.startswith("GIT_")}
    result.update(PATH="/usr/bin:/bin", LC_ALL="C", LANG="C", TZ="UTC",
                  GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                  GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_COUNT="2",
                  GIT_CONFIG_KEY_0="core.hooksPath", GIT_CONFIG_VALUE_0="/dev/null",
                  GIT_CONFIG_KEY_1="core.fsmonitor", GIT_CONFIG_VALUE_1="false")
    return result


def stage_environment(environment, name):
    require(name in REQUIRED_STAGES[1:], "unknown stage environment")
    result = base_environment(environment)
    permitted = ({"WEEK6_INSTALL_ARCHIVE_URL", "WEEK6_INSTALL_MANIFEST_URL"}
                 if name == "install-rust" else
                 {"WEEK6_DECODER_ARCHIVE_URL"} if name == "install-aeneas-charon" else set())
    result.update({key: environment[key] for key in permitted if key in environment})
    if name in NATIVE_STAGES:
        rustup = CANONICAL / "artifacts/boundary-check/isolated-rust-lean-ad7o1fsn/rustup"
        prefix = rustup / "toolchains" / RUST_TOOLCHAIN / "bin"
        cargo_homes = {"rust-tests": "rust-tests-cargo-home",
                       "runtime-differential": "runtime-cargo-home",
                       "mutation-matrix": "negative-cargo-home"}
        result.update(PATH=str(prefix) + ":/usr/bin:/bin", RUSTUP_HOME=str(rustup),
                      RUSTUP_TOOLCHAIN=RUST_TOOLCHAIN, RUSTUP_NO_UPDATE_CHECK="1",
                      CARGO_HOME=str(product(CANONICAL, "week6-native-clean-room") /
                                     cargo_homes[name]), CARGO_TERM_COLOR="never")
    return result


def bootstrap_checkout(commit):
    require(OID.fullmatch(commit or "") and CANONICAL.is_dir() and not CANONICAL.is_symlink() and
            not any(CANONICAL.iterdir()),
            "bootstrap checkout target/candidate differs")
    commands = [
        ["/usr/bin/git", "clone", "--no-checkout", "https://github.com/" + REPOSITORY + ".git",
         "."],
        ["/usr/bin/git", "checkout", "--detach", commit],
        ["/usr/bin/git", "submodule", "update", "--init", "--recursive"],
        ["/usr/bin/make", "ckb-baseline-apply"],
        ["/usr/bin/git", "fsck", "--full"],
    ]
    for index, argv in enumerate(commands):
        command(argv, CANONICAL, timeout=1800)


def public_run(args):
    require(args.repository == REPOSITORY and OID.fullmatch(args.commit or "") and
            args.canonical_checkout == CANONICAL and
            args.install_archive_sha256 == INSTALL_ARCHIVE_SHA and
            args.install_manifest_sha256 == INSTALL_MANIFEST_SHA and
            args.decoder_archive_sha256 == DECODER_ARCHIVE_SHA,
            "public clean-room fixed inputs differ")
    require(CANONICAL.resolve() != BOOTSTRAP_ROOT.resolve() and not CANONICAL.exists() and
            not CANONICAL.is_symlink(), "canonical checkout must be fresh and distinct from bootstrap")
    provider_row = provider()
    base_env = base_environment(os.environ)
    CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    require(CANONICAL.parent.is_dir() and not any(path.is_symlink() for path in CANONICAL.parents),
            "canonical checkout parent is linked/invalid")
    temporary = Path(tempfile.mkdtemp(prefix="week6-checkout-", dir=CANONICAL.parent))
    first_out, first_err = temporary / "stdout", temporary / "stderr"
    CANONICAL.mkdir(exist_ok=False)
    checkout_argv = ["/usr/bin/python3", "-B", "-O", str(Path(__file__).resolve()),
                     "_bootstrap-recursive-checkout", "--commit", args.commit]
    with first_out.open("xb") as a, first_err.open("xb") as b:
        result = subprocess.run(checkout_argv, cwd=CANONICAL, stdin=subprocess.DEVNULL,
                                stdout=a, stderr=b, timeout=1800, env=base_env)
    require(result.returncode == 0, "recursive checkout failed")
    out = new_output(CANONICAL, args.out)
    shutil.move(first_out, out / "recursive-checkout.stdout")
    shutil.move(first_err, out / "recursive-checkout.stderr")
    temporary.rmdir()
    state = {"schema_version": 1, "kind": "week6-clean-room-state-v1",
             "repository": args.repository, "candidate": args.commit,
             "canonical_checkout": str(CANONICAL), "install_archive_sha256": args.install_archive_sha256,
             "install_manifest_sha256": args.install_manifest_sha256,
             "decoder_archive_sha256": args.decoder_archive_sha256,
             "review_policy": args.review_policy.as_posix(), "output": str(out)}
    write(out / "state.json", state)
    require(sha(CANONICAL / "scripts/week6_clean_room.py") == sha(Path(__file__)),
            "checked-out clean-room producer differs from bootstrap")
    stages = [{"name": "recursive-checkout", "argv": checkout_argv, "cwd": ".", "exit_code": 0,
               "stdout": ref(out, out / "recursive-checkout.stdout"),
               "stderr": ref(out, out / "recursive-checkout.stderr")}]
    for name in REQUIRED_STAGES[1:]:
        env = stage_environment(os.environ, name)
        argv = ["/usr/bin/python3", "-B", "-O", "scripts/week6_clean_room.py", "_stage",
                "--name", name, "--state", str(out / "state.json")]
        stages.append(stage_row(out, name, argv, CANONICAL, env))
    sys.path.insert(0, str(CANONICAL / "scripts"))
    import source_snapshot
    import release_external_evidence as external
    snapshot = read(out / "source-snapshot.json")
    require(source_snapshot.capture(CANONICAL) == snapshot, "source changed after clean-room stages")
    checkout_status = command(["/usr/bin/git", "status", "--porcelain"], CANONICAL,
                              env=base_env).stdout.decode().strip()
    tools = read(out / "tool-identities.json")
    require(set(tools) == set(TOOL_STAGE), "tool identity inventory differs")
    log_by_stage = {row["name"]: row["stdout"] for row in stages}
    tool_report = {name: {**row, "install_log": log_by_stage[TOOL_STAGE[name]]}
                   for name, row in tools.items()}
    report = {"schema_version": 1, "kind": "clean-room-evidence-v1", "status": "passed",
        "candidate": args.commit, "provider": provider_row,
        "checkout": {"repository": REPOSITORY, "head": args.commit, "recursive_submodules": True,
            "submodules": {name: snapshot["repositories"][name]["head"]
                           for name in ["deps/ckb-vm", "deps/sail-riscv"]},
            "overlay_applied": True, "worktree_status": checkout_status or "clean root with reviewed submodule overlay",
            "log": stages[0]["stdout"]},
        "tools": tool_report, "source_snapshot": ref(out, out / "source-snapshot.json"), "stages": stages,
        "result": {"runtime_cases": 33, "instruction_families": {"ADD": 13, "ADDI": 10, "BEQ": 10},
            "mutations_applied": 194, "rust_tests": 78, "lean_stages": 28, "lean_tests": 287,
            "lean_public_theorems": 68, "rocq_stages": 11, "rocq_verdict": "NO-GO",
            "unexpected_mismatches": 0, "worktree_reviewed": True, "public_claims_reviewed": True},
        "boundaries": {"release_claimed": False, "week6_closed": False,
                       "fresh_execution_claimed": True, "clean_room_verified": True}}
    write(out / "report.json", report)
    external.check_clean_room(out / "report.json", args.commit, root=CANONICAL)
    audit = out / "audit"; audit.mkdir()
    manifest = audit / "manifest.json"
    audit_manifest(CANONICAL, args.commit, evidence_rows(CANONICAL, out, public=True, clean=True), manifest)
    command(["/usr/bin/python3", "-B", "-O", "scripts/audit_release.py", "--manifest", str(manifest),
             "--out", str(audit / "result")], CANONICAL, codes=(2,), env=base_env)
    external.check_clean_room(out / "report.json", args.commit, root=CANONICAL)
    return report


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="mode")
    internal = sub.add_parser("_stage", help=argparse.SUPPRESS)
    internal.add_argument("--name", required=True, choices=REQUIRED_STAGES[1:])
    internal.add_argument("--state", required=True, type=Path)
    bootstrap = sub.add_parser("_bootstrap-recursive-checkout", help=argparse.SUPPRESS)
    bootstrap.add_argument("--commit", required=True)
    result.add_argument("--repository")
    result.add_argument("--commit")
    result.add_argument("--canonical-checkout", type=Path)
    result.add_argument("--install-archive-sha256")
    result.add_argument("--install-manifest-sha256")
    result.add_argument("--decoder-archive-sha256")
    result.add_argument("--review-policy", type=Path)
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
        require(all(getattr(args, name) is not None for name in ["repository", "commit", "canonical_checkout",
                    "install_archive_sha256", "install_manifest_sha256", "decoder_archive_sha256",
                    "review_policy", "out"]), "all public clean-room arguments are required")
        print(json.dumps(public_run(args), indent=2, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print("Week6 clean-room rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
