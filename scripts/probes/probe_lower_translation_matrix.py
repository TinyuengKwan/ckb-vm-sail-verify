#!/usr/bin/env python3
"""Diagnostic 2x2: old/new join-only Aeneas against old/new lower LLBC.

No model normalization beyond existing raw policy, no proof/adoption claim.
This isolates translator versus LLBC effects, not Charon versus std effects.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from probes import probe_rebuilt_lower_models as lower

require, sha, read = lower.require, lower.sha, lower.read
ORIGIN = ROOT / 'artifacts/boundary-check/rebuilt-lower-models-tt2j7xeu'
ORIGIN_SHA = '5009ba00993188373dd2d502024486884aa8f67f5982495b64516d98e71d0f35'
OLD_FIXTURES = {
    'tests/src/decoder_fn_pointer.rs': '71982b8f933c2ff74ab72e3c1868ec03158b684cac77c36f2ee01c798554b670',
    'tests/src/decoder_shared_closure.rs': '138b9258a27304acd7b135bcb583dfb94239dee28aac41ce1b0b812440327e29',
}


def old_source_identity(source):
    # Historical directory is not a fresh checkout: retain and pin its two
    # reviewed untracked Rust fixtures. They are NOT used by these translations.
    git = lower.aeneas.bundle.git
    commit = git(source, 'rev-parse', 'HEAD').decode().strip()
    require(commit == lower.aeneas.COMMIT, 'old translator source commit drift')
    diff = lower.proof.digest(git(source, 'diff', 'HEAD', '--'))
    require(diff == lower.PATCH_SHA, 'old translator tracked source drift')
    names = set(filter(None, git(source, 'ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')))
    require(names == set(OLD_FIXTURES), 'unreviewed old source fixture set')
    for name, digest in OLD_FIXTURES.items():
        require(sha(lower.snapshot.regular(source, name)) == digest, 'old source fixture drift')
    return {'commit': commit, 'tracked_diff_sha256': diff, 'untracked_fixtures': OLD_FIXTURES,
            'old_tool_rebuilt': False, 'fixtures_translated': False}


def run(out):
    report = {'status': 'running', 'started_at': lower.chain.now(), 'stages': [], 'cells': {},
              'kernel_executed': False, 'policy_changed': False, 'new_tools_approved': False,
              'rust_reextracted': False, 'existing_llbc_translated_for_diagnosis': True,
              'release_claimed': False, 'clean_room_claimed': False}
    env = None

    def save():
        lower.proof.write_json(out / 'report.json', report)

    def stage(name, command):
        row = {'name': name, 'argv': list(map(str, command)), 'cwd': str(out),
               'started_at': lower.chain.now()}
        report['stages'].append(row)
        save()
        print('==> lower-translation-matrix: ' + name, flush=True)
        log = out / (name + '.log')
        try:
            with log.open('xb') as stream:
                result = subprocess.run(row['argv'], cwd=out, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=600)
            row['exit_code'] = result.returncode
            require(result.returncode == 0, 'matrix translation failed')
        finally:
            row.update(finished_at=lower.chain.now(), log=log.name, log_sha256=sha(log))
            save()
        return log.read_text().strip()

    try:
        require(sha(ORIGIN / 'report.json') == ORIGIN_SHA, 'lower source report drift')
        source = read(ORIGIN / 'report.json')
        require(source['status'] == 'lower_models_reextracted_identity_review_required', 'unexpected lower status')
        require(source['inputs_before'] == source['inputs_after'], 'lower inputs changed')
        for name, digest in source['inputs_before'].items():
            require(sha(ROOT / name) == digest, 'lower input drift: ' + name)
        for row in source['stages']:
            lower.chain.evidence.linked(ORIGIN, row['log'], row['log_sha256'])
            lower.check_result(row['exit_code'], (ORIGIN / row['log']).read_text(), row['expected_strict_rejection'])
        components = lower.chain.verify_components()
        require(components == source['components'], 'rebuilt component drift')
        config, policy = read(lower.raw.CONFIG), read(lower.raw.POLICY)
        tools = {'old': ROOT / policy['tool_binary_path'], 'new': Path(source['join_binary']['path'])}
        digests = {'old': policy['tool_binary_sha256'], 'new': source['join_binary']['sha256']}
        sources = {'old': tools['old'].parents[3], 'new': ORIGIN / 'aeneas-source'}
        source_states = {}
        for side in tools:
            lower.chain.executable(tools[side], digests[side])
            source_states[side] = (old_source_identity(sources[side]) if side == 'old' else
                                   lower.check_join_source(sources[side]))
        report['translator_sources'] = source_states
        report['tools'] = {side: {'path': str(tools[side]), 'sha256': digests[side]} for side in tools}
        paths = {Path(__file__), Path(lower.__file__), ORIGIN / 'report.json', lower.raw.CONFIG,
                 lower.raw.POLICY, lower.fields.POLICY, lower.proof.POLICY,
                 ROOT / 'proof/lean/decoder/public-policy.json'}
        paths |= {directory / (stem + '.llbc') for directory in (lower.RAW_DIR, ORIGIN)
                  for stem in ('FactoryScoped', 'MiniComplete')}
        report['inputs_before'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(paths)}
        env = lower.chain.environment(out, components)
        opam = [components['opam']['bootstrap']['path'], 'exec',
                '--switch=' + components['opam']['switch'], '--set-switch', '--']
        for side in tools:
            require(stage(side + '-version', [*opam, tools[side], '-version']) ==
                    'aeneas 379890b5-dirty', 'tool version drift')
        for stem in ('FactoryScoped', 'MiniComplete'):
            for input_side in ('old', 'new'):
                llbc = (lower.RAW_DIR if input_side == 'old' else ORIGIN) / (stem + '.llbc')
                expected = lower.PINS[llbc] if input_side == 'old' else source['models'][stem]['llbc_sha256']
                require(sha(llbc) == expected, 'LLBC identity drift')
                for tool_side in tools:
                    name = stem + '-' + input_side + '-llbc-' + tool_side + '-tool'
                    directory = out / name
                    args = list(config['aeneas_args'])
                    if stem == 'FactoryScoped':
                        args += ['-namespace', config['namespace']]
                    stage(name, [*opam, tools[tool_side], *args, '-dest', directory, llbc])
                    model = directory / (stem + '.lean')
                    report['cells'][name] = {'stem': stem, 'input_side': input_side, 'tool_side': tool_side,
                        'llbc': str(llbc), 'llbc_sha256': sha(llbc), 'model': str(model),
                        'identity': lower.model_identity(stem, model, {}, policy)}
                    save()
        pairs = {}
        for stem in ('FactoryScoped', 'MiniComplete'):
            for side in ('old', 'new'):
                prefix = stem + '-' + side + '-llbc-'
                old = report['cells'][prefix + 'old-tool']['identity']['raw_sha256']
                new = report['cells'][prefix + 'new-tool']['identity']['raw_sha256']
                pairs[stem + '-' + side + '-llbc'] = {'old_tool_raw_sha256': old,
                    'new_tool_raw_sha256': new, 'whole_file_identical': old == new}
        report['same_input_pairs'] = pairs
        for side in tools:
            lower.chain.executable(tools[side], digests[side])
            actual = old_source_identity(sources[side]) if side == 'old' else lower.check_join_source(sources[side])
            require(actual == source_states[side], 'translator source changed')
        require(lower.chain.verify_components() == components, 'component closure changed')
        report['inputs_after'] = {str(path.relative_to(ROOT)): sha(path) for path in sorted(paths)}
        require(report['inputs_after'] == report['inputs_before'], 'matrix input changed')
        report['status'] = 'translation_matrix_complete_no_adoption'
        code = 2
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = lower.chain.now()
    save()
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    out = Path(tempfile.mkdtemp(prefix='lower-translation-matrix-', dir=ROOT / 'artifacts/boundary-check'))
    print(out, flush=True)
    sys.exit(run(out))
