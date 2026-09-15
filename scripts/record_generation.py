#!/usr/bin/env python3
"""Record the real configuration/Rust/Sail generation sequence and whole-tree deltas.

Uses the admitted main tools and existing transactional generators unchanged.
Records are not semantic review, kernel checking, clean-room or release approval.
No arbitrary command, alternate checkout, skip stage or baseline-refresh option.
"""
import argparse
import datetime
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys

import generated_output_inventory as inventory
import source_snapshot

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'artifacts/boundary-check'
PREFIX = 'rebuilt-production-rust-'
EXTRAS = ('artifacts/rebuilt-main-runtime',)
FLAGS = ('regeneration_execution_proven', 'generated_outputs_audited',
         'worktree_audit_closed', 'kernel_executed', 'clean_room_claimed',
         'release_claimed', 'week6_closed')
require = source_snapshot.require


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    import hashlib
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            hasher.update(block)
    return hasher.hexdigest()


def write(path, value):
    import json
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def regular_directory(path):
    path = Path(path).absolute()
    for ancestor in (*reversed(path.parents), path):
        require(not ancestor.is_symlink(), 'linked directory: ' + str(ancestor))
        require(ancestor.is_dir(), 'missing/non-directory: ' + str(ancestor))
    return path


def new_output(path, root=ROOT):
    # Check the lexical spelling before resolution so existing/dangling links
    # cannot silently redirect either the output or the supplied parent.
    path = Path(path).absolute()
    require('..' not in path.parts, 'unsafe recording output')
    regular_directory(path.parent)
    require(path.parent == Path(root) / 'artifacts/generation-runs',
            'recording output must be a new direct child of artifacts/generation-runs')
    require(not path.exists() and not path.is_symlink(), 'recording output already exists')
    path.mkdir()
    return path


def recording_lock(root=ROOT):
    parent = regular_directory(root / 'artifacts/generation-runs')
    fd = os.open(parent / '.record-generation.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    stream = os.fdopen(fd, 'r+')
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return stream
    except BaseException:
        stream.close()
        raise


def recipe():
    return [('sail-config', ['/usr/bin/make', 'sail-config']),
            ('generate-rust', [sys.executable, 'scripts/generate_rebuilt_rust.py']),
            ('generate-sail-lean', ['/bin/bash', 'scripts/generate_proof_model.sh', 'lean']),
            ('generate-sail-rocq', ['/bin/bash', 'scripts/generate_proof_model.sh', 'rocq'])]


def command(out, name, argv, env, timeout, cwd=ROOT):
    require(type(timeout) is int and timeout > 0, 'positive command timeout required')
    record = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd),
              'started_at': now(), 'timeout_seconds': timeout, 'exit_code': None,
              'status': 'starting', 'log': name + '.log'}
    write(out / (name + '-started.json'), record)
    process = None
    try:
        with (out / record['log']).open('xb') as stream:
            process = subprocess.Popen(record['argv'], cwd=cwd, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            record['pid'] = process.pid
            write(out / (name + '-process.json'), record)
            record['exit_code'] = process.wait(timeout=timeout)
            record['status'] = 'completed' if record['exit_code'] == 0 else 'command_failed'
    except BaseException as error:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        record.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'execution_error',
                      error=str(error), error_type=type(error).__name__)
        # A timeout is not the child's ordinary terminal exit code.
        if process is not None:
            record['termination_returncode'] = process.returncode
        if not isinstance(error, (Exception, KeyboardInterrupt)):
            raise
    finally:
        record['finished_at'] = now()
        log = out / record['log']
        if log.exists():
            record['log_sha256'] = sha(log)
        write(out / (name + '-finished.json'), record)
    return record


def parent_names(root):
    directory = regular_directory(root / PARENT)
    return sorted(os.listdir(directory))


