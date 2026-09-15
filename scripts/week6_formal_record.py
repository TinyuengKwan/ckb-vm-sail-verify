"""One fixed formal execution with before/after output observations.

Original production commands and policies are not altered. Existing top-level
proof-check records are copied before overwrite; old nested historical clean
builds are not copied or claimed rescanned. Newly created Rust/public proof trees
and this run's Rocq tree are included alongside all mandatory output roots.
No release, clean-room, current whole-workspace or semantic delta approval claim.
"""
import argparse
import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = None
sys.path.insert(0, str(ROOT / 'scripts'))
import check_proof as proof
import generated_output_inventory as inventory
import record_generation as recording
import rebuilt_main_tools as tools
import release_evidence as common
import release_formal_generation_review as formal_review
import source_snapshot as source

POLICY_SHA = 'b5bdc4017628cb065f273a278c7d7458bb6d93b4572eaca0e4788e519e6ab2c3'
PARENT = 'artifacts/boundary-check'
FLAGS = {'release_claimed', 'week6_closed', 'clean_room_claimed',
         'generated_outputs_audited', 'worktree_audit_closed', 'whole_workspace_coverage_claimed'}


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    recording.write(path, value)


def names(root=ROOT):
    directory = recording.regular_directory(root / PARENT)
    return sorted(os.listdir(directory))


def expand(before, earlier, later):
    """Include every new evidence sibling, without assuming its semantic role."""
    inventory.validate(before)
    common.require(type(earlier) is list and type(later) is list and
                   earlier == sorted(set(earlier)) and later == sorted(set(later)), 'invalid evidence parent inventory')
    for name in [*earlier, *later]:
        inventory.safe(name, root_name=True)
        common.require('/' not in name, 'not a direct evidence child')
    common.require(set(earlier) <= set(later), 'existing evidence sibling disappeared')
    added = [PARENT + '/' + n for n in sorted(set(later) - set(earlier))]
    extra = [n for n in before['roots'] if n not in inventory.CANONICAL_ROOTS]
    result = copy.deepcopy(before)
    result['roots'] = inventory.roots([*extra, *added])
    common.require(not (set(added) & result['entries'].keys()), 'new evidence root was already observed')
    result['entries'].update(dict.fromkeys(added))
    result['snapshot_sha256'] = inventory.digest({k: v for k, v in result.items() if k != 'snapshot_sha256'})
    inventory.validate(result)
    return result, added


def archive_top_files(directory, destination):
    """Copy all immediate regular records; never recurse into old clean builds."""
    recording.regular_directory(directory)
    destination.mkdir(exist_ok=False)
    entries = sorted(directory.iterdir())
    records, directories = {}, []
    for path in entries:
        common.require(not path.is_symlink(), 'linked proof-check record')
        if path.is_dir():
            directories.append(path.name)
            continue
        common.require(path.is_file(), 'special proof-check record')
        before = common.sha(path)
        with (destination / path.name).open('xb') as stream:
            stream.write(path.read_bytes())
        common.require(common.sha(path) == before == common.sha(destination / path.name), 'proof-check record changed while copying')
        records[path.name] = before
    common.require(sorted(p.name for p in directory.iterdir()) == [p.name for p in entries], 'proof-check listing changed')
    for name, digest in records.items():
        common.require(common.sha(directory / name) == digest, 'proof-check records changed during archive')
    return {'files': records, 'unscanned_historical_directories': directories,
            'nested_historical_builds_copied': False}


def new_output(path, root=ROOT):
    root, path = Path(root).resolve(), Path(path).absolute()
    parent = root / PARENT
    common.require(parent.is_dir() and not parent.is_symlink() and path.parent == parent and
                   path.name.startswith('week6-formal-') and path.name != 'week6-formal-' and
                   not path.exists() and not path.is_symlink(), 'new Week6 formal output required')
    path.mkdir()
    return path


