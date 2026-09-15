"""Package and byte-roundtrip the fixed extra installations; not a release/clean-room.

Original roots are read only. No canonical-path deployment or policy update.
The admitted decoder archive and project source checkout remain separate inputs.
"""
import datetime
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import fixed_install_bundle as bundle
import install_distribution_review as review
import source_snapshot

ROOT = review.ROOT
REVIEW = ROOT / 'artifacts/boundary-check/install-distribution-cggb3kep/report.json'
REVIEW_SHA = '77780ebf43842ed0cabc7afabba2a05e6d497a332b6a369e6a1a58f42e965122'
require, sha = bundle.require, bundle.sha


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compression', choices=sorted(bundle.COMPRESSION_MAGIC), default='xz',
                        help='package container; xz keeps the same member identity under the 2 GiB asset limit')
    return parser.parse_args(argv)


def main():
    args = parse_args()
    require(len(sys.argv) == 1, 'usage: build_fixed_install_bundle.py (fixed reviewed installations only)')
    out = Path(tempfile.mkdtemp(prefix='fixed-install-package-', dir=ROOT / 'artifacts/boundary-check'))
    report = {'schema_version': 1, 'status': 'running', 'started_at': stamp(), 'phase': 'source-review',
              'clean_room_claimed': False, 'release_claimed': False, 'kernel_executed': False,
              'operational_installation_claimed': False, 'canonical_paths_modified': False,
              'stages': []}
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def phase(name):
        report['phase'] = name
        save()
        print('Phase: ' + name, flush=True)
    def command(name, argv, cwd, env):
        result = subprocess.run([str(x) for x in argv], cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        log = out / (name + '.log')
        log.write_bytes(result.stdout)
        report['stages'].append({'name': name, 'argv': [str(x) for x in argv], 'cwd': str(cwd),
            'exit_code': result.returncode, 'log': log.name, 'log_sha256': sha(log)})
        save()
        require(result.returncode == 0, 'source Git command failed: ' + name)
        return result.stdout.decode().strip()
    code = 1
    try:
        require(sha(REVIEW) == REVIEW_SHA, 'distribution review identity differs')
        reviewed = review.read(REVIEW)
        require(reviewed['status'] == 'installation_inventory_and_copied_sail_smoke_passed_distribution_incomplete',
                'distribution review incomplete')
        report['review'] = {'path': str(REVIEW.relative_to(ROOT)), 'sha256': REVIEW_SHA}
        report['inputs_before'] = review.audit.snapshot()
        require(report['inputs_before'] == reviewed['inputs_before'] == reviewed['inputs_after'], 'formal input drift')
        source = source_snapshot.capture(ROOT)
        (out / 'source-snapshot.json').write_text(json.dumps(source, indent=2, sort_keys=True) + '\n')
        report['source_snapshot_sha256'] = sha(out / 'source-snapshot.json')
        records = {}
        for name, (relative, digest) in review.REPORTS.items():
            require(sha(ROOT / relative) == digest, 'installation report drift: ' + name)
            records[name] = review.read(ROOT / relative)
        sources = {}
        def add(path, name=None):
            path = Path(path)
            name = bundle.safe_name(name or str(path.relative_to(ROOT)))
            require(name not in sources or sources[name] == path, 'conflicting source path')
            sources[name] = path
        def tree(path, destination=None):
            path = Path(path)
            add(path, destination)
            for child in sorted(path.rglob('*')):
                add(child, str(Path(destination) / child.relative_to(path)) if destination else None)
        groups = {}
        for name, row in reviewed['installations'].items():
            prefix = review.anchored(ROOT, row['absolute_path'])
            actual = review.tools.locations.installation_inventory(prefix, row['folders'])
            require(review.inventory_summary(actual) == {key: row[key] for key in review.inventory_summary(actual)},
                    'installed inventory drift: ' + name)
            groups[name] = actual
            for relative in actual['files']: add(prefix / relative)
            for folder in row['folders']:
                if (prefix / folder).exists(): tree(prefix / folder)
        controls = {}
        for name in ['aeneas', 'sail', 'rocq']:
            installation = records[name]
            prefix = review.anchored(ROOT, installation['opam_root'])
            controls[name] = review.control_files(prefix, installation['switch'])
            require(controls[name] == reviewed['opam_control_observation'][name], 'OPAM controls drift: ' + name)
            for relative in controls[name]['files']: add(prefix / relative)
            for folder in ['repo', 'opam-init']:
                add(prefix / folder)
                for path in sorted((prefix / folder).rglob('*')):
                    if path.name == 'lock': continue
                    add(path)
        for relative, _ in review.REPORTS.values(): add(ROOT / relative)
        phase('independent-sail-source-copy')
        compiler_source = review.anchored(ROOT, records['sail']['source'])
        require(source_snapshot.inventory(compiler_source) == records['sail']['source_after'], 'Sail source drift')
        source_snapshot.independent(compiler_source)
        cloned = out / 'sail-source'
        env = {'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
               'GIT_TERMINAL_PROMPT': '0'}
        command('source-clone', ['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--no-hardlinks',
                '--no-checkout', compiler_source, cloned], out, env)
        command('source-checkout', ['git', '-c', 'core.hooksPath=/dev/null', 'checkout', '--detach',
                records['sail']['source_after']['head']], cloned, env)
        command('source-fsck', ['git', 'fsck', '--full', '--strict'], cloned, env)
        require(source_snapshot.inventory(cloned) == records['sail']['source_after'], 'copied Sail source differs')
        source_snapshot.independent(cloned)
        tree(cloned, str(compiler_source.relative_to(ROOT)))
        phase('manifest-and-archive')
        entries = {name: bundle.identity(path) for name, path in sorted(sources.items())}
        bundle.entries_valid(entries)
        manifest = {'schema_version': 1, 'kind': 'extra-fixed-prefix-installations-v1',
            'canonical_checkout': str(ROOT), 'inputs': {
                'main_policy_sha256': sha(review.tools.proof.POLICY),
                'distribution_review': report['review'],
                'source_snapshot_sha256': report['source_snapshot_sha256'],
                'installation_reports': reviewed['installation_reports'],
                'installed_closures': {name: row['sha256'] for name, row in groups.items()},
                'sail_source_commit': records['sail']['source_after']['head'],
                'decoder_archive_sha256': review.read(ROOT / 'proof/lean/decoder/rebuilt-input-policy.json')['archive_sha256']},
            'required_external': [
                'Project HEAD plus the exact separately inventoried dirty source overlay and fixed submodules',
                'Admitted rebuilt-v2 decoder archive and its existing install/verification command',
                'Pinned Rustup/OPAM/bootstrap executables and compatible system tools/dynamic libraries',
                'Canonical absolute checkout path; no report rewriting or relocation admission',
                'Package provenance reports are included, but their complete historical log/output trees are not',
                'Review redistribution permissions and private path metadata before any external publication'],
            'boundaries': {key: False for key in ['clean_room', 'release', 'kernel_execution', 'relocatable',
                                                 'host_closure_complete']}, 'entries': entries}
        manifest_path = out / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        manifest_sha = sha(manifest_path)
        total = sum(row.get('bytes', 0) for row in entries.values())
        free = os.statvfs(out)
        require(free.f_bavail * free.f_frsize > total * 3, 'insufficient workspace space for archive and staged copy')
        archive = out / ('extra-installations.tar.' + args.compression)
        report['manifest_sha256'] = manifest_sha
        report['entries'] = len(entries)
        report['regular_bytes'] = total
        save()
        bundle.write_archive(archive, sources, entries, args.compression)
        phase('verify-and-stage-new-directory')
        report['roundtrip'] = bundle.stage(archive, manifest_path, manifest_sha, out / 'staged')
        report['archive_bytes'] = archive.stat().st_size
        phase('final-source-and-installation-recheck')
        for name, path in sources.items():
            require(bundle.identity(path) == entries[name], 'original package input changed: ' + name)
        staged_source = out / 'staged' / compiler_source.relative_to(ROOT)
        require(command('staged-source-toplevel', ['git', 'rev-parse', '--show-toplevel'], staged_source, env) ==
                str(staged_source), 'staged source is not an independent Git root')
        require(source_snapshot.inventory(staged_source) == records['sail']['source_after'], 'staged Sail source differs')
        source_snapshot.independent(staged_source)
        require(source_snapshot.capture(ROOT) == source, 'full source snapshot changed')
        report['inputs_after'] = review.audit.snapshot()
        require(report['inputs_after'] == report['inputs_before'] and sha(REVIEW) == REVIEW_SHA,
                'formal/review input drift')
        report['status'] = 'fixed_extra_installations_packaged_and_byte_roundtrip_verified'
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
    report['finished_at'] = stamp()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json'),
                      'error': report.get('error')}), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