def expand_before(before, earlier_names, later_names):
    """Add new Rust staging roots only with recorded pre-run absence evidence.

The original snapshot is retained. No existing directory gets an invented empty
baseline, and every new sibling is rejected unless it matches the fixed producer.
Concurrent unrelated additions are deliberately fail-closed, not filtered away.
"""
    require(type(earlier_names) is list and type(later_names) is list and
            earlier_names == sorted(set(earlier_names)) and
            later_names == sorted(set(later_names)), 'invalid parent listing')
    require(set(earlier_names) <= set(later_names), 'pre-existing evidence root disappeared')
    added = sorted(set(later_names) - set(earlier_names))
    require(all(name.startswith(PREFIX) and name != PREFIX and '/' not in name and
                inventory.safe(name) == name for name in added), 'unclassified new evidence root')
    names = [PARENT + '/' + name for name in added]
    extra = [r for r in before['roots'] if r not in inventory.CANONICAL_ROOTS]
    expanded = {**before, 'roots': inventory.roots([*extra, *names]),
                'entries': {**before['entries'], **dict.fromkeys(names)}}
    expanded['snapshot_sha256'] = inventory.digest({k: v for k, v in expanded.items()
                                                   if k != 'snapshot_sha256'})
    inventory.validate(expanded)
    return expanded, names


def capture_command(out, label, extras, env, timeout):
    argv = [sys.executable, '-B', '-O', 'scripts/generated_output_inventory.py', 'capture',
            '--out', str(out / label)]
    for name in extras:
        argv.extend(['--extra-root', name])
    row = command(out, 'inventory-' + label, argv, env, timeout)
    require(row['status'] == 'completed', 'inventory failed: ' + label)
    return inventory.read_json(out / label / 'snapshot.json')


def sail_transaction(out, stage, backend, before, after, root=ROOT):
    import json
    marker = 'SAIL_INSTALL_JSON='
    lines = (out / stage['log']).read_text().splitlines()
    rows = [json.loads(line[len(marker):]) for line in lines if line.startswith(marker)]
    require(len(rows) == 1, 'missing/duplicate Sail transaction marker')
    row = rows[0]
    require(row['status'] == 'installed' and row['published'] is True and
            row['policy_changed'] is False, 'Sail transaction did not install')
    source = 'deps/sail-riscv/build/' + ('model/Lean_RV64D' if backend == 'lean' else 'rocq')
    destination = 'proof/' + backend + '/generated/sail'
    require(row['source'] == str(root / source) and row['destination'] == str(root / destination),
            'Sail transaction target differs')
    for key, parent, prefix in [('generation_backup', Path(source).parent, '.sail-generation-'),
                                 ('installation_backup', Path(destination).parent, '.sail-install-')]:
        path = Path(row[key])
        require(path.parent == root / parent and path.name.startswith(prefix) and
                path.name != prefix, 'Sail backup outside expected output')
        name = path.relative_to(root).as_posix()
        require(name not in before['entries'] and
                after['entries'].get(name, {}).get('kind') == 'directory', 'Sail transaction is not fresh')
    record = Path(row['installation_backup']) / 'transaction.json'
    name = record.relative_to(root).as_posix()
    require(inventory.read_json(record) == row and
            after['entries'][name]['sha256'] == sha(record), 'Sail transaction record differs')
    for key, base in [('raw_files', source), ('installed_files', destination)]:
        names = row[key]
        require(type(names) is list and names and names == sorted(set(names)), 'Sail file listing')
        observed = sorted(p[len(base) + 1:] for p, v in after['entries'].items()
                          if p.startswith(base + '/') and v is not None and v['kind'] == 'file')
        require(names == observed, 'Sail transaction file inventory differs')
    return row


