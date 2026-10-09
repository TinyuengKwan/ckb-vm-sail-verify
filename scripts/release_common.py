"""Small shared helpers for the acceptance scripts: hashing, safe paths, JSON,
deterministic tar archives, command recording and signature/remote queries.

Nothing here decides acceptance; the validators in audit_release.py do.
"""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
POLICY = "docs/release/policy.json"
SHA256 = re.compile(r"[0-9a-f]{64}")
GIT_OID = re.compile(r"[0-9a-f]{40}")
MAX_ASSET_BYTES = 2 * 1024 ** 3  # GitHub release-asset limit (exclusive).


def require(value, message):
    if not value:
        raise RuntimeError(message)


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid(value):
        raise RuntimeError("non-finite JSON value: " + value)
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs, parse_constant=invalid)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write(path, value):
    with Path(path).open("xb") as stream:
        stream.write(json_bytes(value))


def load_policy(root=ROOT):
    value = read(Path(root) / POLICY)
    require(value.get("schema_version") == 2 and value.get("kind") == "release-policy-v2", "unknown release policy")
    return value


def fields(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), label + " fields")


def text(value, label):
    require(type(value) is str and value.strip(), label)
    return value


def integer(value, label):
    require(type(value) is int and value > 0, label)
    return value


def digest(value, label):
    require(type(value) is str and SHA256.fullmatch(value), label)
    return value


def safe_name(name):
    require(type(name) is str and name and not any(c in name for c in "\\\0\r\n"), "unsafe path: " + repr(name))
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and
            all(part not in ("", ".", "..") for part in path.parts), "unsafe path: " + name)
    return name


def regular(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file(),
            "missing/linked file: " + str(path))
    mode = path.stat().st_mode
    require(stat.S_ISREG(mode) and not mode & 0o7000, "special file: " + str(path))
    return path


def member(root, name):
    """A file named relative to root, without traversal or symlinks."""
    safe_name(name)
    root = Path(root).resolve()
    path = root
    for part in name.split("/"):
        path = path / part
        require(not path.is_symlink(), "symlinked evidence path: " + name)
    require(path.is_file() and path.resolve().is_relative_to(root), "missing evidence file: " + name)
    return path


def linked(root, name, expected):
    digest(expected, "evidence hash: " + str(name))
    path = member(root, name)
    require(sha(path) == expected, "evidence hash differs: " + name)
    return path


def reference(root, row, label):
    fields(row, {"path", "sha256"}, label + " reference")
    return linked(root, text(row["path"], label + " path"), row["sha256"])


def ref(root, path):
    root, path = Path(root).resolve(), Path(path).absolute()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            "reference outside/missing: " + str(path))
    return {"path": path.relative_to(root).as_posix(), "sha256": sha(path)}


def size_ok(size):
    require(type(size) is int and 0 < size < MAX_ASSET_BYTES, "release asset must be under 2 GiB")


def run_command(out, label, argv, cwd, env=None, timeout=1800):
    """Run a command with recorded argv/exit code and hash-bound stdout/stderr files."""
    out = Path(out)
    stdout, stderr = out / (label + ".stdout"), out / (label + ".stderr")
    with stdout.open("xb") as a, stderr.open("xb") as b:
        result = subprocess.run([str(item) for item in argv], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=a, stderr=b, timeout=timeout)
    return {"name": label, "argv": [str(item) for item in argv], "cwd": str(cwd), "exit_code": result.returncode,
            "stdout": ref(out, stdout), "stderr": ref(out, stderr)}


def check_stages(directory, rows, expected_names):
    require(type(rows) is list and [row.get("name") for row in rows] == list(expected_names), "stage inventory")
    for row in rows:
        fields(row, {"name", "argv", "cwd", "exit_code", "stdout", "stderr"}, "stage " + str(row.get("name")))
        require(type(row["argv"]) is list and row["argv"] and all(type(a) is str and a for a in row["argv"]),
                "stage argv: " + row["name"])
        require(same(row["exit_code"], 0), "stage failed: " + row["name"])
        reference(directory, row["stdout"], row["name"] + " stdout")
        reference(directory, row["stderr"], row["name"] + " stderr")


