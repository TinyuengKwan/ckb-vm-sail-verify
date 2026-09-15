#!/usr/bin/env python3
"""Prepare a fresh source/cache candidate for the real main proof-check.

Only the new clone receives the explicit adapter/policy changes. Installs the
admitted tool payload and restores Git dependencies without object hardlinks;
reuses hash-verified private compiler installations, not project build caches.
No formal adoption, proof execution, compiler rebuild or clean-room claim.
"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rebuilt_main_tools as tools
import rebuilt_production_rust as extraction
import source_snapshot as snapshot

require, sha, read = tools.require, tools.sha, tools.read
OLD_POLICY = 'ca6e062b62c448e428fb016a0442d1b271872c26539573077d494b84d074a79f'
PROOF = ROOT / 'artifacts/boundary-check/approved-rebuilt-proof-YQTKZPMC/report.json'
PROOF_SHA = '4385aea4114c1aedc07d7db392d641d46089ed12842ded83bcd4e0b2396ac4a6'
ARCHIVE = ROOT / 'artifacts/boundary-check/rebuilt-input-candidate-z2k9y4hg/rebuilt-decoder-candidate.tar.gz'
EXTRA_TESTS = ['test_rebuilt_main_tools', 'test_generate_rebuilt_rust',
               'test_rebuilt_production_rust', 'test_source_snapshot']
TOOLS_MARKER = 'REBUILT_MAIN_TOOLS_JSON='


def parse_tools_log(output):
    rows = [line[len(TOOLS_MARKER):] for line in output.splitlines() if line.startswith(TOOLS_MARKER)]
    require(len(rows) == 1, 'missing or duplicate candidate tools record')
    result = json.loads(rows[0])
    require(type(result) is dict and set(result) == {'source', 'lake', 'environment'}, 'candidate tools record shape')
    return result


def replace_once(text, before, after):
    require(text.count(before) == 1, 'candidate adapter anchor absent or ambiguous')
    return text.replace(before, after, 1)


def adapter(text):
    edits = [
        ('    return files\n\n\ndef tools_and_environment(policy):\n',
         '    import rebuilt_main_tools\n    for name in rebuilt_main_tools.SOURCES:\n'
         '        files[name] = file_hash(ROOT / name)\n    return files\n\n\ndef tools_and_environment(policy):\n'),
        ('def tools_and_environment(policy):\n    env = os.environ.copy()\n',
         'def tools_and_environment(policy):\n    if "main_toolchain" in policy:\n'
         '        import rebuilt_main_tools\n        return rebuilt_main_tools.resolve(ROOT, policy)\n'
         '    env = os.environ.copy()\n'),
        ('    for name, value in ckb_source_baseline.check(ROOT).items():\n',
         '    if "main_toolchain" in policy:\n        import generate_rebuilt_rust\n'
         '        generate_rebuilt_rust.check_provenance(ROOT, policy, provenance)\n'
         '    for name, value in ckb_source_baseline.check(ROOT).items():\n'),
        ('    run_stage("generate-rust", ["bash", "scripts/generate_rust_model.sh"], env, report)\n',
         '    generator = ([sys.executable, "scripts/generate_rebuilt_rust.py"] if "main_toolchain" in policy\n'
         '                 else ["bash", "scripts/generate_rust_model.sh"])\n'
         '    run_stage("generate-rust", generator, env, report)\n'),
        ('"test_decoder_rebuilt_locations"):\n',
         '"test_decoder_rebuilt_locations", "test_rebuilt_main_tools",\n'
         '                 "test_generate_rebuilt_rust", "test_rebuilt_production_rust", "test_source_snapshot"):\n'),
    ]
    for before, after in edits: text = replace_once(text, before, after)
    return text


def test_adapter(text):
    return replace_once(text,
        '                                "test_decoder_rebuilt_locations", "public-decoder"])',
        '                                "test_decoder_rebuilt_locations", "test_rebuilt_main_tools",\n'
        '                                "test_generate_rebuilt_rust", "test_rebuilt_production_rust",\n'
        '                                "test_source_snapshot", "public-decoder"])')


def run(out):
    report = {'status': 'running', 'started_at': extraction.now(), 'stages': [],
              **dict.fromkeys(('formal_policy_changed', 'formal_outputs_changed', 'proof_check_executed',
                              'compilers_rebuilt', 'old_project_cache_copied', 'clean_room_claimed',
                              'third_party_claimed', 'release_claimed'), False)}
    inputs = {ROOT / name for name in tools.SOURCES} | {Path(__file__).resolve(), tools.proof.POLICY,
              ROOT / 'proof/lean/decoder/public-rebuilt-policy.json', PROOF}
    report['inputs_before'] = {str(path): sha(path) for path in sorted(inputs)}
    extraction.write(out / 'report.json', report)
    env = None

    def execute(name, command, cwd=out):
        return extraction.stage(report, out, name, command, cwd, env)

    try:
        require(sha(tools.proof.POLICY) == OLD_POLICY and sha(PROOF) == PROOF_SHA, 'starting formal acceptance drift')
        old = read(tools.proof.POLICY)
        require(read(PROOF)['status'] == 'passed' and tools.proof.local_sources() == old['local_sources'],
                'formal source identity differs')
        state = snapshot.capture(ROOT)
        config = read(ROOT / 'artifacts/decoder-inputs/rebuilt-v2/payload/candidate/extraction.json')
        runtime = tools.locations.runtime(ROOT / 'artifacts/decoder-inputs/rebuilt-v2')
        prefix = tools.sail_install(ROOT)
        elan_home, lean_prefix = tools.lean_install(read(tools.locations.RUST_REPORT))
        binaries = {name: ROOT / 'artifacts/decoder-inputs/rebuilt-v2/payload/bin/base' / name
                    for name in ('charon', 'charon-driver', 'aeneas')}
        env = tools.environment(out, runtime, config, prefix, elan_home, lean_prefix,
                                ROOT / 'artifacts/decoder-inputs/rebuilt-v2/sources/base/aeneas', binaries)
        checkout = extraction.clone_source(out, state, execute)
        require(all(not (checkout / name).exists() for name in ('target', 'deps/sail-riscv/build',
                    'proof/lean/generated', 'proof/rocq/generated', 'sail-model/build')), 'old project outputs copied')
        report.update(checkout=str(checkout), original_snapshot_sha256=state['snapshot_sha256'],
                      original_policy_sha256=OLD_POLICY, original_proof_sha256=PROOF_SHA,
                      reused_runtime=runtime, private_lean_prefix=str(lean_prefix), sail_prefix=str(prefix))
        # These immutable reports retain original absolute private installation
        # paths. They are not fabricated records of installation in this clone.
        for path in (tools.locations.RUST_REPORT, tools.locations.OPAM_REPORT, ROOT / tools.SAIL_REPORT):
            relative = path.relative_to(ROOT)
            destination = checkout / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            require(sha(destination) == sha(path), 'runtime report copy differs')
        execute('install-rebuilt-inputs', ['python3', checkout / 'scripts/decoder_rebuilt_inputs.py',
                '--install', ARCHIVE, '--destination', checkout / 'artifacts/decoder-inputs/rebuilt-v2'], checkout)
        manifest = read(checkout / 'proof/lean/theorems/lake-manifest.json')
        report['lean_dependencies'] = {}
        for package in manifest['packages']:
            if package['type'] != 'git': continue
            relative = Path('proof/lean/theorems') / manifest['packagesDir'] / package['name']
            source, destination = ROOT / relative, checkout / relative
            require(snapshot.git(source, 'rev-parse', 'HEAD').decode().strip() == package['rev'] and
                    not snapshot.git(source, 'status', '--porcelain').strip(), 'Lean dependency source drift')
            destination.parent.mkdir(parents=True, exist_ok=True)
            execute('clone-lean-' + package['name'], ['git', 'clone', '--no-hardlinks', '--no-checkout', source, destination])
            execute('checkout-lean-' + package['name'], ['git', 'checkout', '--detach', package['rev']], destination)
            snapshot.independent(destination)
            report['lean_dependencies'][package['name']] = package['rev']
        # A mechanical, exact-anchor source transformation only in this new
        # candidate. Both before bytes and complete resulting snapshot are kept.
        for name, transform in [('scripts/check_proof.py', adapter), ('scripts/tests/test_proof_check.py', test_adapter)]:
            path = checkout / name
            require(sha(path) == state['repositories']['.']['files'][name]['sha256'], 'adapter source drift')
            path.write_text(transform(path.read_text()))
        candidate = copy.deepcopy(old)
        candidate.update(main_toolchain=tools.PROFILE, tool_binaries=tools.BINARIES.copy(),
                         translator_versions=tools.VERSIONS.copy())
        candidate['local_sources'] = json.loads(execute('candidate-source-inventory', ['python3', '-c',
            'import sys,json;sys.path.insert(0,"scripts");import check_proof;print(json.dumps(check_proof.local_sources()))'], checkout))
        allowed = {'local_sources', 'tool_binaries', 'translator_versions', 'main_toolchain'}
        require({k: v for k, v in candidate.items() if k not in allowed} ==
                {k: v for k, v in old.items() if k not in allowed}, 'candidate theorem/config/boundary drift')
        tools.proof.write_json(checkout / 'proof/lean/audit/step-policy.json', candidate)
        tools.policy_identity(candidate)
        updated = snapshot.capture(checkout)
        differences = [name for name in state['repositories']['.']['files']
                       if state['repositories']['.']['files'][name] != updated['repositories']['.']['files'].get(name)]
        require(set(differences) == {'scripts/check_proof.py', 'scripts/tests/test_proof_check.py',
                                    'proof/lean/audit/step-policy.json'}, 'unexpected candidate source changes')
        require(set(state['repositories']['.']['files']) == set(updated['repositories']['.']['files']),
                'candidate source addition/deletion')
        for repo in snapshot.REPOS[1:]:
            require(state['repositories'][repo] == updated['repositories'][repo], 'candidate submodule changes')
        extraction.write(out / 'candidate-source-snapshot.json', updated)
        for name in ['test_proof_check', *EXTRA_TESTS]:
            for mode in ([], ['-O']):
                execute(name + ('-optimized' if mode else ''), ['python3', *mode, 'scripts/tests/' + name + '.py'], checkout)
        build = checkout / 'deps/sail-riscv/build'
        execute('configure-rebuilt-sail', ['cmake', '-S', checkout / 'deps/sail-riscv', '-B', build,
            '-DCMAKE_BUILD_TYPE=RelWithDebInfo', '-DDOWNLOAD_GMP=TRUE', '-DSAIL_BIN:FILEPATH=' + str(prefix / 'bin/sail')], checkout)
        # Resolve through the candidate module, not the original helper's ROOT.
        for name in ('SAIL_CONFIG', 'SAIL_CONFIG_OVERRIDE', 'SAIL_BIN'):
            env.pop(name, None)  # Version-only preflight has no generated runtime configuration yet.
        result = execute('resolve-candidate-tools', ['python3', '-O', '-c',
            'import sys,json;sys.path.insert(0,"scripts");import check_proof as p;'
            'q=json.loads(p.POLICY.read_text());e,b,h,l=p.tools_and_environment(q);'
            's=p.source_evidence(q,b,h);keys=("PATH","ELAN_HOME","ELAN_TOOLCHAIN","AENEAS_HOME",'
            '"AENEAS","CHARON","SAIL_DIR","SAIL_PLUGIN_DIR","SAIL_BIN","RUSTUP_HOME","RUSTUP_TOOLCHAIN");'
            'print("REBUILT_MAIN_TOOLS_JSON="+json.dumps({"source":s,"lake":l,"environment":{k:e[k] for k in keys}}))'], checkout)
        resolved = parse_tools_log(result)
        # Do not publish the inherited environment; only intended tool choices.
        report['resolved_tools'] = {k: resolved[k] for k in ('source', 'lake')}
        report['candidate_environment'] = {k: resolved['environment'][k] for k in
            ('PATH', 'ELAN_HOME', 'ELAN_TOOLCHAIN', 'AENEAS_HOME', 'AENEAS', 'CHARON',
             'SAIL_DIR', 'SAIL_PLUGIN_DIR', 'SAIL_BIN', 'RUSTUP_HOME', 'RUSTUP_TOOLCHAIN')}
        require(snapshot.capture(ROOT) == state and snapshot.capture(checkout) == updated, 'source drift during preparation')
        report['inputs_after'] = {str(path): sha(path) for path in sorted(inputs)}
        require(report['inputs_before'] == report['inputs_after'], 'preparation driver/input drift')
        report.update(status='rebuilt_main_candidate_prepared_full_execution_pending',
                      candidate_snapshot_sha256=updated['snapshot_sha256'],
                      candidate_policy_sha256=sha(checkout / 'proof/lean/audit/step-policy.json'),
                      changed_candidate_sources=sorted(differences),
                      planned_main_stages=28, planned_tests=287, planned_public_stages=48)
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = extraction.now()
    extraction.write(out / 'report.json', report)
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    destination = Path(tempfile.mkdtemp(prefix='rebuilt-main-candidate-', dir=ROOT / 'artifacts/boundary-check'))
    print(destination, flush=True)
    sys.exit(run(destination))