def main(output):
    global OUT
    OUT = new_output(output)
    producer = Path(__file__).resolve()
    common.require(producer.is_file() and not producer.is_symlink(), 'linked/missing formal producer')
    with (OUT / 'run.py').open('xb') as stream:
        stream.write(producer.read_bytes())
    common.require(common.sha(OUT / 'run.py') == common.sha(producer), 'formal producer copy changed')
    common.require(not (OUT / 'report.json').exists() and not (OUT / 'started.json').exists(), 'new execution only')
    report = {'schema_version': 1, 'kind': 'formal-execution-with-output-delta-v1',
              'started_at': now(), 'status': 'running', 'stages': [], 'errors': [],
              'kernel_and_rocq_records_validated': False, **dict.fromkeys(FLAGS, False)}
    write(OUT / 'started.json', report)
    before = None
    env = dict(os.environ)
    earlier = None

    def stage(name, argv, timeout, selected_env=None):
        print(name, flush=True)
        row = recording.command(OUT, name, argv, env if selected_env is None else selected_env, timeout, ROOT)
        report['stages'].append(row)
        common.require(row['status'] == 'completed' and common.same(row['exit_code'], 0), 'stage failed: ' + name)
        return row

    def capture(label, extra):
        argv = ['/usr/bin/python3', '-B', '-O', 'scripts/generated_output_inventory.py', 'capture',
                '--out', str(OUT / label)]
        for name in extra:
            argv.extend(['--extra-root', name])
        stage('inventory-' + label, argv, 7200)
        return common.read(OUT / label / 'snapshot.json')

    try:
        common.require(common.sha(proof.POLICY) == POLICY_SHA, 'formal source policy changed')
        policy = common.read(proof.POLICY)
        common.require(proof.local_sources() == policy['local_sources'], 'formal source pins differ')
        frozen = source.capture(ROOT)
        write(OUT / 'source-before.json', frozen)
        report['policy_sha256'] = POLICY_SHA
        report['source_snapshot_sha256'] = frozen['snapshot_sha256']
        # Only check lock availability while preserving old files. The original
        # production command takes its own lock when it runs; no skip mechanism.
        lock = proof.ARTIFACTS / '.lock'
        common.require(lock.is_file() and not lock.is_symlink(), 'missing/linked main lock')
        with lock.open('r+') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            report['previous_main_records'] = archive_top_files(proof.ARTIFACTS, OUT / 'previous-main')
        write(OUT / 'previous-main-archive.json', report['previous_main_records'])
        print('resolve admitted formal tools', flush=True)
        env, binaries, support, _ = tools.resolve(ROOT, policy)
        for key in ['PROOF_BUILD_TIMEOUT', 'BASH_ENV', 'ENV', 'ROCQ_SPIKE_WORK', 'ROCQ_SPIKE_SWITCH']:
            env.pop(key, None)
        report['environment_sha256'] = inventory.digest(env)
        inputs = proof.source_evidence(policy, binaries, support)
        write(OUT / 'formal-inputs-before.json', inputs)
        earlier = names()
        write(OUT / 'evidence-parent-before.json', earlier)
        extras = ['artifacts/rebuilt-main-runtime', str((OUT / 'rocq').relative_to(ROOT))]
        before = capture('before', extras)
        common.require(names() == earlier and source.capture(ROOT) == frozen, 'source/evidence parents changed during initial observation')
        for name, digest in report['previous_main_records']['files'].items():
            common.require(common.sha(proof.ARTIFACTS / name) == digest, 'another main execution changed records before launch')
        stage('proof-check', ['/usr/bin/make', 'proof-check', 'BACKEND=lean'], 14400)
        report['main_records'] = archive_top_files(proof.ARTIFACTS, OUT / 'main')
        write(OUT / 'main-archive.json', report['main_records'])
        main_report = common.read(OUT / 'main/report.json')
        common.require(main_report['status'] == 'passed' and main_report['policy_sha256'] == POLICY_SHA, 'wrong/failed main formal record')
        generated = proof.generated_evidence(policy)
        common.require(common.same(generated, main_report['generated']), 'main run left a different generated identity')
        write(OUT / 'generated-after-main.json', generated)
        rocq_env = {**env, 'ROCQ_SPIKE_WORK': str(OUT / 'rocq')}
        stage('proof-spike', ['/usr/bin/make', 'proof-spike'], 3600, rocq_env)
        rocq_report = common.read(OUT / 'rocq/report.json')
        common.require(rocq_report['status'] == 'passed' and rocq_report['verdict'] == 'NO-GO' and
                       rocq_report['extra_proof_coverage'] is False and rocq_report['policy_sha256'] == POLICY_SHA and
                       common.same(rocq_report['generated'], generated) and
                       common.same(proof.generated_evidence(policy), generated), 'Rocq/main final identity mismatch')
        write(OUT / 'generated-after-rocq.json', generated)
    except (Exception, KeyboardInterrupt) as error:
        report['errors'].append({'phase': 'execution', 'error': str(error), 'error_type': type(error).__name__})
    # Even a failed formal command gets a final observation when the initial
    # snapshot exists. Never throw away the failed logs or invent an empty tree.
    if before is not None:
        try:
            later = names()
            write(OUT / 'evidence-parent-after.json', later)
            expanded, added = expand(before, earlier, later)
            write(OUT / 'before-expanded.json', expanded)
            report['new_evidence_roots'] = added
            after = capture('after', [n for n in expanded['roots'] if n not in inventory.CANONICAL_ROOTS])
            delta = inventory.compare(expanded, after)
            write(OUT / 'delta.json', delta)
            report.update(output_summary=inventory.summary(after), output_changes=len(delta['changes']))
            common.require(names() == later, 'new evidence siblings changed during final observation')
            final_source = source.capture(ROOT)
            write(OUT / 'source-after.json', final_source)
            common.require(final_source == frozen, 'source changed during complete formal recording')
            common.require(common.sha(proof.POLICY) == POLICY_SHA, 'policy changed during formal recording')
            if not report['errors']:
                # Only the two original producers may have created siblings.
                common.require(len(added) == 2 and
                               sum(Path(n).name.startswith('rebuilt-production-rust-') for n in added) == 1 and
                               sum(Path(n).name.startswith('public-check-') for n in added) == 1,
                               'unexpected producer output roots require review')
                row = stage('independent-acceptance', ['/usr/bin/python3', '-B', '-O', '-c',
                              formal_review.ACCEPTANCE_CODE,
                              str(OUT / 'main/report.json'), str(OUT / 'rocq/report.json')], 3600)
                marker = 'FORMAL_FINAL_CHECK_JSON='
                values = [json.loads(line[len(marker):]) for line in (OUT / row['log']).read_text().splitlines()
                          if line.startswith(marker)]
                common.require(len(values) == 1 and set(values[0]) == {'lean', 'rocq'}, 'independent formal record inventory')
                report['formal_acceptance'] = values[0]
                common.require(proof.source_evidence(policy, binaries, support) == inputs and
                               common.same(proof.generated_evidence(policy), generated) and source.capture(ROOT) == frozen,
                               'final formal input/source drift')
                report['kernel_and_rocq_records_validated'] = True
        except (Exception, KeyboardInterrupt) as error:
            report['errors'].append({'phase': 'final_observation_or_acceptance', 'error': str(error),
                                     'error_type': type(error).__name__})
    report['status'] = ('formal_execution_and_delta_recorded_pending_worktree_review'
                        if report['kernel_and_rocq_records_validated'] and not report['errors'] else 'failed')
    report['finished_at'] = now()
    # Exclude the possibly large Rocq result tree here: the output inventory
    # captures it completely and its own checked report binds command records.
    report['record_files'] = {p.relative_to(OUT).as_posix(): common.sha(p)
                              for p in sorted(OUT.rglob('*')) if p.is_file() and
                              'rocq' not in p.relative_to(OUT).parts}
    write(OUT / 'report.json', report)
    print(json.dumps({'status': report['status'], 'report': str(OUT / 'report.json')}), flush=True)
    return 0 if not report['errors'] and report['kernel_and_rocq_records_validated'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        with recording.recording_lock():
            sys.exit(main(args.out))
    except (Exception, KeyboardInterrupt) as error:
        print('week6 formal recording rejected: ' + str(error), file=sys.stderr)
        sys.exit(1)
