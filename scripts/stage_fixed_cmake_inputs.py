"""Stage the reviewed CMake download package into NEW input/build directories.

No CMake, compiler, network, source patching or canonical deployment is performed.
The FetchContent source overrides are explicit; GMP keeps its original URL/hash
declaration and receives only its exact archive in the expected new cache path.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

import fixed_install_bundle as bundle

require, sha = bundle.require, bundle.sha
MANIFEST_SHA = '792223f4b9773e647805edc4b0b9e1a2064d1a2c498866d14c1a748f405217dd'
ARCHIVE_SHA = '51589032e8adc0aa6db1420633630e5d83cbbb0e094990d0484dd9f6fc8199c9'
FILES = {'CLI11.hpp', 'gmp-6.3.0.tar.xz', 'v1.8.1.tar.gz', 'asio-1.36.0.tar.bz2'}


def new_directory(path):
    path = Path(path).absolute()
    require(path.resolve() == path and not any(p.is_symlink() for p in (path, *path.parents)), 'aliased output')
    require(not path.exists(), 'output already exists')
    return path


def data_matches(data, row):
    require(len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], 'download payload differs')
    declaration = row['declaration']
    algorithm = {'SHA256': 'sha256', 'SHA3_256': 'sha3_256'}.get(declaration['hash_algorithm'])
    require(algorithm is not None and hashlib.new(algorithm, data).hexdigest() == declaration['digest'], 'CMake download hash differs')


def unpack_source(archive_path, destination, top):
    """Only regular files and directories under one exact upstream root."""
    destination = new_directory(destination)
    destination.mkdir(parents=True)
    seen, directories, records = set(), [], {}
    with tarfile.open(archive_path, 'r:*') as archive:
        for member in archive:
            name = member.name.rstrip('/') if member.isdir() else member.name
            bundle.safe_name(name)
            require(name == top or name.startswith(top + '/'), 'unexpected upstream archive root')
            require(name not in seen, 'duplicate source archive entry')
            seen.add(name)
            require((member.isfile() or member.isdir()) and not member.islnk() and not member.issym(), 'source link/special file')
            require(not member.mode & ~0o777, 'special source permissions')
            target = destination / name
            require(not any(p.is_symlink() for p in (target, *target.parents)), 'linked source extraction target')
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                target.mkdir(exist_ok=True)
                directories.append((target, member.mode))
            else:
                with target.open('xb') as stream: shutil.copyfileobj(archive.extractfile(member), stream)
                target.chmod(member.mode)
    require(seen and top in seen and (destination / top).is_dir(), 'upstream root absent')
    for target, mode in sorted(directories, key=lambda row: len(row[0].parts), reverse=True): target.chmod(mode)
    for path in destination.rglob('*'): records[str(path.relative_to(destination))] = bundle.identity(path)
    require(set(records) == seen, 'implicit/extra archive directory not declared')
    return records


def configure_options(out):
    out = Path(out).absolute()
    return ['-DFETCHCONTENT_FULLY_DISCONNECTED:BOOL=ON', '-DFETCHCONTENT_UPDATES_DISCONNECTED:BOOL=ON',
            '-DFETCHCONTENT_SOURCE_DIR_CLI11_HPP:PATH=' + str(out / 'sources/cli11_hpp'),
            '-DFETCHCONTENT_SOURCE_DIR_JSONCONS:PATH=' + str(out / 'sources/jsoncons/jsoncons-1.8.1'),
            '-DFETCHCONTENT_SOURCE_DIR_ASIO:PATH=' + str(out / 'sources/asio/asio-1.36.0'),
            '-DDOWNLOAD_GMP:BOOL=TRUE']


def stage(archive_path, manifest_path, out):
    out = new_directory(out)
    require(sha(manifest_path) == MANIFEST_SHA and sha(archive_path) == ARCHIVE_SHA, 'unreviewed CMake input package')
    manifest = json.loads(Path(manifest_path).read_bytes())
    require(manifest['schema_version'] == 1 and manifest['kind'] == 'fixed-cmake-download-inputs-v1' and
            set(manifest['files']) == FILES, 'CMake input package scope differs')
    for key in ['cold_configure_tested', 'complete_build_input_closure', 'network_downloads_performed', 'release_claimed']:
        require(manifest[key] is False, 'CMake input package overclaim')
    # Validate all outer members before output creation.
    contents = {}
    with tarfile.open(archive_path, 'r:gz') as archive:
        for member in archive:
            require(member.name in FILES and member.name not in contents and member.isfile() and
                    not member.islnk() and not member.issym() and not member.pax_headers, 'invalid download package member')
            row = manifest['files'][member.name]
            require(member.mode == row['mode'] == 0o644 and member.size == row['bytes'], 'download member metadata')
            data = archive.extractfile(member).read()
            data_matches(data, row)
            contents[member.name] = data
    require(set(contents) == FILES, 'download omitted')
    out.mkdir(parents=True)
    report = {'schema_version': 1, 'status': 'running', 'manifest_sha256': MANIFEST_SHA,
              'archive_sha256': ARCHIVE_SHA, 'source_snapshot_sha256': manifest['source_snapshot_sha256'],
              'helper_sha256': sha(Path(__file__)), 'archive_helper_sha256': sha(Path(bundle.__file__)),
              'clean_room_closed': False, 'week6_closed': False, 'release_claimed': False,
              'cold_configure_tested': False, 'compiler_executed': False, 'network_downloads_performed': False,
              'canonical_deployment_tested': False, 'os_sandboxed': False}
    def save(): (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    save()
    try:
        downloads = out / 'downloads'
        downloads.mkdir()
        for name, data in contents.items():
            path = downloads / name
            with path.open('xb') as stream: stream.write(data)
            path.chmod(0o644)
        sources = out / 'sources'
        sources.mkdir()
        report['source_archives'] = {}
        for key, filename, top in [('jsoncons', 'v1.8.1.tar.gz', 'jsoncons-1.8.1'),
                                    ('asio', 'asio-1.36.0.tar.bz2', 'asio-1.36.0')]:
            report['source_archives'][key] = unpack_source(downloads / filename, sources / key, top)
        cli = sources / 'cli11_hpp'
        cli.mkdir()
        shutil.copyfile(downloads / 'CLI11.hpp', cli / 'CLI11.hpp')
        (cli / 'CLI11.hpp').chmod(0o644)
        gmp = out / 'build/gmp-prefix/src/gmp-6.3.0.tar.xz'
        gmp.parent.mkdir(parents=True)
        shutil.copyfile(downloads / gmp.name, gmp)
        gmp.chmod(0o644)
        require(not (out / 'build/CMakeCache.txt').exists(), 'build is not fresh')
        for name, row in manifest['files'].items(): data_matches((downloads / name).read_bytes(), row)
        data_matches((cli / 'CLI11.hpp').read_bytes(), manifest['files']['CLI11.hpp'])
        data_matches(gmp.read_bytes(), manifest['files'][gmp.name])
        require(sha(archive_path) == ARCHIVE_SHA and sha(manifest_path) == MANIFEST_SHA and
                sha(Path(__file__)) == report['helper_sha256'] and sha(Path(bundle.__file__)) == report['archive_helper_sha256'], 'staging input/code drift')
        report.update(status='fixed_cmake_inputs_staged_configuration_pending', out=str(out), build=str(out / 'build'),
                      configure_options=configure_options(out), gmp_archive=str(gmp),
                      cli_header_sha256=sha(cli / 'CLI11.hpp'))
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
    save()
    require(report['status'] == 'fixed_cmake_inputs_staged_configuration_pending', report.get('error', 'staging failed'))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = stage(args.archive, args.manifest, args.out)
        print(json.dumps({'status': result['status'], 'report': str(Path(result['out']) / 'report.json')}))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
