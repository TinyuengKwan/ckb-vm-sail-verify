"""Inventory whole declared output trees and compute exact node deltas.

Includes caches and retained backups within nine mandatory canonical roots.
Run-local outputs need explicit additional roots. Never follows symlinks or
executes generators; two snapshots do not establish that regeneration occurred.
This is a building block, not a worktree/release acceptance validator.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

from release_runtime_evidence import read_json, require, same

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOTS = (
    'build', 'deps/ckb-vm/target', 'deps/sail-riscv/build',
    'proof/lean/generated', 'proof/lean/theorems/.lake',
    'proof/rocq/generated', 'proof/rocq/spike', 'sail-model/build', 'target',
)
KIND = 'declared-generated-output-inventory-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def fields(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), 'invalid ' + label + ' fields')


def safe(name, root_name=False):
    require(type(name) is str and name and not name.startswith('/') and '\x00' not in name and
            all(part not in ('', '.', '..') for part in name.split('/')) and
            (not root_name or '.git' not in name.split('/')), 'unsafe inventory path')
    return name


def roots(extra=()):
    values = [*CANONICAL_ROOTS, *extra]
    require(all(type(name) is str for name in values), 'invalid output root')
    require(len(values) == len(set(values)), 'duplicate output root')
    values = sorted(safe(name, root_name=True) for name in values)
    require(not any(b.startswith(a + '/') for a in values for b in values if a != b),
            'overlapping output roots')
    return values


def state(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def regular(parent_fd, leaf, initial):
    # O_NONBLOCK prevents a raced replacement with a FIFO from hanging the audit.
    # O_NOFOLLOW prevents a raced final symlink from reading a different target.
    fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    with os.fdopen(fd, 'rb') as stream:
        require(state(os.fstat(stream.fileno())) == state(initial), 'file changed before hashing')
        require(stat.S_ISREG(initial.st_mode), 'non-regular output file')
        hasher = hashlib.sha256()
        size = 0
        while data := stream.read(1024 * 1024):
            hasher.update(data)
            size += len(data)
        require(state(os.fstat(stream.fileno())) == state(initial) and
                state(os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)) == state(initial) and
                size == initial.st_size,
                'file changed during hashing')
    return {'kind': 'file', 'mode': stat.S_IMODE(initial.st_mode),
            'size': size, 'sha256': hasher.hexdigest()}


def capture(root=ROOT, extra_roots=()):
    root = Path(root).resolve()
    selected = roots(extra_roots)
    entries = {}

    def visit(parent_fd, leaf, name):
        initial = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        mode = stat.S_IMODE(initial.st_mode)
        if stat.S_ISLNK(initial.st_mode):
            target = os.readlink(leaf, dir_fd=parent_fd)
            require(state(os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)) == state(initial),
                    'symlink changed while reading')
            entries[name] = {'kind': 'symlink', 'mode': mode, 'target': target}
        elif stat.S_ISREG(initial.st_mode):
            entries[name] = regular(parent_fd, leaf, initial)
        elif stat.S_ISDIR(initial.st_mode):
            fd = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            try:
                require(state(os.fstat(fd)) == state(initial), 'directory changed before inventory')
                entries[name] = {'kind': 'directory', 'mode': mode}
                children = sorted(os.listdir(fd))
                for child in children:
                    child_name = safe(name + '/' + child)
                    visit(fd, child, child_name)
                require(state(os.fstat(fd)) == state(initial) and sorted(os.listdir(fd)) == children and
                        state(os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)) == state(initial),
                        'directory changed during inventory')
            finally:
                os.close(fd)
        else:
            raise RuntimeError('special output node is not auditable: ' + name)

    for name in selected:
        # Walk using directory descriptors, never path resolution through an
        # ancestor that could be replaced by a symlink during the scan.
        with ExitStack() as opened:
            def directory(leaf, parent_fd=None):
                fd = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                opened.callback(os.close, fd)
                return fd
            parent_fd = directory(root)
            absent = False
            for part in name.split('/')[:-1]:
                try:
                    parent_fd = directory(part, parent_fd)
                except FileNotFoundError:
                    absent = True
                    break
            if absent:
                entries[name] = None
            else:
                leaf = name.rsplit('/', 1)[-1]
                try:
                    os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
                except FileNotFoundError:
                    entries[name] = None
                else:
                    visit(parent_fd, leaf, name)
    result = {'schema_version': 1, 'kind': KIND, 'roots': selected,
              'entries': entries, 'symlinks_followed': False,
              'whole_workspace_coverage_claimed': False}
    result['snapshot_sha256'] = digest(result)
    validate(result)
    return result


def validate(value):
    fields(value, {'schema_version', 'kind', 'roots', 'entries', 'symlinks_followed',
                   'whole_workspace_coverage_claimed', 'snapshot_sha256'}, 'output inventory')
    require(same(value['schema_version'], 1) and value['kind'] == KIND, 'unknown output inventory schema')
    require(value['symlinks_followed'] is False and value['whole_workspace_coverage_claimed'] is False,
            'output inventory assurance upgrade')
    selected = value['roots']
    require(type(selected) is list and all(type(name) is str for name in selected), 'invalid roots list')
    require(set(CANONICAL_ROOTS) <= set(selected), 'mandatory output roots omitted')
    require(selected == roots([name for name in selected if name not in CANONICAL_ROOTS]),
            'root inventory changed, duplicated or unsorted')
    entries = value['entries']
    require(type(entries) is dict and set(selected) <= set(entries), 'missing root node inventory')
    for name, row in entries.items():
        safe(name)
        owners = [base for base in selected if name == base or name.startswith(base + '/')]
        require(len(owners) == 1, 'node outside declared roots')
        owner = owners[0]
        if name != owner:
            parent = name.rsplit('/', 1)[0]
            require(type(entries.get(parent)) is dict and entries[parent].get('kind') == 'directory',
                    'node has absent/non-directory parent')
        if row is None:
            require(name == owner, 'only an absent root can have a null node')
            continue
        require(type(row) is dict and type(row.get('kind')) is str, 'invalid node record')
        kind = row['kind']
        expected = {'file': {'kind', 'mode', 'size', 'sha256'},
                    'directory': {'kind', 'mode'}, 'symlink': {'kind', 'mode', 'target'}}
        require(kind in expected, 'unsupported node kind')
        fields(row, expected[kind], 'output node')
        require(type(row['mode']) is int and 0 <= row['mode'] <= 0o7777, 'invalid node mode')
        if kind == 'file':
            require(type(row['size']) is int and row['size'] >= 0, 'invalid node size')
            require(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
                    'invalid node SHA-256')
        elif kind == 'symlink':
            require(type(row['target']) is str and row['target'] and '\x00' not in row['target'],
                    'invalid symlink target')
    require(value['snapshot_sha256'] == digest({k: v for k, v in value.items() if k != 'snapshot_sha256'}),
            'output snapshot digest differs')


def compare(before, after):
    validate(before)
    validate(after)
    require(before['roots'] == after['roots'], 'cannot compare different output scopes')
    old, new = before['entries'], after['entries']
    changes = {}
    for name in sorted(old.keys() | new.keys()):
        a, b = old.get(name), new.get(name)
        if same(a, b):
            continue
        operation = 'added' if a is None else 'deleted' if b is None else 'modified'
        changes[name] = {'operation': operation, 'before': a, 'after': b}
    return {'schema_version': 1, 'kind': 'declared-generated-output-delta-v1',
            'before_sha256': before['snapshot_sha256'], 'after_sha256': after['snapshot_sha256'],
            'roots': before['roots'], 'changes': changes, 'regeneration_execution_proven': False,
            'generated_outputs_audited': False, 'worktree_audit_closed': False,
            'release_claimed': False, 'week6_closed': False}


def summary(value):
    return {'nodes': len(value['entries']),
            'files': sum(row is not None and row['kind'] == 'file' for row in value['entries'].values()),
            'bytes': sum(row['size'] for row in value['entries'].values() if row and row['kind'] == 'file'),
            'symlinks': sum(row is not None and row['kind'] == 'symlink' for row in value['entries'].values()),
            'absent_roots': [name for name in value['roots'] if value['entries'][name] is None]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    grab = commands.add_parser('capture')
    grab.add_argument('--root', type=Path, default=ROOT)
    grab.add_argument('--extra-root', action='append', default=[])
    grab.add_argument('--out', type=Path, required=True)
    delta = commands.add_parser('compare')
    delta.add_argument('--before', type=Path, required=True)
    delta.add_argument('--after', type=Path, required=True)
    delta.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        out = args.out.resolve()
        require(not out.exists(), 'output directory already exists')
        if args.command == 'capture':
            root = args.root.resolve()
            for name in roots(args.extra_root):
                require(not out.is_relative_to(root/name), 'inventory output lies inside an inventoried tree')
            value = capture(root, args.extra_root)
            filename = 'snapshot.json'
            details = summary(value)
        else:
            # File hashes and strict JSON loading guard both evidence inputs.
            before_bytes, after_bytes = args.before.read_bytes(), args.after.read_bytes()
            value = compare(read_json(args.before), read_json(args.after))
            require(args.before.read_bytes() == before_bytes and args.after.read_bytes() == after_bytes,
                    'comparison inputs changed')
            filename = 'delta.json'
            details = {'changes': len(value['changes'])}
        out.mkdir(parents=True, exist_ok=False)
        with (out/filename).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        print(json.dumps({'status': 'recorded_not_release_acceptance', 'path': str(out/filename), **details}))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({'status': 'invalid', 'error': str(error), 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
