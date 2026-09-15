"""Hash-pinned archive of extra fixed-prefix installations; never deploys over a checkout.

Staging restores bytes in a NEW directory, not an operational relocated toolchain.
The caller must obtain the manifest digest through a separately trusted channel.
"""
import argparse
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import stat
import subprocess
import tarfile


# The manifest binds member identity, not the container.  gzip is kept so the
# historically pinned package still verifies; xz is the format for new packages
# because the same bytes fit under GitHub's 2 GiB release-asset limit.
COMPRESSION_MAGIC = {'gz': b'\x1f\x8b', 'xz': b'\xfd7zXZ\x00'}
XZ = '/usr/bin/xz'


def require(value, message):
    if not value: raise RuntimeError(message)


def digest_stream(stream):
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024): digest.update(chunk)
    return digest.hexdigest()


def sha(path):
    with Path(path).open('rb') as stream: return digest_stream(stream)


def safe_name(name):
    require(type(name) is str and name and '\\' not in name and '\0' not in name and
            PurePosixPath(name).as_posix() == name and not name.startswith('/') and
            all(part not in ('', '.', '..') for part in name.split('/')), 'unsafe archive name')
    return name


def identity(path):
    path = Path(path)
    require(all(not parent.is_symlink() for parent in path.parents), 'linked source ancestor')
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return {'kind': 'symlink', 'target': os.readlink(path)}
    if stat.S_ISDIR(info.st_mode):
        require(not (info.st_mode & 0o7000), 'special directory permission bits')
        return {'kind': 'directory', 'mode': info.st_mode & 0o777}
    require(stat.S_ISREG(info.st_mode) and not (info.st_mode & 0o7000), 'special source or permission bits')
    return {'kind': 'file', 'sha256': sha(path), 'bytes': info.st_size, 'mode': info.st_mode & 0o777}


def entries_valid(entries):
    require(type(entries) is dict and entries, 'empty entry inventory')
    for name, row in entries.items():
        safe_name(name)
        require(type(row) is dict, 'invalid entry record')
        for parent in PurePosixPath(name).parents:
            require(str(parent) not in entries or entries[str(parent)].get('kind') == 'directory',
                    'entry overlaps a file/link parent')
        if row.get('kind') == 'file':
            require(set(row) == {'kind', 'sha256', 'bytes', 'mode'} and
                    type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']) and
                    type(row['bytes']) is int and row['bytes'] >= 0 and type(row['mode']) is int and
                    0 <= row['mode'] <= 0o777, 'invalid regular entry')
        elif row.get('kind') == 'directory':
            require(set(row) == {'kind', 'mode'} and type(row['mode']) is int and 0 <= row['mode'] <= 0o777,
                    'invalid directory entry')
        else:
            require(row.get('kind') == 'symlink' and set(row) == {'kind', 'target'} and
                    type(row['target']) is str and row['target'] and '\\' not in row['target'] and
                    '\0' not in row['target'] and not row['target'].startswith('/'), 'invalid symbolic link')
    for name, row in entries.items():
        if row['kind'] != 'symlink': continue
        current, visited = name, set()
        while entries.get(current, {}).get('kind') == 'symlink':
            require(current not in visited, 'symbolic link cycle')
            visited.add(current)
            current = safe_name(posixpath.normpath(posixpath.join(posixpath.dirname(current),
                                                                entries[current]['target'])))
        require(entries.get(current, {}).get('kind') == 'file', 'link chain does not end at a recorded regular file')


def load_manifest(path, expected_sha):
    require(type(expected_sha) is str and re.fullmatch('[0-9a-f]{64}', expected_sha), 'trusted manifest digest absent')
    require(sha(path) == expected_sha, 'manifest digest differs')
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    manifest = json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)
    require(type(manifest.get('schema_version')) is int and manifest['schema_version'] == 1 and
            manifest.get('kind') == 'extra-fixed-prefix-installations-v1', 'unknown installation package')
    require(set(manifest) == {'schema_version', 'kind', 'canonical_checkout', 'inputs', 'required_external',
                              'boundaries', 'entries'}, 'manifest fields differ')
    require(type(manifest['canonical_checkout']) is str and Path(manifest['canonical_checkout']).is_absolute(),
            'canonical checkout absent')
    require(type(manifest['inputs']) is dict and manifest['inputs'] and
            type(manifest['required_external']) is list and manifest['required_external'] and
            all(type(item) is str and item for item in manifest['required_external']), 'package provenance absent')
    require(manifest['boundaries'] == {key: False for key in
            ['clean_room', 'release', 'kernel_execution', 'relocatable', 'host_closure_complete']},
            'package assurance differs')
    require(all(type(v) is bool for v in manifest['boundaries'].values()), 'nonboolean package assurance')
    entries_valid(manifest['entries'])
    return manifest


