"""Restore the exact prepared source/tool/decoder inputs into a NEW checkout.

staging: noncanonical file restoration only; never run formal resolvers/proofs.
canonical: explicit fresh canonical-path deployment, still awaiting host/full-chain checks.
No host installation, network clone, policy rewriting or existing checkout overwrite.
"""
import argparse
from contextlib import contextmanager
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import fixed_install_bundle as bundle
import source_snapshot

HANDOFF_SHA = '7a88d4eaa88c83a2317401ac64d9b8dc1c74e6125d40a539645e75f5f103a015'
CANONICAL = Path('/home/clair/tinyueng_workplace/ckb-vm-sail-verify')
MAIN_POLICY = '7ced9f425d1fbda578a796fbc7135a15fec930b66adfbc26a3fc1ba1a177b6f5'
BOUNDARIES = ['clean_room_closed', 'week6_closed', 'release_claimed', 'third_party_reproduced',
              'host_closure_complete', 'arbitrary_path_relocation_adopted', 'current_worktree_is_frozen_capsule']
INSTALL_ROOTS = ['aeneas-opam-finalize-mj9dgb4h', 'aeneas-opam-qhtaephh', 'isolated-rocq-ac54t6f8',
                 'isolated-rust-lean-ad7o1fsn', 'isolated-sail-nrdi23ds']
require, sha = bundle.require, bundle.sha