# ---- archives -----------------------------------------------------------

def tar_info(name, size=0, mode=0o644, directory=False):
    info = tarfile.TarInfo(name.rstrip("/") + "/" if directory else safe_name(name))
    info.uid = info.gid = info.mtime = 0
    info.uname = info.gname = ""
    info.mode = mode & 0o777
    info.size = size
    if directory:
        info.type = tarfile.DIRTYPE
    return info


class _Reader:
    def __init__(self, data):
        self.data, self.offset = data, 0

    def read(self, size=-1):
        if size < 0:
            size = len(self.data) - self.offset
        result = self.data[self.offset:self.offset + size]
        self.offset += len(result)
        return result


def write_tar_gz(path, files, extra=None, directories=()):
    """Deterministic gzip tar: sorted members, zero timestamps/ownership, no links."""
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), "archive output occupied: " + str(path))
    with path.open("xb") as raw, gzip.GzipFile(filename="", mode="wb", compresslevel=1, mtime=0, fileobj=raw) as gz, \
            tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in directories:
            tar.addfile(tar_info(name, directory=True, mode=0o755))
        for name, source in sorted(files.items()):
            source = regular(source)
            before = sha(source)
            with source.open("rb") as stream:
                tar.addfile(tar_info(name, source.stat().st_size, source.stat().st_mode), stream)
            require(sha(source) == before, "input changed during archive: " + name)
        for name, data in sorted((extra or {}).items()):
            tar.addfile(tar_info(name, len(data)), _Reader(data))
    return sha(path)


def tar_inventory(path):
    """Size and digest of every regular member of a gzip tar; links/devices/duplicates fail."""
    files, directories, seen = {}, set(), set()
    with tarfile.open(path, "r:gz") as archive:
        for item in archive:
            name = safe_name(item.name.rstrip("/") if item.isdir() else item.name)
            require(not item.mode & ~0o777 and name not in seen, "special/duplicate archive member: " + name)
            seen.add(name)
            if item.isdir():
                directories.add(name + "/")
                continue
            require(item.isfile() and not item.linkname, "special/link archive member: " + name)
            stream = archive.extractfile(item)
            require(stream is not None, "unreadable archive member")
            size, hasher = 0, hashlib.sha256()
            while block := stream.read(1024 * 1024):
                size += len(block)
                hasher.update(block)
            require(size == item.size, "archive member size differs")
            files[name] = {"size": size, "sha256": hasher.hexdigest()}
    require(files, "empty archive")
    return files, directories


def manifest_members(rows, label):
    require(type(rows) is list and rows, "empty " + label + " members")
    result = {}
    for row in rows:
        fields(row, {"path", "size", "sha256"}, label + " member")
        name = safe_name(row["path"])
        require(name not in result and type(row["size"]) is int and row["size"] >= 0, "duplicate/invalid " + label + " member")
        result[name] = {"size": row["size"], "sha256": digest(row["sha256"], label + " member hash")}
    return result


def archive_member_bytes(archive, name, limit=16 * 1024 ** 2):
    with tarfile.open(archive, "r:gz") as tar:
        matches = [m for m in tar if m.name == name]
        require(len(matches) == 1 and matches[0].isfile() and 0 < matches[0].size <= limit,
                "archive member missing/ambiguous/oversized: " + name)
        return tar.extractfile(matches[0]).read()