def compression_of(path):
    """Detect the container from magic bytes; the name is never trusted."""
    with Path(path).open('rb') as stream: head = stream.read(6)
    for name, magic in COMPRESSION_MAGIC.items():
        if head.startswith(magic): return name
    raise RuntimeError('unsupported archive compression')


def open_archive(path):
    return tarfile.open(path, 'r|' + compression_of(path))


def write_archive(path, sources, entries, compression='xz'):
    entries_valid(entries)
    require(compression in COMPRESSION_MAGIC, 'unsupported archive compression')
    require(set(sources) == set(entries), 'archive source inventory differs')
    require(not Path(path).exists() and not Path(path).is_symlink(), 'archive destination exists')
    options = {'compresslevel': 1} if compression == 'gz' else {'preset': 9}
    with tarfile.open(path, 'x:' + compression, format=tarfile.PAX_FORMAT, **options) as archive:
        for name, row in sorted(entries.items()):
            require(identity(sources[name]) == row, 'source changed before archive: ' + name)
            member = tarfile.TarInfo(name)
            member.uid = member.gid = member.mtime = 0
            if row['kind'] == 'file':
                member.size, member.mode = row['bytes'], row['mode']
                with Path(sources[name]).open('rb') as stream: archive.addfile(member, stream)
            elif row['kind'] == 'directory':
                member.type, member.mode = tarfile.DIRTYPE, row['mode']
                archive.addfile(member)
            else:
                member.type, member.linkname, member.mode = tarfile.SYMTYPE, row['target'], 0o777
                archive.addfile(member)


def validate_member(member, entries, seen):
    name = safe_name(member.name)
    require(name in entries and name not in seen, 'extra or repeated archive entry')
    seen.add(name)
    row = entries[name]
    require(member.uid == member.gid == 0 and not member.uname and not member.gname and
            member.mtime == 0, 'unreviewed ownership/timestamp metadata')
    if row['kind'] == 'file':
        require(member.isreg() and member.size == row['bytes'] and member.mode == row['mode'] and
                not member.linkname and not member.sparse, 'regular archive metadata differs')
    elif row['kind'] == 'directory':
        require(member.isdir() and member.size == 0 and member.mode == row['mode'] and not member.linkname,
                'directory archive metadata differs')
    else:
        require(member.issym() and member.linkname == row['target'] and member.size == 0 and member.mode == 0o777,
                'symbolic archive metadata differs')
    return name, row


def verify_archive(archive_path, manifest_path, manifest_sha):
    manifest = load_manifest(manifest_path, manifest_sha)
    entries, seen = manifest['entries'], set()
    before = sha(archive_path)
    with open_archive(archive_path) as archive:
        for member in archive:
            name, row = validate_member(member, entries, seen)
            if row['kind'] == 'file':
                stream = archive.extractfile(member)
                require(stream is not None and digest_stream(stream) == row['sha256'], 'archived bytes differ: ' + name)
    require(seen == set(entries), 'missing archive entries')
    require(sha(archive_path) == before and sha(manifest_path) == manifest_sha, 'archive/manifest changed during verification')
    return {'archive_sha256': before, 'manifest_sha256': manifest_sha, 'entries': len(entries),
            'compression': compression_of(archive_path),
            'regular_bytes': sum(row.get('bytes', 0) for row in entries.values()),
            'clean_room_claimed': False, 'operational_installation_claimed': False}


def decompressed_digest(archive_path):
    """SHA-256 of the uncompressed tar stream, independent of the container."""
    opener = gzip.open if compression_of(archive_path) == 'gz' else lzma.open
    with opener(archive_path, 'rb') as stream: return digest_stream(stream)


