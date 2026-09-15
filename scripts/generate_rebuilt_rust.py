#!/usr/bin/env python3
"""Explicit rebuilt production generator; old baseline script stays intact.

Requires the rebuilt main profile, performs actual fresh staged extraction,
then installs a model/LLBC pair with retained backups and rollback. Selected
by the formal main gate only through its reviewed policy/code profile.
"""
import fcntl
import json
from pathlib import Path
import shutil
import sys
import tempfile

import rebuilt_main_tools as tools
import rebuilt_production_rust as extraction
import sail_model_transaction as transaction

ROOT = extraction.ROOT
require, sha, read = extraction.require, extraction.sha, extraction.read
STAGES = ['clone-root', 'checkout-root', 'clone-deps-ckb-vm', 'checkout-deps-ckb-vm',
          'clone-deps-sail-riscv', 'checkout-deps-sail-riscv', 'rustc-path', 'rust-version',
          'charon-version', 'aeneas-version', 'fetch-production', 'extract-production', 'translate-production']


def policy_binding(root, report):
    path = root / 'proof/lean/audit/step-policy.json'
    require(report['inputs_after'].get(str(path)) == sha(path),
            'extraction report belongs to another checkout or policy')


def check_provenance(root, policy, provenance):
    tools.policy_identity(policy)
    record = provenance['rebuilt_extraction']
    require(set(record) == {'profile', 'report', 'report_sha256'} and record['profile'] == tools.PROFILE,
            'rebuilt extraction provenance shape')
    name = tools.locations.admitted.safe_name(record['report'])
    path = root / name
    require(Path(name).parts[:2] == ('artifacts', 'boundary-check') and path.name == 'report.json',
            'extraction report outside evidence directory')
    require(sha(tools.locations.admitted.regular(path)) == record['report_sha256'], 'extraction report drift')
    report = read(path)
    require(report['status'] == extraction.STATUS and
            all(report[k] is False for k in extraction.BOUNDARIES), 'staged extraction status/scope')
    policy_binding(root, report)
    require([s['name'] for s in report['stages']] == STAGES, 'staged extraction stage inventory')
    for stage in report['stages']:
        require(type(stage['exit_code']) is int and stage['exit_code'] == 0 and
                stage['log'] == stage['name'] + '.log' and
                sha(path.parent / stage['log']) == stage['log_sha256'], 'staged extraction log drift')
    require(report['inputs_before'] == report['inputs_after'] and
            report['installed_before'] == report['installed_after'] and
            report['runtime_before'] == report['runtime_after'], 'staged extraction input drift')
    require(report['production_selection_sha256'] == extraction.CONFIG_SHA and
            report['model_identity'] == {'sha256': extraction.MODEL_SHA, 'whole_file_identical': True,
                                        'normalization_used': False}, 'production selection/model identity')
    require(report['llbc_sha256'] == provenance['llbc_sha256'] and
            report['model_identity']['sha256'] == provenance['generated_lean_sha256'], 'provenance model pair differs')
    expected = {k: tools.BINARIES[k] for k in ('aeneas', 'charon', 'charon-driver')}
    require({k: v['sha256'] for k, v in report['tools'].items()} == expected, 'extraction base tool identities')
    require(sha(path.parent / 'CkbVmProduction.llbc') == provenance['llbc_sha256'] and
            sha(path.parent / 'generated/CkbVmProduction.lean') == provenance['generated_lean_sha256'],
            'staged original model pair drift')


