#!/usr/bin/env python3
"""Source-only public ADD kernel rebuild using recorded rebuilt-tool outputs.

Reuses generated SOURCE from actual, pinned candidate extraction reports, and
the private Lean compiler/standard library. No project/support compiled cache,
tool adoption, new extraction, complete proof-check or Week6 release claim.
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
import check_lean_clean as clean
import public_decoder_gate as public_gate
from probes import probe_lower_original_negatives as negatives
from probes import probe_decoder_full_mir as full
from probes import probe_sail_model_identity as sail

k = negatives.kernel
lower, chain, gate = k.lower, k.lower.chain, k.lower.proof
require, sha, read = k.require, k.sha, k.read
NEGATIVE = ROOT / 'artifacts/boundary-check/lower-original-negatives-qridxngh'
NEGATIVE_SHA = '1b045c976d4d8de26fbb26443a1d74eb3f7bab320b7a7d2a2939da1dc9e3ad9e'
SAIL = ROOT / 'artifacts/boundary-check/sail-candidate-model-rjsls7ks'
SAIL_SHA = '1bd3ed428d37923841ab351bd83529778adcda47d9d4edca6c51dffcb03a3e49'
PUBLIC = ROOT / 'proof/lean/decoder/toolchain/full-entry'
FULL = ROOT / 'proof/lean/decoder/toolchain/full-mir'
PUBLIC_SHA = 'e2643499ef13d20ed1797dca4d2e6192851fdad0b0e6e53ffc41247ce85fd0b4'
SNAPSHOT_SHA = '33b76c6791a874357ae9859b57ddb8c7b37e689e3c4a7b8edc900386a82e1135'
TARGETS = ['LeanRV64D', 'CkbVmProduction', 'SmokeImports', 'AddRegisterAxioms',
           'RegisterRegression', 'AddStepAxioms', 'StepRegression', 'ProductionAdd',
           'ProductionAddWitness', '+Mathlib.Tactic.IntervalCases']
PUBLIC_MODULES = full.MODULES + full.GENERAL_MODULES + [
    'OuterConversion', 'OuterPublic', 'OuterPublicStep', 'OuterPublicWitness']
# Legacy, uninitialized gitlink in the pinned aesop tree; it is not a Lake
# dependency. Never fetch it or silently treat its absent contents as sources.
INACTIVE_GITLINKS = {'aesop': {'lean_packages/std': 'c2130e653bc1057f8f21196a9b89987d84fe247b'}}


def pinned(path, expected):
    require(sha(path) == expected, 'pinned input drift: ' + str(path))
    return read(path)


def audit_json(output, marker):
    rows = [line[len(marker):] for line in output.splitlines() if line.startswith(marker)]
    require(len(rows) == 1, 'missing or duplicate audit marker')
    return json.loads(rows[0])


def check_success(code, output):
    # A case-insensitive search for "panic" rejects the legitimate module
    # Aeneas.Std.Core.Panic. Use the original main gate's internal-failure
    # signatures plus actual diagnostic lines, not arbitrary identifier text.
    require(type(code) is int and code == 0, 'candidate stage failed')
    require(not gate.INTERNAL_FAILURE.search(output) and 'sorryAx' not in output,
            'candidate internal failure or unaccepted axiom')
    require(not re.search(r'(?mi)^(?:[^\n]*\.lean:\d+:\d+:\s*)?'
                          r'(?:error:|panic\b|internal error\b|out of memory\b)', output),
            'candidate error diagnostic')


def check_rejection(code, output, expected):
    # A wrong theorem can contain Result.fail Error.panic as ordinary data.
    # Require the expected diagnostic, not just its text in a displayed term.
    require(type(code) is int and code == 1, 'negative did not exit with a Lean error')
    require(re.search(r'(?m)^(?:[^\n]*\.lean:\d+:\d+:\s*)?error:\s*' + expected,
                      output) is not None, 'missing intended Lean rejection diagnostic')
    require(not gate.INTERNAL_FAILURE.search(output) and 'sorryAx' not in output and
            not re.search(r'unknownIdentifier|unknown identifier|unknown namespace|unknown module|'
                          r'unknown constant|object file .* does not exist|failed to import|'
                          r'maximum.*(?:heartbeats|recursion)|out of memory|stack overflow|'
                          r'deterministic timeout|timed out|internal error|uncaught exception', output, re.I) and
            not re.search(r'(?mi)^\s*(?:[^\n]*\.lean:\d+:\d+:\s*)?(?:error:\s*)?panic\b|'
                          r"^thread [^\n]* panicked\b", output),
            'infrastructure/internal failure is not a Lean semantic rejection')


def linked_public(data):
    anchor = b'import Aeneas\n'
    require(data.count(anchor) == 1, 'public import anchor not unique')
    return data.replace(anchor, anchor + b'import CkbVmProduction\n', 1)


def remap_support(text, destination):
    # Exact reviewed layout remap, not a generated Lean code normalization.
    old = 'path = "/home/clair/.local/share/aeneas/backends/lean"'
    require(text.count(old) == 1, 'unexpected generated Rust support path')
    return text.replace(old, 'path = ' + json.dumps(str(destination)), 1)


def source_inventory(directory):
    """All non-cache source/config bytes, not just .lean files."""
    return gate.tree_files(directory, lambda p: not (
        p.suffix in ('.olean', '.ilean', '.o', '.so', '.a') or '.olean.' in p.name))


def compiled_files(directory):
    return [str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and
            (p.suffix in ('.olean', '.ilean') or '.olean.' in p.name)]


def tracked_sources(directory):
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=directory, timeout=60).split(b'\0')
    result = {}
    links = INACTIVE_GITLINKS.get(directory.name, {})
    seen_links = set()
    for raw in names:
        if not raw:
            continue
        name = raw.decode()
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts, 'unsafe tracked source path')
        source = directory / path
        if name in links:
            index = subprocess.check_output(['git', 'ls-files', '-s', '--', name],
                                            cwd=directory, text=True, timeout=60).strip()
            require(index == '160000 ' + links[name] + ' 0\t' + name and not source.is_symlink() and
                    (not source.exists() or (source.is_dir() and not any(source.iterdir()))),
                    'inactive gitlink changed or populated')
            seen_links.add(name)
            continue
        # Some pinned upstream scripts are relative symlinks to other tracked
        # files. Git revision/clean-status checks bind the link text; also bind
        # its contents and forbid external or dangling targets.
        require(source.is_file() and source.resolve().is_relative_to(directory.resolve()),
                'missing or escaping tracked dependency source')
        result[name] = sha(source)
    require(result and seen_links == set(links), 'empty tracked dependency source or missing gitlink')
    return result


def candidate_raw(audit, original, expected, map_audit):
    summary = lower.fields.audit_summary(audit)
    changes = k.changed_definitions(summary, original['audit'])
    require(audit == expected, 'candidate raw audit differs from fixed kernel evidence')
    for name in k.CHANGED:
        require(audit['definitions'][name] == map_audit['definitions'][name], 'raw/map body mismatch')
    try:
        lower.raw.check_audit(audit, original)
    except RuntimeError:
        return changes
    raise RuntimeError('original raw policy unexpectedly accepted candidate')


def public_summary(audit, expected):
    summary = full.audit_summary(audit)
    if 'contracts' in audit:
        summary['contracts'] = {name: gate.digest(value.encode()) for name, value in audit['contracts'].items()}
    for name, row in summary['theorems'].items():
        require(not any(re.search(r'sorryAx|_native|native_decide', a) for a in row['axioms']),
                'unaccepted public theorem dependency: ' + name)
    require(summary == expected, 'public theorem/type/body/contract snapshot changed')
    return summary


def prior_stages(directory, report, kind):
    for row in report['stages']:
        chain.evidence.linked(directory, row['log'], row['log_sha256'])
        output = (directory / row['log']).read_text()
        if kind == 'lower':
            lower.check_result(row['exit_code'], output, row['expected_strict_rejection'])
        elif row.get('expected_rejection') == 'strict-join':
            require(type(row['exit_code']) is int and row['exit_code'] == 2, 'strict exit drift')
            lower.check_result(row['exit_code'], output, strict=True)
        else:
            k.check_exit(row['exit_code'], output, row.get('expected_rejection'))


def verify_inputs():
    kr = pinned(negatives.ORIGIN / 'report.json', negatives.ORIGIN_SHA)
    nr = pinned(NEGATIVE / 'report.json', NEGATIVE_SHA)
    lr = pinned(k.ORIGIN / 'report.json', k.ORIGIN_SHA)
    require(kr['status'] == 'lower_map_equivalence_and_raw_kernel_checked_admission_pending' and
            len(kr['stages']) == 23, 'kernel candidate incomplete')
    require(nr['status'] == 'original_lower_negatives_and_runtime_completed_admission_pending' and
            len(nr['stages']) == 17, 'original negatives incomplete')
    require(lr['status'] == 'lower_models_reextracted_identity_review_required' and len(lr['stages']) == 26,
            'lower extraction incomplete')
    for directory, report, kind in [(negatives.ORIGIN, kr, 'kernel'), (NEGATIVE, nr, 'negative'),
                                     (k.ORIGIN, lr, 'lower')]:
        require(report['inputs_before'] == report['inputs_after'], 'prior inputs changed')
        for name, digest in report['inputs_before'].items():
            require(sha(ROOT / name) == digest, 'prior source drift: ' + name)
        prior_stages(directory, report, kind)
    components = chain.verify_components()
    require(components == lr['components'], 'tool closure differs from extraction')
    checkout, state = lower.candidate()
    require(lower.snapshot.capture(Path(lr['checkout'])) == state, 'lower candidate source differs')
    joint = read(lower.ORIGIN / 'report.json')
    require(joint['components'] == components, 'joint extraction components differ')
    for stem, row in lr['models'].items():
        require(sha(Path(row['llbc'])) == row['llbc_sha256'] and
                lower.model_identity(stem, Path(row['model']), read(lower.fields.POLICY),
                                     read(lower.raw.POLICY)) == row['identity'], 'lower model/LLBC drift')
    for row in joint['models'].values():
        require(sha(Path(row['model'])) == row['raw_sha256'] and sha(Path(row['llbc'])) == row['llbc_sha256'],
                'joint model or LLBC drift')
    require(chain.identity.check(Path(joint['models']['public']['model']), checkout) ==
            joint['models']['public']['model_identity'], 'public generated identity')
    require(chain.identity.check_iterator(Path(joint['models']['iterator']['model']), checkout, lower.ORIGIN) ==
            joint['models']['iterator']['model_identity'], 'iterator generated identity')
    policy = read(gate.POLICY)
    require(gate.local_sources() == policy['local_sources'], 'formal source drift')
    pp = pinned(public_gate.POLICY, PUBLIC_SHA)
    require(public_gate.sources() == pp['sources'], 'public source drift')
    pinned(PUBLIC / 'audit-snapshot.json', SNAPSHOT_SHA)
    sr = pinned(SAIL / 'report.json', SAIL_SHA)
    require(sr['status'] == 'failed' and sr['error'] == 'raw candidate model differs' and
            len(sr['stages']) == 5, 'unexpected Sail comparison disposition')
    prior_stages(SAIL, sr, 'sail')
    # Only the already audited exact-install migration may satisfy old pins.
    historical = {'proof/lean/audit/step-policy.json', 'scripts/check_proof.py'}
    for name, digest in sr['inputs_before'].items():
        path = chain.MIGRATION / 'source' / name if name in historical else ROOT / name
        require(sha(path) == digest, 'Sail generation input drift: ' + name)
    raw_sail = SAIL / 'candidate-build'
    require(sail.raw_outputs(raw_sail) == sr['candidate_outputs'], 'Sail generated outputs drift')
    require(sr['candidate_outputs']['lean'] == sr['baseline_outputs']['lean'] and
            sr['model_comparisons']['lean']['identical'], 'Sail Lean raw identity changed')
    si = pinned(sail.INSTALL_REPORT, sail.INSTALL_SHA)
    require(sail.install.check_source(Path(si['source'])) == si['source_after'], 'Sail compiler source drift')
    require(sail.install.rocq.installed_inventory(Path(si['prefix'])) == si['installed_closure'],
            'Sail compiler installation drift')
    require(lower.snapshot.inventory(Path(sr['model_source'])) == sr['model_source_before'] ==
            lower.snapshot.inventory(ROOT / 'deps/sail-riscv'), 'Sail model source drift')
    ar = read(Path(components['reports']['aeneas']['path']))
    support = Path(ar['sides']['base']['source']) / 'backends/lean'
    require(gate.digest(gate.canonical(gate.tree_files(support, gate.lean_sources))) ==
            policy['aeneas_lean_sources_sha256'], 'new Aeneas support identity')
    return {'kernel': kr, 'negative': nr, 'lower': lr, 'joint': joint, 'sail': sr,
            'components': components, 'support': str(support), 'source_snapshot': state}


def run(out):
    report = {'status': 'running', 'started_at': chain.now(), 'stages': [],
              'policy_changed': False, 'new_tools_approved': False, 'release_claimed': False,
              'clean_room_claimed': False, 'third_party_claimed': False, 'full_proof_check_claimed': False,
              'rust_reextracted_this_run': False, 'sail_reextracted_this_run': False,
              'generated_sources_reused_from_candidate_reports': True,
              'project_or_support_compiled_cache_reused': False, 'public_candidate_kernel_executed': False,
              'full_translator_qualification_executed': False, 'sail_cpp_difference_resolved': False}
    env = None

    def save():
        gate.write_json(out / 'report.json', report)

    def stage(name, args, cwd=out, run_env=None, reject=None, timeout=600):
        actual_env = run_env or env
        row = {'name': name, 'argv': list(map(str, args)), 'cwd': str(cwd), 'started_at': chain.now(),
               'lean_path': actual_env.get('LEAN_PATH'), 'expected_rejection': reject}
        report['stages'].append(row)
        save()
        print('==> rebuilt-public-kernel: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                process = subprocess.run(row['argv'], cwd=cwd, env=actual_env, stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=timeout)
            row['exit_code'] = process.returncode
            output = log.read_text(errors='replace')
            if reject:
                check_rejection(process.returncode, output, reject)
            else:
                check_success(process.returncode, output)
        finally:
            row.update(finished_at=chain.now(), log=log.name, log_sha256=sha(log))
            save()
        return output.strip()

    try:
        verified = verify_inputs()
        report['candidate_evidence'] = {str(path.relative_to(ROOT)): sha(path) for path in (
            negatives.ORIGIN / 'report.json', NEGATIVE / 'report.json', k.ORIGIN / 'report.json',
            lower.ORIGIN / 'report.json', SAIL / 'report.json')}
        policy, rp, fp = read(gate.POLICY), read(lower.raw.POLICY), read(lower.fields.POLICY)
        report['formal_generated_before'] = gate.generated_evidence(policy)
        report['components'] = verified['components']
        inputs = {Path(__file__), Path(clean.__file__), Path(full.__file__), public_gate.POLICY,
                  sail.ADAPTER, sail.TOOLCHAIN, gate.THEOREMS / 'lake-manifest.json',
                  ROOT / 'proof/lean/generated/rust/lakefile.toml'}
        inputs |= {ROOT / name for name in verified['negative']['inputs_before']}
        inputs |= {ROOT / name for name in read(public_gate.POLICY)['sources']}
        inputs |= {ROOT / name for name in policy['local_sources']}
        inputs |= {ROOT / name for name in report['candidate_evidence']}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        installation = read(chain.MIR.RUST_REPORT)
        elan = Path(installation['private_homes']['ELAN_HOME'])
        require(chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'Lean installation drift')
        compiler = elan / 'toolchains/leanprover--lean4---v4.31.0'
        lake, lean = compiler / 'bin/lake', compiler / 'bin/lean'
        report['lean'] = {'prefix': str(compiler), 'lean_sha256': sha(lean), 'lake_sha256': sha(lake),
                          'installation_report_sha256': chain.MIR.RUST_SHA}
        env = chain.environment(out, verified['components'])
        for key in list(env):
            if key.startswith(('LEAN', 'ELAN')):
                env.pop(key)
        env.update(LEAN_NUM_THREADS='8', LEAN_ABORT_ON_PANIC='1', ELAN_HOME=str(elan),
                   PATH=str(compiler / 'bin') + os.pathsep + env['PATH'])
        work = out / 'clean'
        project = work / 'proof/lean/theorems'
        for relative in ('proof/lean/theorems', 'proof/lean/generated/rust', 'proof/lean/audit', 'proof/lean/compat'):
            clean.source_copy(ROOT / relative, work / relative)
        # Install actual recorded candidate source, not the old model as a substitute.
        main = Path(verified['joint']['models']['main']['model'])
        require(sha(main) == sha(ROOT / 'proof/lean/generated/rust/CkbVmProduction.lean'), 'main model identity')
        shutil.copyfile(main, work / 'proof/lean/generated/rust/CkbVmProduction.lean')
        sail_model = work / 'proof/lean/generated/sail'
        shutil.copytree(SAIL / 'candidate-build/model/Lean_RV64D', sail_model)
        stage('adapt-candidate-sail', ['patch', '--batch', '--forward', '--fuzz=0', '-p0',
              '--directory=' + str(sail_model), '--input=' + str(sail.ADAPTER)])
        shutil.copyfile(sail.TOOLCHAIN, sail_model / 'lean-toolchain')
        require(gate.tree_files(sail_model, gate.lean_sources) == report['formal_generated_before']['models']['sail'],
                'adapted candidate Sail model differs from formal policy')
        report['candidate_sail_adapted_sources'] = gate.tree_files(sail_model, gate.lean_sources)
        support = work / 'support/Aeneas'
        clean.source_copy(Path(verified['support']), support)
        require(source_inventory(support) == source_inventory(Path(verified['support'])), 'support source/config copy')
        (project / '.lake').mkdir()
        (project / '.lake/aeneas').symlink_to(support, target_is_directory=True)
        config = work / 'proof/lean/generated/rust/lakefile.toml'
        original_config = config.read_text()
        config.write_text(remap_support(original_config, support))
        report['layout_remap'] = {'source_sha256': gate.digest(original_config.encode()),
                                 'candidate_sha256': sha(config), 'scope': 'one dependency path only'}
        report['dependencies'] = {}
        manifest = read(project / 'lake-manifest.json')
        for package in manifest['packages']:
            if package['type'] != 'git':
                continue
            name = package['name']
            require(re.fullmatch(r'[A-Za-z0-9_-]+', name) is not None, 'unsafe package name')
            origin = gate.THEOREMS / manifest['packagesDir'] / name
            target = project / manifest['packagesDir'] / name
            require(gate.output(['git', 'rev-parse', 'HEAD'], origin) == package['rev'] and
                    gate.output(['git', 'status', '--porcelain'], origin) == '', 'dependency source not pinned/clean')
            target.parent.mkdir(parents=True, exist_ok=True)
            stage('clone-' + name, ['git', 'clone', '--quiet', '--no-hardlinks', '--no-checkout', origin, target])
            stage('checkout-' + name, ['git', 'checkout', '--quiet', '--detach', package['rev']], target)
            lower.snapshot.independent(target)
            tracked = tracked_sources(origin)
            require(tracked_sources(target) == tracked and source_inventory(target) == tracked,
                    'dependency tracked source copy differs: ' + name)
            original_files = source_inventory(origin)
            report['dependencies'][name] = {'revision': package['rev'], 'source_sha256':
                gate.digest(gate.canonical(tracked)), 'git_objects_shared': False,
                'uninitialized_unused_gitlinks': INACTIVE_GITLINKS.get(name, {}),
                'tracked_internal_symlinks': {key: os.readlink(target / key)
                    for key in tracked if (target / key).is_symlink()},
                'origin_nontracked_noncache_files_not_copied': {
                    key: original_files[key] for key in sorted(original_files.keys() - tracked.keys())}}
        models = out / 'models'
        models.mkdir()
        originals = {}
        for stem in lower.STEMS:
            originals[stem] = k.ORIGIN / 'models' / (stem + '.lean')
            require(sha(originals[stem]) == verified['lower']['models'][stem]['identity']['raw_sha256'], 'new lower source drift')
        for stem in ['RawFields', *lower.raw.MODULES, 'ExportFieldAudit', 'ExportRawAudit']:
            originals[stem] = lower.raw.PROOF / (stem + '.lean')
        for stem in PUBLIC_MODULES + ['ExportFullMirAudit', 'ExportGeneralAudit', 'ExportPublicAudit', 'RejectWrongPublic']:
            directory = PUBLIC if stem.startswith('OuterPublic') or stem in ('OuterConversion', 'ExportPublicAudit', 'RejectWrongPublic') else FULL
            originals[stem] = directory / (stem + '.lean')
        for stem in ['LowerMapEquivalence', 'ExportLowerMapAudit']:
            originals[stem] = k.FIXTURES / (stem + '.lean')
        for stem, source in originals.items():
            shutil.copyfile(source, models / (stem + '.lean'))
        for stem, (old, new) in k.RENAMES.items():
            source = lower.aeneas.PUBLIC / 'models' / (stem + '.lean')
            require(lower.model_identity(stem, source, fp, rp)['matches_existing_policy'], 'archived model identity')
            (models / ('Archived' + stem + '.lean')).write_bytes(k.archived_namespace(source.read_bytes(), old, new))
        public_source = Path(verified['joint']['models']['public']['model'])
        (models / 'OuterRawLinked.lean').write_bytes(linked_public(public_source.read_bytes()))
        shutil.copyfile(Path(verified['joint']['models']['iterator']['model']), models / 'FnPtrFullMir.lean')
        report['model_and_proof_sources_before'] = {p.name: sha(p) for p in sorted(models.glob('*.lean'))}
        report['clean_sources_before'] = source_inventory(work)
        require(compiled_files(out) == [], 'compiled project/support cache copied')
        report['initial_compiled_modules'] = 0
        require(Path(stage('compiler-prefix', [lake, 'env', 'lean', '--print-prefix'], project)).resolve() ==
                compiler.resolve(), 'compiler escaped private installation')
        base = stage('lean-path', [lake, 'env', 'printenv', 'LEAN_PATH'], project)
        report['lean_search_paths'] = clean.check_paths(base, out, compiler)
        stage('clean-main-build', [lake, '--no-cache', 'build', *TARGETS], project, timeout=5400)
        env['LEAN_PATH'] = base
        audit = gate.parse_audit(stage('main-audit', [lean, work / 'proof/lean/audit/ExportStepAudit.lean'], project))
        gate.check_audit(audit, policy)
        gate.write_json(out / 'main-audit.json', audit)
        report['main_axiom_count'] = len(audit['axioms'])
        env['LEAN_PATH'] = str(models) + os.pathsep + base
        report['public_lean_search_paths'] = clean.check_paths(env['LEAN_PATH'], out, compiler)

        def compile_module(stem, directory=models, run_env=None, label=None, reject=None):
            return stage(label or 'kernel-' + stem, [lean, '--root=' + str(directory),
                         directory / (stem + '.lean'), '-o', directory / (stem + '.olean')],
                         project, run_env=run_env, reject=reject)

        for stem in [*lower.STEMS, 'ArchivedFactoryScoped', 'ArchivedMiniComplete', 'LowerMapEquivalence']:
            compile_module(stem)
        ma = audit_json(compile_module('ExportLowerMapAudit'), 'LOWER_MAP_AUDIT_JSON=')
        require(ma == read(negatives.ORIGIN / 'map-audit.json') and
                sha(negatives.ORIGIN / 'map-audit.json') == verified['kernel']['map_audit_sha256'], 'map audit drift')
        for stem, (old, archived) in k.RENAMES.items():
            k.archive_body_identity(ma['definitions'][archived + '.core.option.Option.map'], stem,
                                    rp['audit']['definitions'][old + '.core.option.Option.map'])
        gate.write_json(out / 'map-audit.json', ma)
        compile_module('RawFields')
        fa = lower.fields.audit_from(compile_module('ExportFieldAudit'))
        lower.fields.check_audit(fa, fp)
        gate.write_json(out / 'field-audit.json', fa)
        for stem in lower.raw.MODULES:
            compile_module(stem)
        ra = lower.raw.audit_from(compile_module('ExportRawAudit'))
        require(sha(negatives.ORIGIN / 'raw-audit.json') == verified['kernel']['raw_audit_sha256'], 'fixed raw audit drift')
        report['candidate_raw_definition_changes'] = candidate_raw(ra, rp, read(negatives.ORIGIN / 'raw-audit.json'), ma)
        report['unchanged_raw_policy_rejects_candidate'] = True
        gate.write_json(out / 'raw-audit.json', ra)
        for stem in ['FnPtrFullMir', 'OuterRawLinked', *PUBLIC_MODULES]:
            compile_module(stem)
        snapshots = read(PUBLIC / 'audit-snapshot.json')
        report['public_audits'] = {}
        for label, exporter, marker in [('full-mir', 'ExportFullMirAudit', 'FULL_MIR_AUDIT_JSON='),
            ('general', 'ExportGeneralAudit', 'GENERAL_DECODER_AUDIT_JSON='),
            ('public', 'ExportPublicAudit', 'PUBLIC_DECODER_AUDIT_JSON=')]:
            actual = audit_json(stage('audit-' + label, [lean, models / (exporter + '.lean')], project), marker)
            summary = public_summary(actual, snapshots[label])
            gate.write_json(out / (label + '-audit.json'), actual)
            gate.write_json(out / (label + '-summary.json'), summary)
            report['public_audits'][label] = {'theorem_count': len(actual['theorems']),
                'definition_count': len(actual['definitions']), 'contract_count': len(actual.get('contracts', {})),
                'audit_sha256': sha(out / (label + '-audit.json'))}
        stage('negative-wrong-public', [lean, models / 'RejectWrongPublic.lean'], project, reject='Type mismatch')
        weakened = out / 'weakened-public'
        weakened.mkdir()
        text = (models / 'OuterPublic.lean').read_text()
        require(text.count('/-- Original ADD word') == 1, 'public weakening boundary drift')
        prefix = text.split('/-- Original ADD word', 1)[0]
        prefix = negatives.mutate(prefix, 'theorem public_mop_off {M R : Type}',
                                 'theorem public_mop_off (unused : False) {M R : Type}')
        (weakened / 'OuterPublic.lean').write_text(prefix + '\nend\nend OuterAdd\n')
        bad_env = dict(env, LEAN_PATH=str(weakened) + os.pathsep + env['LEAN_PATH'])
        compile_module('OuterPublic', weakened, bad_env, 'public-false-compiles')
        exporter = weakened / 'ExportWeakening.lean'
        exporter.write_text('import OuterPublic\nimport Lean\nopen Lean Elab Command\n'
            'run_cmd do\n  let info ← getConstInfo ``OuterAdd.public_mop_off\n'
            '  liftIO <| IO.println ("TYPE=" ++ (Lean.Json.str (reprStr info.type)).compress)\n')
        altered = audit_json(stage('public-false-audit', [lean, exporter], project, run_env=bad_env), 'TYPE=')
        altered_sha = gate.digest(altered.encode())
        require(altered_sha != snapshots['public']['theorems']['OuterAdd.public_mop_off']['type_sha256'],
                'public False premise accepted by exact type audit')
        report['public_false_premise'] = {'source_sha256': sha(weakened / 'OuterPublic.lean'),
            'exporter_sha256': sha(exporter), 'altered_type_sha256': altered_sha, 'rejected_by_type_audit': True}
        require(source_inventory(work) == report['clean_sources_before'], 'clean source/config changed during build')
        require({p.name: sha(p) for p in sorted(models.glob('*.lean'))} == report['model_and_proof_sources_before'],
                'model/proof source changed during build')
        for name, row in report['dependencies'].items():
            target = project / manifest['packagesDir'] / name
            lower.snapshot.independent(target)
            require(gate.output(['git', 'rev-parse', 'HEAD'], target) == row['revision'] and
                    gate.output(['git', 'status', '--porcelain'], target) == '', 'dependency changed during build')
            require(gate.digest(gate.canonical(tracked_sources(target))) == row['source_sha256'],
                    'dependency source/config content changed during build')
        require(verify_inputs() == verified, 'candidate input/tool closure changed during build')
        require(gate.generated_evidence(policy) == report['formal_generated_before'], 'formal generated models changed')
        require(chain.MIR.rust.inventory(elan) == installation['installed_closures']['elan'], 'Lean installation changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(inputs)}
        require(report['inputs_after'] == report['inputs_before'], 'input/policy drift')
        report['compiled_modules_after'] = len(list(out.rglob('*.olean')))
        report.update(status='rebuilt_public_kernel_checked_admission_pending', public_candidate_kernel_executed=True)
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = chain.now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='rebuilt-public-kernel-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