def extract_verified(archive, destination, members, directories=()):
    """Extract exactly a known inventory into a new directory, rehashing every file."""
    destination = Path(destination).absolute()
    require(not destination.exists() and not any(p.is_symlink() for p in (destination, *destination.parents)),
            "new extraction destination required")
    for name, row in members.items():
        safe_name(name)
        fields(row, {"size", "sha256"}, "extraction member")
    allowed = {str(p) for n in members for p in PurePosixPath(n).parents if str(p) != "."} | set(directories)
    destination.mkdir(parents=True)
    seen, files = set(), set()
    with tarfile.open(archive, "r:gz") as tar:
        for item in tar:
            name = safe_name(item.name.rstrip("/") if item.isdir() else item.name)
            require(name not in seen and not item.mode & ~0o777, "duplicate/special extraction entry: " + name)
            seen.add(name)
            target = destination / name
            require(not any(p.is_symlink() for p in (target, *target.parents)), "linked extraction ancestor")
            if item.isdir():
                require(name in allowed and name not in members, "unexpected extraction directory: " + name)
                target.mkdir(parents=True, exist_ok=True)
                continue
            require(item.isfile() and name in members and item.size == members[name]["size"],
                    "unexpected extraction member: " + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            hasher = hashlib.sha256()
            with tar.extractfile(item) as incoming, target.open("xb") as outgoing:
                while block := incoming.read(1024 * 1024):
                    hasher.update(block)
                    outgoing.write(block)
            require(hasher.hexdigest() == members[name]["sha256"], "extracted bytes differ: " + name)
            target.chmod(item.mode)
            files.add(name)
    require(files == set(members), "missing extraction members")


# ---- signatures and remote queries ----------------------------------------

def approved_identity(allowed, identity):
    allowed = regular(allowed)
    rows = [line for line in allowed.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
    require(any(line.split(maxsplit=1)[0] == identity for line in rows), "identity is not an approved signer: " + identity)
    return allowed


def verify_ssh_signature(allowed, identity, namespace, signature, payload, label):
    allowed = approved_identity(allowed, identity)
    with Path(payload).open("rb") as stream:
        result = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I", identity, "-n", namespace,
                                 "-s", str(signature)], stdin=stream, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60)
    require(result.returncode == 0, label + " signature verification failed")


def verify_tag(root, version, allowed, identity, candidate):
    """The owner's SSH-signed tag is the delivery approval: verify it against the
    repository's allowed-signers file and require it to point at the candidate."""
    allowed = approved_identity(allowed, identity)
    # Git signs tags in the "git" namespace; restrict the approved identity's keys to it.
    keys = []
    for line in allowed.read_text().splitlines():
        parts = line.split()
        if parts and parts[0] == identity and not line.lstrip().startswith("#"):
            keys.append(identity + ' namespaces="git" ' + " ".join(part for part in parts[1:] if not part.startswith("namespaces=")))
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
    import tempfile
    with tempfile.NamedTemporaryFile("w", prefix="tag-signers-", suffix=".txt", delete=False) as handle:
        handle.write("\n".join(keys) + "\n")
        signers = handle.name
    try:
        verify = subprocess.run(["git", "-c", "gpg.format=ssh", "-c", "gpg.ssh.allowedSignersFile=" + signers,
                                 "verify-tag", version], cwd=root, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60)
    finally:
        os.unlink(signers)
    require(verify.returncode == 0, "tag signature verification failed: " + version)
    status = (verify.stdout + verify.stderr).decode(errors="replace")
    require('Good "git" signature for ' + identity + " " in status, "tag is not signed by the approved identity")
    target = subprocess.run(["git", "rev-parse", "--verify", version + "^{commit}"], cwd=root,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    require(target.returncode == 0 and target.stdout.decode().strip() == candidate, "tag does not point at the candidate")
    tag = subprocess.run(["git", "rev-parse", "--verify", "refs/tags/" + version], cwd=root,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    require(tag.returncode == 0, "tag object absent: " + version)
    return {"tag": version, "tag_object": tag.stdout.decode().strip(), "commit": candidate,
            "signer": identity, "verified": True}


def query_json(argv, label):
    result = subprocess.run([str(a) for a in argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    require(result.returncode == 0, label + " query failed")
    try:
        return json.loads(result.stdout)
    except Exception as error:
        raise RuntimeError(label + " query did not return JSON") from error
