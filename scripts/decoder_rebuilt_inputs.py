#!/usr/bin/env python3
"""Install/load explicitly admitted v2 inputs, without changing the v1 gate.

The repository policy is the authority, not a package's self-description or an
installation receipt. Historical candidate files remain byte-exact. No fallback
to v1 tools, model rewriting, tool compilation or proof execution is performed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile

import decoder_input_bundle as bundle

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'proof/lean/decoder/rebuilt-input-policy.json'
CATALOGUE = ROOT / 'proof/lean/decoder/rebuilt-input-catalogue.json'
PROFILE = 'rv64-add-rebuilt-inputs-v2'
CATALOGUE_SHA = 'b9015281f8a2c4d30aabd0b91eb6993d492b87e15eb83dcf93a8a66df8daa523'
CONFIGURATION = {'instruction': 'normal 32-bit RV64 ADD', 'version': 2, 'isa': 'IMC+B',
                 'mop': False, 'cache': 'actual fresh decoder', 'theorem': 'OuterAdd.cold_public_add_step'}
LIMITATIONS = [
    'trusted-translators-not-generally-proved-correct', 'upstream-ui-not-all-pass',
    'visitors-20250212-below-declared-20260520-constraint-not-satisfied',
    'historical-diagnostic-classifier-source-identity-not-established',
    'lower-map-body-change-requires-explicit-equivalence-not-path-normalization',
    'physical-memory-reset-full-vm-and-mop-on-not-proved',
    'host-rust-opam-lean-sail-rocq-installations-not-contained',
    'historical-evidence-closure-not-contained',
]
BOUNDARIES = ('main_gate_adopted', 'proof_check_claimed', 'sail_tool_adopted',
              'clean_room_claimed', 'release_claimed')
VARIANTS = {'base/charon': ('charon', None), 'public/charon': ('charon', 'charon.patch'),
            'base/aeneas': ('aeneas', None), 'public/aeneas': ('aeneas', 'aeneas.patch'),
            'join/aeneas': ('aeneas', 'aeneas-join.patch')}
QUALIFICATIONS = {'public_clean', 'borrow', 'fnptr', 'charon_ui', 'charon_diagnostics',
                  'guard_equivalence', 'loop_equivalence'}
require, sha = bundle.require, bundle.sha


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)


def safe_name(name):
    require(isinstance(name, str) and name and '\\' not in name, 'unsafe relative name')
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and
            all(part not in ('', '.', '..', '.git') for part in name.split('/')), 'unsafe relative name')
    return name


def regular(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'linked input path')
    require(path.is_file() and path.stat().st_nlink == 1, 'missing or hardlinked input')
    return path


def load_policy():
    regular(POLICY); regular(CATALOGUE)
    policy, catalogue = read(POLICY), read(CATALOGUE)
    require(type(policy['schema_version']) is int and policy['schema_version'] == 1 and
            policy['kind'] == 'scoped-rebuilt-decoder-input-admission' and
            policy['status'] == 'approved-inputs-main-gate-migration-pending' and
            policy['profile'] == PROFILE, 'unknown rebuilt input admission')
    require(policy['production_baseline'] == 'ckb-vm-1ffba3977da9-runtime-container-v1' and
            canonical(policy['configuration']) == canonical(CONFIGURATION), 'admission scope drift')
    require(policy['limitations'] == LIMITATIONS, 'admission limitations changed')
    require(all(policy[key] is False for key in BOUNDARIES), 'input admission is not gate/release success')
    require(policy['catalogue'] == {'path': str(CATALOGUE.relative_to(ROOT)), 'sha256': CATALOGUE_SHA}
            and sha(CATALOGUE) == CATALOGUE_SHA, 'admission catalogue drift')
    require(set(policy['source_variants']) == set(VARIANTS), 'source variants differ')
    for label, (family, patch) in VARIANTS.items():
        info = policy['source_variants'][label]
        require(info['family'] == family and info['patch'] == patch and
                info['commit'] == catalogue['source_commits'][family], 'source variant scope drift')
    require(set(policy['qualification']) == QUALIFICATIONS, 'qualification set differs')
    for label, info in policy['qualification'].items():
        name = 'qualification/' + label + '.json'
        require(info['file'] == name and info['sha256'] == catalogue['files'][name]['sha256'],
                'qualification identity drift')
    disposition = policy['known_regression_disposition']
    for key in ('historical_classifier_source_identity_matched', 'full_upstream_suite_passed',
                'upstream_visitors_constraint_satisfied', 'goldens_updated'):
        require(disposition[key] is False, 'qualification limitation erased')
    return policy, catalogue


def verify_payload(payload, policy, catalogue):
    payload = Path(payload).absolute()
    manifest_path = regular(payload / 'package.json')
    require(sha(manifest_path) == policy['manifest_sha256'], 'candidate manifest identity drift')
    manifest = read(manifest_path)
    # The package's original candidate disposition is historical data. Admission
    # is a separate policy decision; never edit the manifest to claim approval.
    require(type(manifest['schema_version']) is int and manifest['schema_version'] == 1 and
            manifest['kind'] == 'rebuilt-decoder-candidate-inputs', 'unknown candidate payload')
    require(canonical(manifest['boundaries']) == canonical(catalogue['boundaries']) and
            all(value is False for value in manifest['boundaries'].values()), 'candidate provenance overclaim')
    require(manifest['source_commits'] == catalogue['source_commits'] and
            canonical(manifest['files']) == canonical(catalogue['files']), 'external catalogue differs')
    bundle.check_files(payload, {name: row['sha256'] for name, row in catalogue['files'].items()}, manifest['files'])
    require(manifest_path.stat().st_mode & 0o777 == 0o644, 'manifest mode drift')
    for name in catalogue['files']: regular(payload / safe_name(name))
    for label, expected in policy['qualification'].items():
        report = read(payload / expected['file'])
        require(report['status'] == expected['status'], 'qualification disposition differs: ' + label)
    disposition = policy['known_regression_disposition']
    ui = read(payload / 'qualification/charon_ui.json')
    diagnostic = read(payload / 'qualification/charon_diagnostics.json')
    require(ui['summary'] == disposition['ui_summary'] and diagnostic['counts'] == disposition['diagnostic_counts']
            and diagnostic['historical_replay']['historical_classifier_source_identity_matched'] is False,
            'qualification review drift')
    return manifest


def source_inventory(source):
    source = Path(source).absolute()
    require(source.is_dir() and not any(p.is_symlink() for p in (source, *source.parents)), 'linked source directory')
    gitdir = source / '.git'
    require(gitdir.is_dir() and not gitdir.is_symlink() and not (gitdir / 'commondir').exists(), 'shared Git directory')
    require(not (gitdir / 'objects/info/alternates').exists(), 'Git object alternates')
    for path in (gitdir / 'objects').rglob('*'):
        require(not path.is_symlink() and (path.is_dir() or path.is_file() and path.stat().st_nlink == 1),
                'linked Git object')
    require(not bundle.git(source, 'diff', '--cached', '--') and
            not bundle.git(source, 'ls-files', '--others', '--exclude-standard', '-z'), 'index or untracked source changes')
    files = {}
    for row in bundle.git(source, 'ls-tree', '-rz', 'HEAD').split(b'\0'):
        if not row: continue
        metadata, raw = row.split(b'\t', 1)
        mode, kind, _ = metadata.decode().split(); name = safe_name(raw.decode())
        require(kind == 'blob' and mode in ('100644', '100755', '120000'), 'unexpected source entry')
        path = source / name
        require(not any(p.is_symlink() for p in path.parents if p != source.parent), 'linked source ancestor')
        if mode == '120000':
            require(path.is_symlink(), 'committed source link replaced')
            target = os.readlink(path)
            require(not Path(target).is_absolute() and
                    Path(os.path.normpath(path.parent / target)).is_relative_to(source), 'escaping source link')
            data, actual_mode = target.encode(), '120000'
        else:
            regular(path); data = path.read_bytes()
            actual_mode = '100755' if path.stat().st_mode & 0o111 else '100644'
        files[name] = {'mode': actual_mode, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
    require(files, 'empty tool source')
    return digest(files)


def verify_sources(directory, policy, catalogue):
    result = {}
    for label, (family, patch) in VARIANTS.items():
        source = directory / 'sources' / label; expected = policy['source_variants'][label]
        require(bundle.git(source, 'rev-parse', 'HEAD').decode().strip() == expected['commit'], 'source commit drift')
        inventory = source_inventory(source)
        require(inventory == expected['file_inventory_sha256'], 'tool source inventory drift: ' + label)
        diff = bundle.git(source, 'diff', 'HEAD', '--')
        require(diff == ((directory / 'payload/patches' / patch).read_bytes() if patch else b''), 'source patch drift')
        result[label] = inventory
        if family == 'aeneas':
            ml = source / 'charon'
            require((source / 'src/charon').resolve() == ml and
                    bundle.git(ml, 'rev-parse', 'HEAD').decode().strip() == catalogue['source_commits']['charon'], 'Charon ML source link/commit drift')
            require(source_inventory(ml) == expected['charon_ml_file_inventory_sha256'] and
                    not bundle.git(ml, 'diff', 'HEAD', '--'), 'Charon ML source drift')
    return result


def load(directory):
    directory = Path(directory).absolute()
    policy, catalogue = load_policy()
    before = (sha(POLICY), sha(CATALOGUE))
    manifest = verify_payload(directory / 'payload', policy, catalogue)
    sources = verify_sources(directory, policy, catalogue)
    require((sha(POLICY), sha(CATALOGUE)) == before, 'admission policy changed during load')
    return {'profile': PROFILE, 'directory': str(directory), 'payload': str(directory / 'payload'),
            'policy_sha256': before[0], 'catalogue_sha256': before[1],
            'manifest_sha256': sha(directory / 'payload/package.json'),
            'source_inventories': sources, 'files': len(manifest['files']),
            'bytes': sum(row['bytes'] for row in manifest['files'].values()),
            'scoped_inputs_admitted': True, **{key: False for key in BOUNDARIES}}


def install(archive, destination):
    archive, destination = Path(archive).absolute(), Path(destination).absolute()
    require(not destination.exists() and not destination.is_symlink(), 'installation destination already exists')
    require(not any(p.is_symlink() for p in destination.parents), 'linked installation ancestor')
    policy, catalogue = load_policy(); policy_before = sha(POLICY)
    require(sha(regular(archive)) == policy['archive_sha256'], 'archive identity differs from admission')
    with tarfile.open(archive, 'r:gz') as stream:
        members = stream.getmembers(); bundle.check_members(members)
        require({m.name for m in members} == set(catalogue['files']) | {'package.json'}, 'archive inventory differs')
        # Reserve the whole destination, not just payload: no reuse or overwrite.
        destination.mkdir(parents=True, exist_ok=False)
        payload = destination / 'payload'; payload.mkdir()
        for member in members:
            path = payload / member.name; path.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, path.open('xb') as target:
                shutil.copyfileobj(source, target)
            path.chmod(member.mode)
    verify_payload(payload, policy, catalogue)
    logs = destination / 'install-logs'; logs.mkdir()
    stages = []

    def git_stage(name, cwd, *args):
        print('==> rebuilt input install: ' + name, flush=True)
        output = bundle.git(cwd, *args)
        log = logs / (name + '.log')
        with log.open('xb') as stream: stream.write(output)
        stages.append({'name': name, 'cwd': str(cwd), 'git_args': list(map(str, args)),
                       'exit_code': 0, 'stdout_sha256': sha(log)})

    for label, (family, patch) in VARIANTS.items():
        source = destination / 'sources' / label; source.parent.mkdir(parents=True, exist_ok=True)
        name = label.replace('/', '-')
        git_stage('clone-' + name, destination, 'clone', '--no-hardlinks', '--no-checkout', payload / 'sources' / (family + '.bundle'), source)
        git_stage('checkout-' + name, source, 'checkout', '--detach', catalogue['source_commits'][family])
        git_stage('fsck-' + name, source, 'fsck', '--full', '--strict')
        if patch: git_stage('patch-' + name, source, 'apply', payload / 'patches' / patch)
        if family == 'aeneas':
            ml = source / 'charon'
            git_stage('clone-ml-' + name, destination, 'clone', '--no-hardlinks', '--no-checkout', payload / 'sources/charon.bundle', ml)
            git_stage('checkout-ml-' + name, ml, 'checkout', '--detach', catalogue['source_commits']['charon'])
            git_stage('fsck-ml-' + name, ml, 'fsck', '--full', '--strict')
    result = load(destination)
    require(sha(POLICY) == policy_before and sha(archive) == policy['archive_sha256'], 'installation inputs changed')
    receipt = {'status': 'scoped-inputs-installed-main-gate-migration-pending',
               'finished_at': datetime.now(timezone.utc).isoformat(), 'installation': result,
               'archive_sha256': policy['archive_sha256'], 'stages': stages,
               'installer_sha256': sha(Path(__file__)), 'shared_bundle_helper_sha256': sha(Path(bundle.__file__))}
    # A receipt is a record, never an input to load().
    with (destination / 'install-report.json').open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--install', type=Path, metavar='ARCHIVE')
    action.add_argument('--verify', type=Path, metavar='DIRECTORY')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    require((args.destination is not None) == (args.install is not None), 'destination required only for install')
    result = install(args.install, args.destination) if args.install else load(args.verify)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