def recompress_xz(source_path, manifest_path, manifest_sha, destination, threads=1, xz=XZ):
    """Re-container a verified gzip package as xz without touching its member identity.

    The manifest and every archived member stay byte-identical, so the manifest
    digest is unchanged and only the outer archive digest is new.  Compression
    runs through the system xz so multi-threading is available; the result is
    then fully re-verified member by member and its uncompressed tar stream must
    equal the source's.  Nothing is deployed and no clean-room claim is made.
    """
    source_path, destination = Path(source_path), Path(destination)
    require(type(threads) is int and threads > 0, 'invalid xz thread count')
    require(Path(xz).is_file() and os.access(xz, os.X_OK), 'xz executable missing')
    require(compression_of(source_path) == 'gz', 'recompression source is not a gzip package')
    require(not destination.exists() and not destination.is_symlink(), 'recompression destination exists')
    source = verify_archive(source_path, manifest_path, manifest_sha)
    version = subprocess.run([xz, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    require(version.returncode == 0, 'xz version probe failed')
    argv = [xz, '-9', '-T', str(threads), '--check=sha256', '-z', '-c']
    tar_digest = hashlib.sha256()
    with destination.open('xb') as output, gzip.open(source_path, 'rb') as stream:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.PIPE)
        try:
            while chunk := stream.read(1024 * 1024):
                tar_digest.update(chunk)
                process.stdin.write(chunk)
        finally:
            process.stdin.close()
            stderr = process.stderr.read()
            process.stderr.close()
            code = process.wait()
    require(code == 0, 'xz failed: ' + stderr.decode(errors='replace').strip())
    result = verify_archive(destination, manifest_path, manifest_sha)
    require(result['compression'] == 'xz', 'recompressed package is not xz')
    require(decompressed_digest(destination) == tar_digest.hexdigest() == decompressed_digest(source_path),
            'uncompressed tar stream differs after recompression')
    require(sha(source_path) == source['archive_sha256'], 'source package changed during recompression')
    return {'source_archive_sha256': source['archive_sha256'], 'archive_sha256': result['archive_sha256'],
            'manifest_sha256': manifest_sha, 'tar_stream_sha256': tar_digest.hexdigest(),
            'entries': result['entries'], 'regular_bytes': result['regular_bytes'],
            'source_bytes': source_path.stat().st_size, 'archive_bytes': destination.stat().st_size,
            'xz_version': version.stdout.decode(errors='replace').strip().splitlines()[0], 'xz_argv': argv,
            'compression': 'xz', 'clean_room_claimed': False, 'operational_installation_claimed': False}


def stage(archive_path, manifest_path, manifest_sha, destination):
    destination = Path(destination).absolute()
    require(not destination.exists() and not destination.is_symlink(), 'staging destination exists')
    require(not any(p.is_symlink() for p in destination.parents), 'linked staging ancestor')
    checked = verify_archive(archive_path, manifest_path, manifest_sha)
    manifest = load_manifest(manifest_path, manifest_sha)
    entries, seen, links, directories = manifest['entries'], set(), [], []
    destination.mkdir(parents=True, exist_ok=False)
    # Never tar.extract: only create validated regular members with exclusive opens.
    with open_archive(archive_path) as archive:
        for member in archive:
            name, row = validate_member(member, entries, seen)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            require(not any(p.is_symlink() for p in (target, *target.parents)), 'linked staging member')
            if row['kind'] == 'symlink':
                links.append((target, row['target']))
                continue
            if row['kind'] == 'directory':
                target.mkdir(exist_ok=True)
                directories.append((target, row['mode']))
                continue
            with target.open('xb') as stream: shutil.copyfileobj(archive.extractfile(member), stream, 1024 * 1024)
            target.chmod(row['mode'])
    require(seen == set(entries), 'missing staged entries')
    for target, link in links: target.symlink_to(link)
    for target, mode in sorted(directories, key=lambda row: len(row[0].parts), reverse=True): target.chmod(mode)
    verify_staged(destination, entries)
    require(sha(archive_path) == checked['archive_sha256'] and sha(manifest_path) == manifest_sha,
            'archive/manifest changed during staging')
    return {**checked, 'staged_at': str(destination)}


def verify_staged(destination, entries):
    destination = Path(destination)
    entries_valid(entries)
    observed = {}
    implied = {str(parent) for name in entries for parent in PurePosixPath(name).parents if str(parent) != '.'}
    for path in destination.rglob('*'):
        name = str(path.relative_to(destination))
        if path.is_dir() and not path.is_symlink() and name not in entries:
            require(name in implied, 'unexpected staged directory')
            continue
        observed[name] = identity(path)
        if path.is_file() and not path.is_symlink(): require(path.stat().st_nlink == 1, 'hardlinked staged file')
    require(observed == entries, 'staged inventory differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--stage', type=Path, help='NEW directory; byte staging, not tool deployment')
    parser.add_argument('--recompress-xz', type=Path, help='NEW .tar.xz path; re-container a verified gzip package')
    parser.add_argument('--xz-threads', type=int, default=1)
    args = parser.parse_args()
    require(not (args.stage and args.recompress_xz), 'choose one of --stage and --recompress-xz')
    if args.recompress_xz:
        result = recompress_xz(args.archive, args.manifest, args.manifest_sha256, args.recompress_xz, args.xz_threads)
    elif args.stage:
        result = stage(args.archive, args.manifest, args.manifest_sha256, args.stage)
    else:
        result = verify_archive(args.archive, args.manifest, args.manifest_sha256)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