def run(out, command_timeout=3600, inventory_timeout=3600):
    import check_proof
    import rebuilt_main_tools
    report = {'schema_version': 1, 'kind': 'generation-execution-record-v1',
              'started_at': now(), 'status': 'running', 'stages': [],
              'generation_commands_completed': False, **dict.fromkeys(FLAGS, False)}
    code = 1
    try:
        policy = inventory.read_json(ROOT / 'proof/lean/audit/step-policy.json')
        rebuilt_main_tools.policy_identity(policy)
        # Bind complete source, not just the policy's smaller formal-source list.
        source_before = source_snapshot.capture(ROOT)
        write(out / 'source-before.json', source_before)
        env, binaries, support, lake = rebuilt_main_tools.resolve(ROOT, policy)
        source_evidence = check_proof.source_evidence(policy, binaries, support)
        write(out / 'formal-inputs-before.json', source_evidence)
        report['policy_sha256'] = sha(ROOT / 'proof/lean/audit/step-policy.json')
        # Environment values may contain credentials: retain a digest, never
        # dump the ambient environment into a distributable execution log.
        report['environment_sha256'] = inventory.digest(env)
        report['environment_values_published'] = False
        earlier = parent_names(ROOT)
        write(out / 'evidence-parent-before.json', earlier)
        before = capture_command(out, 'before', EXTRAS, env, inventory_timeout)
        require(parent_names(ROOT) == earlier, 'evidence roots changed before generation')
        require(source_snapshot.capture(ROOT) == source_before, 'source changed before generation')
        for name, argv in recipe():
            print('generation-record: ' + name, flush=True)
            row = command(out, name, argv, env, command_timeout)
            report['stages'].append(row)
            if row['status'] != 'completed':
                break
        # Preserve source/output changes even after an ordinary generator failure.
        later = parent_names(ROOT)
        write(out / 'evidence-parent-after.json', later)
        expanded, added = expand_before(before, earlier, later)
        write(out / 'before-expanded.json', expanded)
        report['new_staging_roots'] = added
        extra = [r for r in expanded['roots'] if r not in inventory.CANONICAL_ROOTS]
        after = capture_command(out, 'after', extra, env, inventory_timeout)
        delta = inventory.compare(expanded, after)
        write(out / 'delta.json', delta)
        source_after = source_snapshot.capture(ROOT)
        write(out / 'source-after.json', source_after)
        report['source_bookends_match'] = source_before == source_after
        require(report['source_bookends_match'], 'source changed during generation recording')
        require(parent_names(ROOT) == later, 'evidence roots changed during final observation')
        completed = len(report['stages']) == len(recipe()) and all(
            row['status'] == 'completed' for row in report['stages'])
        report['generation_commands_completed'] = completed
        require(completed, 'generation command failed; partial evidence retained')
        # The installed provenance must point to the newly observed actual Rust
        # producer; an unchanged old provenance cannot stand in for this run.
        require(len(added) == 1, 'expected exactly one fresh production extraction')
        generated = check_proof.generated_evidence(policy)
        producer = generated['rust_provenance']['rebuilt_extraction']['report']
        require(producer == added[0] + '/report.json', 'Rust provenance is not from this run')
        write(out / 'generated-identities.json', generated)
        sail = {backend: sail_transaction(out, report['stages'][index], backend, expanded, after)
                for index, backend in ((2, 'lean'), (3, 'rocq'))}
        write(out / 'sail-transactions.json', sail)
        require(after['entries']['proof/rocq/generated/sail/ckb_vm_config.json']['sha256'] ==
                generated['sail_config_sha256'], 'Rocq configuration differs')
        require(check_proof.source_evidence(policy, binaries, support) == source_evidence,
                'formal inputs changed during generation')
        # resolve() validates complete admitted installations again, not merely
        # the version strings of a few executables.
        final_env, final_binaries, final_support, final_lake = rebuilt_main_tools.resolve(ROOT, policy)
        require((final_env, final_binaries, final_support, final_lake) == (env, binaries, support, lake),
                'resolved tools/environment changed')
        require(source_snapshot.capture(ROOT) == source_after, 'source changed during final input validation')
        report.update(status='generation_sequence_recorded_pending_review',
                      output_summary=inventory.summary(after), changes=len(delta['changes']),
                      output_scope_is_whole_workspace=False)
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
    finally:
        report['finished_at'] = now()
        # Complete file list, including failed-stage logs and earlier inventory
        # snapshots. These hashes bind evidence bytes, not authenticated authorship.
        report['references'] = {p.relative_to(out).as_posix(): sha(p)
                                for p in sorted(out.rglob('*')) if p.is_file()}
        write(out / 'report.json', report)
    print('generation-record: ' + report['status'] + ' ' + str(out / 'report.json'), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--command-timeout', type=int, default=3600)
    parser.add_argument('--inventory-timeout', type=int, default=3600)
    args = parser.parse_args()
    try:
        require(args.command_timeout > 0 and args.inventory_timeout > 0, 'positive timeouts required')
        with recording_lock():
            return run(new_output(args.out), args.command_timeout, args.inventory_timeout)
    except (Exception, KeyboardInterrupt) as error:
        print('generation-record: rejected: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
