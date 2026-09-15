#!/usr/bin/env python3
"""Kernel-check actual lower models, map equivalence and original raw theorems.

Fresh model/proof oleans; explicitly reuses the existing main/support compiled
dependencies. Strict raw policy must still reject the two changed definitions.
No adoption, full clean-room, or public-decoder candidate proof claim.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import probe_rebuilt_lower_models as lower

require, sha, read = lower.require, lower.sha, lower.read
ORIGIN = ROOT / 'artifacts/boundary-check/rebuilt-lower-models-tt2j7xeu'
ORIGIN_SHA = '5009ba00993188373dd2d502024486884aa8f67f5982495b64516d98e71d0f35'
FIXTURES = ROOT / 'scripts/fixtures/lower-model-equivalence'
CHANGED = {'RawDecodeFactory.core.option.Option.map', 'decoder_shared_closure.core.option.Option.map'}
RENAMES = {'FactoryScoped': ('RawDecodeFactory', 'ArchivedRawDecodeFactory'),
           'MiniComplete': ('decoder_shared_closure', 'archived_decoder_shared_closure')}
STANDARD = {'propext', 'Classical.choice', 'Quot.sound'}


def archived_namespace(data, old, new):
    text = data.decode()
    for prefix in ('namespace ', 'end '):
        before = prefix + old + '\n'
        require(text.count(before) == 1, 'archive namespace anchor not unique')
        text = text.replace(before, prefix + new + '\n')
    return text.encode()


def archive_body_identity(body, stem, expected):
    """Undo only the two internal names introduced by the archived copy.

    Applies to the OLD copy, never new model code or the live raw policy.
    Every remaining byte of the elaborated expression must match that policy.
    """
    require(stem in RENAMES, 'unknown archive model')
    old, new = RENAMES[stem]
    mapped = body
    for before, after in [
        ('`' + new + '.core.option.Option.map.match_1', '`' + old + '.core.option.Option.map.match_1'),
        ('`self.«_@».Archived' + stem + ' ', '`self.«_@».' + stem + ' '),
    ]:
        require(mapped.count(before) == 1, 'archive internal name anchor not unique')
        mapped = mapped.replace(before, after)
    digest = lower.proof.digest(mapped.encode())
    require(digest == expected, 'archive map differs beyond copy-generated internal names')
    return {'raw_sha256': lower.proof.digest(body.encode()), 'original_namespace_sha256': digest,
            'remapped_match_helper_names': 1, 'remapped_hygienic_binder_names': 1,
            'scope': 'archived-copy-only'}


def changed_definitions(actual, expected):
    require(actual['axioms'] == expected['axioms'], 'raw theorem axioms changed')
    require(actual['types'] == expected['types'], 'raw theorem types changed')
    require(set(actual['definitions']) == set(expected['definitions']), 'raw definition set changed')
    changed = {name for name in expected['definitions'] if actual['definitions'][name] != expected['definitions'][name]}
    require(changed == CHANGED, 'unexpected raw definition changes')
    return sorted(changed)


def cached_modules(paths):
    result = {}
    for directory in paths:
        # Lake also lists optional packages whose build directories do not yet
        # exist. Record absence, never silently drop that search-path entry.
        # An actual missing import still fails the real Lean invocation.
        if not directory.exists():
            require(not directory.is_symlink(), 'dangling compiled dependency link')
            result[str(directory)] = {'exists': False, 'files': {}}
            continue
        require(directory.is_dir(), 'compiled dependency path is not a directory')
        files = {str(path.relative_to(directory)): sha(path) for path in sorted(directory.rglob('*'))
                 if path.is_file() and (path.suffix in ('.olean', '.ilean') or '.olean.' in path.name)}
        result[str(directory)] = {'exists': True, 'files': files}
    return result


def check_exit(code, output, reject=None):
    require(not re.search(r'unknown module|unknownIdentifier|unknown constant|maximum.*(?:recursion|heartbeats)|'
                          r'out of memory|Stack overflow|PANIC|Internal error', output, re.I),
            'kernel resource/import/internal failure')
    if reject:
        require(type(code) is int and code == 1 and reject in output, 'wrong semantic rejection')
    else:
        require(type(code) is int and code == 0 and 'sorryAx' not in output, 'kernel stage failed')


def run(out):
    report = {'status': 'running', 'started_at': lower.chain.now(), 'stages': [],
              'kernel_executed': False, 'compiled_main_and_support_reused': True,
              'clean_dependency_build': False, 'clean_room_claimed': False, 'new_tools_approved': False,
              'policy_changed': False, 'release_claimed': False, 'public_candidate_kernel_executed': False}
    env = None

    def save():
        lower.proof.write_json(out / 'report.json', report)

    def stage(name, command, cwd=out, run_env=None, reject=None):
        row = {'name': name, 'argv': list(map(str, command)), 'cwd': str(cwd),
               'expected_rejection': reject, 'started_at': lower.chain.now()}
        report['stages'].append(row)
        save()
        print('==> lower-map-kernel: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=cwd, env=run_env or env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=600)
            row['exit_code'] = result.returncode
            output = log.read_text(errors='replace')
            check_exit(result.returncode, output, reject)
        finally:
            row.update(finished_at=lower.chain.now(), log=log.name, log_sha256=sha(log))
            save()
        return output.strip()

    try:
        require(sha(ORIGIN / 'report.json') == ORIGIN_SHA, 'lower report drift')
        origin = read(ORIGIN / 'report.json')
        require(origin['status'] == 'lower_models_reextracted_identity_review_required', 'unexpected model status')
        require(origin['inputs_before'] == origin['inputs_after'], 'lower inputs changed')
        for name, digest in origin['inputs_before'].items():
            require(sha(ROOT / name) == digest, 'lower input drift: ' + name)
        for row in origin['stages']:
            lower.chain.evidence.linked(ORIGIN, row['log'], row['log_sha256'])
            lower.check_result(row['exit_code'], (ORIGIN / row['log']).read_text(), row['expected_strict_rejection'])
        components = lower.chain.verify_components()
        require(components == origin['components'], 'rebuilt component drift')
        policy, rp, fp = read(lower.proof.POLICY), read(lower.raw.POLICY), read(lower.fields.POLICY)
        lower.proof.require_equal(lower.proof.local_sources(), policy['local_sources'], 'formal sources')
        require(lower.raw.source_hashes() == rp['sources'] and lower.fields.source_hashes() == fp['sources'],
                'lower proof source drift')
        report['formal_generated_before'] = lower.proof.generated_evidence(policy)
        source_paths = {Path(__file__), ORIGIN / 'report.json', lower.proof.POLICY, lower.raw.POLICY, lower.fields.POLICY}
        source_paths |= {ROOT / name for name in set(rp['sources']) | set(fp['sources'])}
        source_paths |= set(FIXTURES.glob('*.lean'))
        source_paths |= {ORIGIN / 'models' / (stem + '.lean') for stem in lower.STEMS}
        source_paths |= {lower.aeneas.PUBLIC / 'models' / (stem + '.lean') for stem in RENAMES}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(source_paths)}
        models = out / 'models'
        models.mkdir()
        for stem in lower.STEMS:
            source = ORIGIN / 'models' / (stem + '.lean')
            require(lower.model_identity(stem, source, fp, rp) == origin['models'][stem]['identity'], 'model drift')
            shutil.copy2(source, models / source.name)
        report['archived_copies'] = {}
        for stem, (old, new) in RENAMES.items():
            source = lower.aeneas.PUBLIC / 'models' / (stem + '.lean')
            require(lower.model_identity(stem, source, fp, rp)['matches_existing_policy'], 'archived model drift')
            data = archived_namespace(source.read_bytes(), old, new)
            target = models / ('Archived' + stem + '.lean')
            target.write_bytes(data)
            report['archived_copies'][stem] = {'source_sha256': sha(source), 'copy_sha256': sha(target),
                                               'old_namespace': old, 'new_namespace': new}
        modules = ['RawFields', 'ExportFieldAudit', *lower.raw.MODULES, 'ExportRawAudit']
        for name in modules:
            shutil.copy2(lower.raw.PROOF / (name + '.lean'), models / (name + '.lean'))
        for path in FIXTURES.glob('*.lean'):
            shutil.copy2(path, models / path.name)
        report['model_and_proof_sources_before'] = {path.name: sha(path) for path in sorted(models.glob('*.lean'))}
        require(not list(models.glob('*.olean')) and not list(models.glob('*.ilean')), 'new model cache not empty')
        report['initial_new_compiled_modules'] = 0
        installation = read(lower.chain.MIR.RUST_REPORT)
        elan = Path(installation['private_homes']['ELAN_HOME'])
        require(lower.chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'Lean install drift')
        compiler = elan / 'toolchains/leanprover--lean4---v4.31.0'
        lean, lake = compiler / 'bin/lean', compiler / 'bin/lake'
        report['lean'] = {'path': str(lean), 'sha256': sha(lean), 'installation_report_sha256': lower.chain.MIR.RUST_SHA}
        env = lower.chain.environment(out, components)
        for key in list(env):
            if key.startswith(('LEAN', 'ELAN')):
                env.pop(key)
        env.update(ELAN_HOME=str(elan), ELAN_TOOLCHAIN=policy['lean_toolchain'], LEAN_ABORT_ON_PANIC='1')
        require('4.31.0' in stage('lean-version', [lean, '--version']), 'Lean version drift')
        value = stage('dependency-path', [lake, 'env', 'printenv', 'LEAN_PATH'], lower.proof.THEOREMS)
        paths = [Path(path).resolve() for path in value.split(os.pathsep)]
        require(len(paths) == len(set(paths)) and all(path.is_absolute() for path in paths), 'ambiguous dependency path')
        report['compiled_dependencies_before'] = cached_modules(paths)
        env['LEAN_PATH'] = str(models) + os.pathsep + os.pathsep.join(map(str, paths))
        report['lean_path'] = env['LEAN_PATH']

        def compile_module(name, directory=models, run_env=None, reject=None, label=None):
            command = [lean, '--root=' + str(directory), directory / (name + '.lean')]
            if not reject:
                command += ['-o', directory / (name + '.olean')]
            return stage(label or 'kernel-' + name, command, run_env=run_env, reject=reject)

        for name in [*lower.STEMS, 'ArchivedFactoryScoped', 'ArchivedMiniComplete', 'LowerMapEquivalence']:
            compile_module(name)
        output = compile_module('ExportLowerMapAudit')
        marker = 'LOWER_MAP_AUDIT_JSON='
        lines = [line[len(marker):] for line in output.splitlines() if line.startswith(marker)]
        require(len(lines) == 1, 'missing map audit')
        audit = json.loads(lines[0])
        require(len(audit['theorems']) == 4 and len(audit['definitions']) == 4, 'incomplete map audit')
        require(all(set(row['axioms']) <= STANDARD for row in audit['theorems'].values()), 'nonstandard map axiom')
        require(all(body != 'NOT_A_DEFINITION' for body in audit['definitions'].values()), 'map replaced by axiom')
        report['archive_body_identities'] = {}
        for stem, (original, archived) in RENAMES.items():
            name = original + '.core.option.Option.map'
            old_name = archived + '.core.option.Option.map'
            report['archive_body_identities'][stem] = archive_body_identity(
                audit['definitions'][old_name], stem, rp['audit']['definitions'][name])
        lower.proof.write_json(out / 'map-audit.json', audit)
        report['map_audit_sha256'] = sha(out / 'map-audit.json')
        compile_module('RawFields')
        field = lower.fields.audit_from(compile_module('ExportFieldAudit'))
        lower.fields.check_audit(field, fp)
        lower.proof.write_json(out / 'field-audit.json', field)
        report['field_audit_sha256'] = sha(out / 'field-audit.json')
        for name in lower.raw.MODULES:
            compile_module(name)
        raw = lower.raw.audit_from(compile_module('ExportRawAudit'))
        summary = lower.fields.audit_summary(raw)
        report['changed_raw_definitions'] = changed_definitions(summary, rp['audit'])
        for name in CHANGED:
            require(raw['definitions'][name] == audit['definitions'][name], 'equivalence/raw body mismatch')
        try:
            lower.raw.check_audit(raw, rp)
        except RuntimeError:
            report['unchanged_raw_policy_rejects_candidate'] = True
        else:
            raise RuntimeError('strict raw policy unexpectedly accepted changed definitions')
        lower.proof.write_json(out / 'raw-audit.json', raw)
        report['raw_audit_sha256'] = sha(out / 'raw-audit.json')
        report['theorem_counts'] = {'map_equivalence': 4, 'fields': len(field['theorems']), 'raw': len(raw['theorems'])}
        wrong = out / 'wrong-result'
        wrong.mkdir()
        text = (models / 'MiniComplete.lean').read_text()
        anchor = 'ok (some t, false)'
        require(text.count(anchor) == 1, 'wrong-result anchor not unique')
        (wrong / 'MiniComplete.lean').write_text(text.replace(anchor, 'ok (none, false)'))
        wrong_env = dict(env, LEAN_PATH=str(wrong) + os.pathsep + env['LEAN_PATH'])
        compile_module('MiniComplete', wrong, wrong_env, label='negative-model-compiles')
        compile_module('LowerMapEquivalence', run_env=wrong_env, reject='unsolved goals', label='negative-wrong-result')
        weak = out / 'false-premise'
        weak.mkdir()
        text = (models / 'LowerMapEquivalence.lean').read_text()
        anchor = 'theorem mini_map_function {T U F : Type}'
        require(text.count(anchor) == 1, 'False anchor not unique')
        (weak / 'LowerMapEquivalence.lean').write_text(text.replace(anchor,
            'theorem mini_map_function (unjustified : False) {T U F : Type}'))
        weak_env = dict(env, LEAN_PATH=str(weak) + os.pathsep + env['LEAN_PATH'])
        compile_module('LowerMapEquivalence', weak, weak_env, label='false-premise-compiles')
        compile_module('ExportLowerMapAudit', run_env=weak_env, reject='type mismatch', label='negative-false-premise')
        require(cached_modules(paths) == report['compiled_dependencies_before'], 'reused compiled dependencies changed')
        require(lower.chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'Lean installation changed')
        require({path.name: sha(path) for path in sorted(models.glob('*.lean'))} ==
                report['model_and_proof_sources_before'], 'model/proof copies changed')
        require(lower.proof.generated_evidence(policy) == report['formal_generated_before'], 'formal model changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(source_paths)}
        require(report['inputs_before'] == report['inputs_after'], 'input/policy drift')
        report.update(status='lower_map_equivalence_and_raw_kernel_checked_admission_pending', kernel_executed=True)
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = lower.chain.now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='lower-map-kernel-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