def install(root, model, llbc, provenance, support_home, move=None):
    """Retain both old outputs and all failed outputs; never recursively delete."""
    move = move or (lambda source, destination: source.rename(destination))
    root = transaction.directory_path(root)
    destination = transaction.directory_path(root / 'proof/lean/generated/rust')
    target = root / 'target/CkbVmProduction.llbc'
    transaction.directory_path(target.parent)
    require(not target.is_symlink() and (not target.exists() or target.is_file()), 'unsafe old LLBC target')
    require(sha(model) == provenance['generated_lean_sha256'] and sha(llbc) == provenance['llbc_sha256'],
            'new model pair differs from provenance')
    destination.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='.rust-install-', dir=destination.parent))
    staged = backup / 'staged'
    staged.mkdir()
    shutil.copyfile(model, staged / 'CkbVmProduction.lean')
    shutil.copyfile(root / 'proof/lean/theorems/lean-toolchain', staged / 'lean-toolchain')
    (staged / 'lakefile.toml').write_text('name = "CkbVmProduction"\ndefaultTargets = ["CkbVmProduction"]\n\n'
        '[[require]]\nname = "Aeneas"\npath = ' + json.dumps(str(support_home / 'backends/lean')) +
        '\n\n[[lean_lib]]\nname = "CkbVmProduction"\n')
    extraction.write(staged / 'SOURCE_BASELINE.json', provenance)
    (staged / 'TOOLCHAIN.txt').write_text('charon=' + tools.VERSIONS['charon'] + '\naeneas=' +
        tools.VERSIONS['aeneas'] + '\nprofile=' + tools.PROFILE + '\nlean_toolchain=' + tools.TOOLCHAIN + '\n')
    staged_llbc = backup / 'staged.llbc'
    shutil.copyfile(llbc, staged_llbc)
    transaction.regular_tree(staged)
    record = {'status': 'running', 'destination': str(destination), 'llbc': str(target),
              'backup': str(backup), 'old_model_saved': False, 'old_llbc_saved': False,
              'new_model_installed': False, 'new_llbc_installed': False, 'policy_changed': False}

    def save(): extraction.write(backup / 'transaction.json', record)

    save()
    try:
        if destination.exists():
            move(destination, backup / 'previous')
            record['old_model_saved'] = True
            save()
        if target.exists():
            move(target, backup / 'previous.llbc')
            record['old_llbc_saved'] = True
            save()
        move(staged, destination)
        record['new_model_installed'] = True
        save()
        move(staged_llbc, target)
        record['new_llbc_installed'] = True
        save()
        require(sha(destination / 'CkbVmProduction.lean') == provenance['generated_lean_sha256'] and
                sha(target) == provenance['llbc_sha256'], 'installed model pair differs')
        record['status'] = 'installed'
        save()
        return record
    except BaseException as error:
        # Rename rollback does not discard a new or old output. Recovery does
        # not call the injectable move hook used to test publication failures.
        if record['new_llbc_installed']: target.rename(backup / 'failed-new.llbc')
        if record['new_model_installed']: destination.rename(backup / 'failed-new-model')
        if record['old_llbc_saved']: (backup / 'previous.llbc').rename(target)
        if record['old_model_saved']: (backup / 'previous').rename(destination)
        record.update(status='failed-restored', error=str(error), error_type=type(error).__name__)
        save()
        error.add_note('Recoverable Rust transaction: ' + str(backup / 'transaction.json'))
        raise


def run():
    policy = read(ROOT / 'proof/lean/audit/step-policy.json')
    tools.policy_identity(policy)  # Reject the existing formal profile before writing anything.
    env, binaries, support, lake = tools.resolve(ROOT, policy)
    before = tools.proof.source_evidence(policy, binaries, support)
    target = ROOT / 'target'
    transaction.directory_path(target).mkdir(parents=True, exist_ok=True)
    lock = target / '.rebuilt-rust.lock'
    require(not lock.is_symlink(), 'linked Rust generation lock')
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out = Path(tempfile.mkdtemp(prefix='rebuilt-production-rust-', dir=ROOT / 'artifacts/boundary-check'))
        require(extraction.run(out, ROOT / 'artifacts/decoder-inputs/rebuilt-v2') == 0,
                'fresh production extraction failed; see ' + str(out / 'report.json'))
        report = read(out / 'report.json')
        provenance = {**tools.proof.ckb_source_baseline.check(ROOT),
                      'generated_lean_sha256': report['model_identity']['sha256'], 'llbc_sha256': report['llbc_sha256'],
                      'rebuilt_extraction': {'profile': tools.PROFILE, 'report': str((out / 'report.json').relative_to(ROOT)),
                                             'report_sha256': sha(out / 'report.json')}}
        check_provenance(ROOT, policy, provenance)
        require(tools.proof.source_evidence(policy, binaries, support) == before, 'source drift before installation')
        result = install(ROOT, out / 'generated/CkbVmProduction.lean', out / 'CkbVmProduction.llbc', provenance, support)
        print(json.dumps(result), flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(run())
    except (Exception, KeyboardInterrupt) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