def read(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def clean_environment():
    return {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0', 'GIT_ALLOW_PROTOCOL': 'file',
            'GIT_CONFIG_COUNT': '2', 'GIT_CONFIG_KEY_0': 'core.hooksPath', 'GIT_CONFIG_VALUE_0': '/dev/null',
            'GIT_CONFIG_KEY_1': 'core.fsmonitor', 'GIT_CONFIG_VALUE_1': 'false'}


@contextmanager
def isolated_process_environment():
    original = dict(os.environ)
    os.environ.clear()
    os.environ.update(clean_environment())
    try: yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def new_path(path):
    path = Path(path).absolute()
    require(path.resolve() == path and not any(p.is_symlink() for p in (path, *path.parents)), 'aliased output path')
    require(not path.exists(), 'output already exists: ' + str(path))
    return path


def destination_for(mode, out):
    require(mode in ('staging', 'canonical'), 'unknown restoration mode')
    out = new_path(out)
    destination = CANONICAL if mode == 'canonical' else out / 'checkout'
    new_path(destination)
    require(not out.is_relative_to(destination), 'report directory overlaps checkout')
    require((destination == CANONICAL) == (mode == 'canonical'), 'canonical/staging scope differs')
    return destination


def load_handoff(path):
    require(sha(path) == HANDOFF_SHA, 'unapproved handoff identity')
    handoff = read(path)
    require(handoff['schema_version'] == 1 and type(handoff['schema_version']) is int and
            handoff['kind'] == 'fixed-input-handoff-preparation-only' and
            handoff['canonical_checkout'] == str(CANONICAL) and handoff['main_policy_sha256'] == MAIN_POLICY,
            'handoff scope differs')
    require(set(handoff['boundaries']) == set(BOUNDARIES) and
            all(value is False for value in handoff['boundaries'].values()), 'handoff assurance changed')
    require(handoff['working_tree_overlay_required'] is True, 'source overlay cannot be omitted')
    return handoff


def reference(input_root, row):
    require(type(row) is dict and set(row) == {'path', 'sha256'}, 'invalid input reference')
    path = Path(input_root).absolute() / bundle.safe_name(row['path'])
    require(path.resolve() == path and not any(p.is_symlink() for p in (path, *path.parents)) and
            path.is_file() and sha(path) == row['sha256'], 'input reference differs: ' + row['path'])
    return path


def all_references(value):
    if type(value) is dict:
        if set(value) == {'path', 'sha256'}: return [value]
        return [row for nested in value.values() for row in all_references(nested)]
    if type(value) is list: return [row for nested in value for row in all_references(nested)]
    return []


def source_transfer(handoff, input_root):
    source = handoff['source']
    descriptor = read(reference(input_root, source['transfer_manifest']))
    require(set(descriptor) == {'schema_version', 'kind', 'source_manifest_sha256', 'source_snapshot_sha256',
                               'entries', 'clean_room_claimed', 'release_claimed'} and
            type(descriptor['schema_version']) is int and descriptor['schema_version'] == 1 and
            descriptor['kind'] == 'fixed-source-capsule-archive-v1' and
            descriptor['source_manifest_sha256'] == source['capsule_manifest_sha256'] and
            descriptor['source_snapshot_sha256'] == handoff['source_snapshot_sha256'] and
            descriptor['clean_room_claimed'] is False and descriptor['release_claimed'] is False,
            'source transfer descriptor differs')
    bundle.entries_valid(descriptor['entries'])
    require(all(row['kind'] in ('file', 'directory') for row in descriptor['entries'].values()),
            'source capsule cannot contain symbolic links')
    return descriptor


def extract_source(archive_path, descriptor, destination, archive_sha):
    """Known source transfer format, not an installation-format relabeling."""
    destination = new_path(destination)
    require(sha(archive_path) == archive_sha, 'source archive drift before extraction')
    entries, seen, directories = descriptor['entries'], set(), []
    bundle.entries_valid(entries)
    require(all(row['kind'] in ('file', 'directory') for row in entries.values()), 'source link refused')
    destination.mkdir(parents=True)
    with bundle.open_archive(archive_path) as archive:
        for member in archive:
            name, row = bundle.validate_member(member, entries, seen)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            require(not any(p.is_symlink() for p in (target, *target.parents)), 'linked source extraction target')
            if row['kind'] == 'directory':
                target.mkdir(exist_ok=True)
                directories.append((target, row['mode']))
            else:
                with target.open('xb') as stream: shutil.copyfileobj(archive.extractfile(member), stream, 1024 * 1024)
                target.chmod(row['mode'])
    require(seen == set(entries), 'missing source archive entries')
    for target, mode in sorted(directories, key=lambda row: len(row[0].parts), reverse=True): target.chmod(mode)
    bundle.verify_staged(destination, entries)
    require(sha(archive_path) == archive_sha, 'source archive drift during extraction')


def installation_roots(entries):
    roots = set()
    for name in entries:
        parts = Path(bundle.safe_name(name)).parts
        require(len(parts) >= 3 and parts[:2] == ('artifacts', 'boundary-check') and
                parts[2] in INSTALL_ROOTS, 'installation entry outside fixed roots')
        roots.add(parts[2])
    require(roots == set(INSTALL_ROOTS), 'incomplete installation root inventory')
    return sorted(roots)


def install_staged_roots(staged, checkout, entries):
    """Move only the five verified, disjoint installation roots into a new checkout."""
    roots = installation_roots(entries)
    parent = checkout / 'artifacts/boundary-check'
    require(not any(p.is_symlink() for p in (parent, *parent.parents)), 'linked installation destination')
    for name in roots:
        target = parent / name
        require(not target.exists() and not target.is_symlink(), 'installation destination occupied: ' + name)
        source = staged / 'artifacts/boundary-check' / name
        require(source.is_dir() and not source.is_symlink(), 'staged installation root missing')
    parent.mkdir(parents=True, exist_ok=True)
    for name in roots: shutil.move(str(staged / 'artifacts/boundary-check' / name), parent / name)
    return roots


def run(handoff_path, input_root, out, mode):
    out = Path(out).absolute()
    # Refuse an existing canonical checkout before hashing/unpacking large inputs.
    destination = destination_for(mode, out)
    handoff = load_handoff(handoff_path)
    references = all_references(handoff)
    require(len(references) == 9, 'handoff evidence reference inventory')
    resolved = {row['path']: reference(input_root, row) for row in references}
    descriptor = source_transfer(handoff, input_root)
    install_ref = handoff['extra_installations']['manifest']
    installations = bundle.load_manifest(resolved[install_ref['path']], install_ref['sha256'])
    installation_roots(installations['entries'])
    require(installations['inputs']['source_snapshot_sha256'] == handoff['source_snapshot_sha256'] and
            installations['canonical_checkout'] == handoff['canonical_checkout'] and
            installations['inputs']['main_policy_sha256'] == handoff['main_policy_sha256'] and
            installations['inputs']['decoder_archive_sha256'] == handoff['decoder_inputs']['archive']['sha256'],
            'installation/source/decoder cross-link differs')
    # All external references and the complete scope are validated before output creation.
    out.mkdir(parents=True)
    report = {'schema_version': 1, 'status': 'running', 'started_at': stamp(), 'mode': mode,
              'destination': str(destination), 'handoff_sha256': HANDOFF_SHA, 'stages': [],
              'clean_room_closed': False, 'week6_closed': False, 'release_claimed': False,
              'host_packages_installed': False, 'proof_chain_executed': False, 'canonical_deployment_tested': False,
              'operational_toolchain_verified': False, 'os_sandboxed': False, 'network_clone_claimed': False}
    def save(): (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def phase(name):
        report['phase'] = name
        save()
        print('Phase: ' + name, flush=True)
    def command(name, argv, cwd, timeout=300):
        start = stamp()
        result = subprocess.run([str(x) for x in argv], cwd=cwd, env=clean_environment(),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        log = out / (name + '.log')
        log.write_bytes(result.stdout)
        report['stages'].append({'name': name, 'argv': [str(x) for x in argv], 'cwd': str(cwd),
            'started_at': start, 'finished_at': stamp(), 'exit_code': result.returncode,
            'log': log.name, 'log_sha256': sha(log)})
        save()
        require(result.returncode == 0, 'restoration command failed: ' + name)
        return result.stdout.decode().strip()
    code = 1
    try:
        report['restorer_sources'] = {str(Path(module.__file__).resolve()): sha(Path(module.__file__))
                                     for module in [sys.modules[__name__], bundle, source_snapshot,
                                                    source_snapshot.baseline]}
        report['references'] = references
        phase('source-archive-and-capsule')
        capsule = out / 'source-capsule'
        extract_source(resolved[handoff['source']['archive']['path']], descriptor, capsule,
                       handoff['source']['archive']['sha256'])
        require(sha(capsule / 'manifest.json') == handoff['source']['capsule_manifest_sha256'] and
                sha(capsule / 'source-snapshot.json') == handoff['source_snapshot_sha256'], 'capsule identity differs')
        capsule_manifest = read(capsule / 'manifest.json')
        state = read(capsule / 'source-snapshot.json')
        require(state['repositories']['.']['head'] == handoff['project_head'] and
                set(state['repositories']) == {'.', 'deps/ckb-vm', 'deps/sail-riscv'}, 'source repository inventory')
        require({name: bundle.identity(capsule / name) for name in capsule_manifest['files']} ==
                capsule_manifest['files'], 'capsule file manifest differs')
        require(sha(Path(source_snapshot.__file__)) == state['repositories']['.']['files']['scripts/source_snapshot.py']['sha256'] and
                sha(Path(source_snapshot.baseline.__file__)) == state['repositories']['.']['files']['scripts/ckb_source_baseline.py']['sha256'],
                'bootstrap source-restoration helpers differ from frozen source')
        phase('offline-recursive-source-restoration')
        repos = {'.': 'project', 'deps/ckb-vm': 'ckb-vm', 'deps/sail-riscv': 'sail-riscv'}
        for repo, label in repos.items():
            ref = capsule_manifest['bundles'][repo]
            require(sha(capsule / ref['path']) == ref['sha256'] and ref['head'] == state['repositories'][repo]['head'],
                    'source bundle reference differs')
            require(command('bundle-heads-' + label, ['git', 'bundle', 'list-heads', capsule / ref['path']], out) ==
                    ref['head'] + ' HEAD', 'source bundle refs differ')
        destination.parent.mkdir(parents=True, exist_ok=True)
        new_path(destination)
        command('clone-project', ['git', 'clone', '--no-hardlinks', '--no-checkout',
                capsule / capsule_manifest['bundles']['.']['path'], destination], out)
        command('checkout-project', ['git', 'checkout', '--detach', handoff['project_head']], destination)
        for repo, label in repos.items():
            if repo != '.': command('configure-' + label, ['git', 'config', 'submodule.' + repo + '.url',
                capsule / capsule_manifest['bundles'][repo]['path']], destination)
        command('recursive-submodules', ['git', 'submodule', 'update', '--init', '--recursive', '--',
                'deps/ckb-vm', 'deps/sail-riscv'], destination)
        for repo, label in repos.items():
            require(command('root-' + label, ['git', 'rev-parse', '--show-toplevel'], destination / repo) ==
                    str(destination / repo), 'wrong restored Git root')
            command('fsck-' + label, ['git', 'fsck', '--full', '--strict'], destination / repo)
        with isolated_process_environment(): source_snapshot.restore(destination, capsule / 'source-payload', state)
        require(sha(destination / 'proof/lean/audit/step-policy.json') == handoff['main_policy_sha256'], 'restored main policy')
        phase('extra-installations')
        install_staged = out / 'extra-staged'
        report['extra_stage'] = bundle.stage(resolved[handoff['extra_installations']['archive']['path']],
                                             resolved[install_ref['path']], install_ref['sha256'], install_staged)
        report['installed_roots'] = install_staged_roots(install_staged, destination, installations['entries'])
        report['extra_stage_retained_after_move'] = False
        report['extra_installation_current_root'] = str(destination)
        # Only the five exact moved roots are inspected; do not scan unrelated checkout data.
        for name, expected in installations['entries'].items():
            require(bundle.identity(destination / name) == expected, 'installed member differs: ' + name)
        phase('admitted-decoder-installation')
        admission = handoff['decoder_inputs']
        require(sha(destination / 'proof/lean/decoder/rebuilt-input-policy.json') == admission['admission_policy_sha256'] and
                sha(destination / 'proof/lean/decoder/rebuilt-input-catalogue.json') == admission['catalogue_sha256'],
                'restored decoder admission differs')
        command('decoder-install', [sys.executable, '-O', destination / 'scripts/decoder_rebuilt_inputs.py',
                '--install', resolved[admission['archive']['path']], '--destination',
                destination / 'artifacts/decoder-inputs/rebuilt-v2'], destination, timeout=1800)
        command('decoder-independent-load', [sys.executable, '-O', destination / 'scripts/decoder_rebuilt_inputs.py',
                '--verify', destination / 'artifacts/decoder-inputs/rebuilt-v2'], destination, timeout=1800)
        phase('final-source-and-input-checks')
        with isolated_process_environment():
            require(source_snapshot.capture(destination) == state, 'restored source changed during installations')
            for repo in repos: source_snapshot.independent(destination / repo)
        for row in references: reference(input_root, row)
        require(sha(handoff_path) == HANDOFF_SHA and all(sha(Path(name)) == digest for name, digest in report['restorer_sources'].items()),
                'restorer/handoff source drift')
        report['source_snapshot_sha256'] = handoff['source_snapshot_sha256']
        report['canonical_deployment_tested'] = mode == 'canonical'
        report['status'] = ('fixed_inputs_restored_at_canonical_path_full_verification_pending' if mode == 'canonical'
                            else 'fixed_inputs_staged_noncanonical_full_verification_not_claimed')
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
    report['finished_at'] = stamp()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json'), 'error': report.get('error')}), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', type=Path, required=True)
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='NEW output directory')
    parser.add_argument('--mode', choices=['staging', 'canonical'], default='staging')
    args = parser.parse_args()
    try: return run(args.handoff, args.input_root, args.out, args.mode)
    except (Exception, KeyboardInterrupt) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
