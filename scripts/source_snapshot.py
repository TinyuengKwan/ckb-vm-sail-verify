"""Byte/mode inventory for HEAD plus an explicit dirty working-tree overlay.

Not a Git commit, semantic approval, release version or supply-chain attestation.
Ignored build/evidence files are excluded; submodule contents are inventoried
separately. Source symlinks and undeclared/nested submodules fail closed.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import ckb_source_baseline as baseline

ROOT = Path(__file__).resolve().parents[1]
REPOS = ['.', 'deps/ckb-vm', 'deps/sail-riscv']


def require(value, message):
    if not value: raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE, timeout=60)


def safe(name):
    require(isinstance(name, str) and name and not Path(name).is_absolute() and
            all(part not in ('', '.', '..', '.git') for part in name.split('/')), 'unsafe source path')
    return name


def regular(repo, name):
    path = Path(repo)
    for part in safe(name).split('/'):
        path = path / part
        require(not path.is_symlink(), 'source symlink: ' + name)
    require(path.is_file(), 'missing/non-regular source: ' + name)
    return path


def entries(repo):
    blobs, links = {}, {}
    for row in git(repo, 'ls-tree', '-rz', 'HEAD').split(b'\0'):
        if not row: continue
        meta, name = row.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        name = safe(name.decode())
        if mode == '160000' and kind == 'commit': links[name] = oid
        else:
            require(kind == 'blob' and mode in ['100644', '100755'], 'unsupported Git source entry')
            blobs[name] = {'mode': mode, 'git_blob': oid}
    return blobs, links


def inventory(repo):
    repo = Path(repo).resolve()
    original, links = entries(repo)
    paths = set(filter(None, git(repo, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')))
    files, changes = {}, {}
    for name in sorted(paths - links.keys()):
        safe(name)
        path = repo / name
        if not path.exists() and not path.is_symlink():
            require(name in original, 'missing added source')
            continue
        path = regular(repo, name)
        data = path.read_bytes()
        mode = '100755' if path.stat().st_mode & 0o111 else '100644'
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        files[name] = {'mode': mode, 'sha256': digest(data), 'size': len(data)}
        if name not in original or original[name] != {'mode': mode, 'git_blob': blob}:
            changes[name] = {'operation': 'added' if name not in original else 'modified',
                             'before': original.get(name), 'after': files[name]}
    for name in sorted(original.keys() - files.keys()):
        changes[name] = {'operation': 'deleted', 'before': original[name], 'after': None}
    return {'head': git(repo, 'rev-parse', 'HEAD').decode().strip(), 'gitlinks': links,
            'files': files, 'changes_from_head': changes}


def capture(root=ROOT):
    root = Path(root).resolve()
    repositories = {name: inventory(root / name) for name in REPOS}
    require(set(repositories['.']['gitlinks']) == set(REPOS[1:]), 'unexpected project submodules')
    for name in REPOS[1:]:
        require(repositories['.']['gitlinks'][name] == repositories[name]['head'] and
                not repositories[name]['gitlinks'], 'submodule revision drift or unhandled nested submodule')
    require(not repositories['deps/sail-riscv']['changes_from_head'], 'unreviewed Sail source changes')
    result = {'schema_version': 1, 'identity_kind': 'HEAD-plus-byte-inventoried-working-tree-not-a-commit',
              'repositories': repositories, 'ckb_source_baseline': baseline.check(root),
              'ignored_build_and_evidence_files_included': False, 'semantic_review_claimed': False}
    return {**result, 'snapshot_sha256': digest(canonical(result))}


def export(root, snapshot, directory):
    """Create immutable-by-hash payload, without touching Git index or original files."""
    root, directory = Path(root).resolve(), Path(directory).resolve()
    require(capture(root) == snapshot, 'source changed before snapshot export')
    directory.mkdir(parents=True, exist_ok=False)
    for repo, info in snapshot['repositories'].items():
        for name, expected in info['files'].items():
            source = regular(root / repo, name)
            target = directory / repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(int(expected['mode'], 8) & 0o777)
            require(digest(target.read_bytes()) == expected['sha256'], 'snapshot copy changed')
    require(capture(root) == snapshot, 'source changed during snapshot export')


def independent(repo):
    directory = Path(git(repo, 'rev-parse', '--absolute-git-dir').decode().strip())
    require(not (directory / 'objects/info/alternates').exists(), 'Git object alternates are not independent')
    require(all(p.stat().st_nlink == 1 for p in (directory / 'objects').rglob('*') if p.is_file()),
            'shared/hardlinked Git objects')


def restore(root, payload, snapshot):
    """Apply payload only to freshly cloned, exact clean HEADs, never an existing dirty tree."""
    root, payload = Path(root).resolve(), Path(payload).resolve()
    for repo, info in snapshot['repositories'].items():
        destination = root / repo
        independent(destination)
        require(git(destination, 'rev-parse', 'HEAD').decode().strip() == info['head'], 'wrong snapshot base')
        # The root's submodule dirtiness is checked after all overlays are applied.
        require(not git(destination, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=all').strip(),
                'overlay destination already dirty')
        original, _ = entries(destination)
        for name in original.keys() - info['files'].keys():
            regular(destination, name).unlink()  # exact known file in the new clone only
        for name, expected in info['files'].items():
            source = regular(payload / repo, name)
            require(digest(source.read_bytes()) == expected['sha256'] and source.stat().st_size == expected['size'],
                    'source payload hash/size differs')
            target = destination / name
            # Parents are from clean Git trees or newly created directories.
            path = destination
            for part in safe(name).split('/'):
                path /= part
                require(not path.is_symlink(), 'overlay target symlink')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(int(expected['mode'], 8) & 0o777)
    require(capture(root) == snapshot, 'restored source tree differs from captured snapshot')
