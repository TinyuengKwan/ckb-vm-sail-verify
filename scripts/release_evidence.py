"""Read-only revalidation of existing local evidence, never a fresh execution claim."""
from pathlib import Path
import re

import check_proof as proof
import public_decoder_acceptance as public
import public_decoder_gate as public_gate
import release_runtime_evidence as runtime
import rocq_spike as rocq
from probes import probe_release_runtime as producer

require, same, read, sha = runtime.require, runtime.same, runtime.read_json, runtime.sha
ROOT = proof.ROOT
TEST_COUNTS = dict(zip([
    'test_lean_imports', 'test_lean_step', 'test_proof_check', 'test_ckb_source_baseline',
    'test_lean_clean', 'test_decoder_public_source', 'test_decoder_public_clean',
    'test_public_decoder_acceptance', 'test_public_decoder_gate', 'test_decoder_harness',
    'test_decoder_model_identity', 'test_decoder_iterator_identity',
    'test_decoder_input_bundle', 'test_decoder_input_locations',
    'test_sail_model_transaction', 'test_decoder_rebuilt_inputs', 'test_decoder_rebuilt_locations'],
    [19, 18, 18, 12, 6, 10, 7, 26, 14, 10, 9, 10, 21, 7, 21, 15, 13]))
LEAN_STAGES = ['sail-config', 'environment', 'generate-rust', 'generate-sail',
               'kernel-step', 'theorem-audit', *TEST_COUNTS, 'public-decoder']
REBUILT_TEST_COUNTS = {'test_rebuilt_main_tools': 12, 'test_generate_rebuilt_rust': 10,
                       'test_rebuilt_production_rust': 12, 'test_source_snapshot': 17}
ROCQ_STAGES = ['packages', 'version', 'rust-generate', 'rust-primitives', 'rust-model',
               'rust-repro', 'sail-support', 'sail-types', 'sail-model', 'sail-repro']


def lean_inventory(policy):
    """The rebuilt profile adds mandatory checks; it cannot reduce the old gate."""
    counts, stages = dict(TEST_COUNTS), list(LEAN_STAGES)
    if 'main_toolchain' not in policy:
        return counts, stages
    require(policy['main_toolchain'] == 'rebuilt-main-v1', 'unknown main toolchain inventory')
    require(stages[-1] == 'public-decoder' and not (counts.keys() & REBUILT_TEST_COUNTS.keys()),
            'main inventory already changed; review required')
    counts.update(REBUILT_TEST_COUNTS)
    return counts, [*stages[:-1], *REBUILT_TEST_COUNTS, 'public-decoder']


def member(directory, name):
    """Evidence references cannot escape their root or traverse symlinks."""
    require(isinstance(name, str) and name and not Path(name).is_absolute() and
            all(part not in ('', '.', '..') for part in name.split('/')), 'unsafe evidence path')
    directory = Path(directory).resolve()
    path = directory
    for part in name.split('/'):
        path = path / part
        require(not path.is_symlink(), 'symlink evidence path')
    require(path.is_file() and path.resolve().is_relative_to(directory), 'missing evidence file: ' + name)
    return path


def linked(directory, name, digest):
    require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'invalid SHA-256')
    path = member(directory, name)
    require(sha(path) == digest, 'evidence hash differs: ' + name)
    return path


def current_formal():
    policy = read(proof.POLICY)
    _, binaries, home, _ = proof.tools_and_environment(policy)
    return policy, proof.source_evidence(policy, binaries, home), proof.generated_evidence(policy)


def check_runtime(path):
    path = Path(path)
    out, report = path.parent, read(path)
    env, compiler = producer.environment()
    expected = producer.observed_environment(env)
    require(same(report['schema_version'], 1) and
            report['status'] == 'local_runtime_and_relocated_replay_passed', 'runtime probe incomplete')
    for key in ['release_claimed', 'clean_room_claimed', 'third_party_claimed', 'sail_emulator_rebuilt']:
        require(report[key] is False, 'runtime assurance changed: ' + key)
    require(report['cargo_target_initially_absent'] is True, 'runtime Cargo target reused')
    require(same(report['environment_before'], expected) and same(report['environment_after'], expected),
            'runtime environment differs from current observation')
    require(report['inputs_before'] == report['inputs_after'] == producer.inputs(compiler),
            'runtime sources/tools/policy changed')
    binary = linked(out, 'cargo-target/debug/ckb-vm-sail-diff', report['binary_sha256'])
    corpus = member(out, 'corpus-mutations.stdout')
    result = runtime.validate(corpus, out / 'original', expected)
    require(same(result, report['runtime']) and same(result, runtime.validate(corpus, out / 'relocated', expected)),
            'runtime originals/copies no longer agree')
    ids = [row['id'] for row in read(corpus)['results']]
    names = ['verify-environment', 'build-cli', 'corpus-mutations'] + ['replay-' + name for name in ids]
    require([row['name'] for row in report['stages']] == names, 'runtime stage inventory')
    common = [str(binary), '--json', '--sail-bin', producer.SAIL_BIN, '--sail-config', producer.CONFIG]
    commands = [['bash', 'scripts/verify_environment.sh'],
                ['cargo', 'build', '--locked', '-p', 'ckb-vm-sail-diff'],
                [*common, '--corpus', '--mutate', '--artifact-dir', str(out / 'original')]] + [
                [*common, '--replay', str(out / 'relocated' / (name + '.json')),
                 '--artifact-dir', str(out / 'replays' / name)] for name in ids]
    for stage, command in zip(report['stages'], commands):
        require(same(stage['exit_code'], 0) and stage['argv'] == command, 'runtime stage exit/command')
        require(set(stage['logs']) == {stage['name'] + '.' + ext for ext in ['stdout', 'stderr']},
                'runtime stage log inventory')
        for name, digest in stage['logs'].items(): linked(out, name, digest)
    require([r['case_id'] for r in report['replays']] == ids, 'replay inventory')
    for row in report['replays']:
        name = row['case_id']
        require(row['report'] == 'replay-' + name + '.stdout' and
                row['artifact'] == f'replays/{name}/{name}.json', 'replay references changed')
        replay = linked(out, row['report'], row['report_sha256'])
        artifact = linked(out, row['artifact'], row['artifact_sha256'])
        original = linked(out, 'relocated/' + name + '.json', row['input_sha256'])
        runtime.check_replay(read(replay), read(artifact), read(original), expected)
    return {'scope': 'existing_local_runtime_and_relocated_replay', 'cases': result['cases'],
            'mutations': result['mutations'], 'replays': len(ids), 'fresh_execution_claimed': False}


def check_lean(path):
    path = Path(path)
    out, report = path.parent, read(path)
    policy, source, generated = current_formal()
    counts, stages = lean_inventory(policy)
    require(same(report['schema_version'], 1) and report['status'] == 'passed' and
            report['assurance'] == 'conditional' and report['coverage'] == 'runtime-only' and
            report['release_audit'] is False, 'wrong Lean status/assurance')
    require(report['policy_sha256'] == sha(proof.POLICY), 'stale Lean policy')
    for key in ['theorem', 'outstanding_contracts', 'configuration']:
        require(same(report[key], policy[key]), 'Lean boundary changed: ' + key)
    require(report['source'] == source and report['generated'] == generated and
            report['ckb_source_baseline'] == source['ckb_source_baseline'], 'Lean source/model identity')
    require([row['name'] for row in report['stages']] == stages, 'Lean stage inventory')
    logs = {}
    for row in report['stages']:
        name = row['name']
        require(row['status'] == 'passed' and same(row['exit_code'], 0) and row['log'] == name + '.log',
                'Lean stage failed or wrong log')
        logs[name] = linked(out, row['log'], row['sha256']).read_text()
        if name in counts:
            require(re.findall(r'(?m)^Ran (\d+) tests? in ', logs[name]) == [str(counts[name])] and
                    re.search(r'(?m)^OK\s*\Z', logs[name]), 'missing/changed test completion: ' + name)
    audit = read(member(out, 'lean-audit.json'))
    require(audit == proof.parse_audit(logs['theorem-audit']), 'Lean audit/log disagree')
    proof.check_audit(audit, policy)
    require(report['boundary_sha256'] == proof.boundary_hashes(audit) and
            report['axiom_counts'] == {k: len(v) for k, v in policy['axioms'].items()} and
            report['witness_axiom_counts'] == {k: len(v) for k, v in audit['witness_axioms'].items()},
            'Lean audit counters/boundaries')
    public_policy = read(public_gate.POLICY)
    public_gate.check_policy(public_policy)
    recorded = report['public_decoder']
    public_path = Path(recorded['report'])
    require(public_path.is_absolute() and public_path.is_relative_to(ROOT / 'artifacts/boundary-check'),
            'public report outside evidence tree')
    public_path = linked(ROOT, str(public_path.relative_to(ROOT)), recorded['report_sha256'])
    require([line[8:] for line in logs['public-decoder'].splitlines() if line.startswith('Report: ')] ==
            [str(public_path)], 'main/public execution link')
    actual = public.validate(public_path)
    actual.update(main_gate_adopted=True, public_policy_sha256=sha(public_gate.POLICY),
                  configuration=public_policy['configuration'], limitations=public_policy['limitations'],
                  tool_adoption_claimed=True)
    require(actual == recorded and report['clean_build'] == actual['clean_build'], 'public/clean acceptance differs')
    return {'scope': 'existing_conditional_Lean_evidence', 'main_stages': len(stages),
            'tests': sum(counts.values()), 'public_theorems': actual['public_theorem_count'],
            'fresh_kernel_run_claimed': False}


def check_rocq(path):
    path = Path(path)
    out, report = path.parent, read(path)
    require(same(report['schema_version'], 1) and report['status'] == 'passed' and
            report['verdict'] == 'NO-GO' and report['extra_proof_coverage'] is False and
            report['clean_room_claimed'] is False, 'wrong Rocq status/coverage')
    require(report['policy_sha256'] == sha(proof.POLICY), 'stale Rocq policy; rerun spike')
    require(Path(report['directory']) == out, 'Rocq directory differs')
    policy, source, generated = current_formal()
    require(report['source'] == source and report['generated'] == generated, 'Rocq source/model identity')
    context = rocq.rebuilt_context
    rebuilt = context.selected(policy)
    stages = ['sail-generate', *ROCQ_STAGES] if rebuilt else ROCQ_STAGES
    require(report['input_sha256'] == report['input_sha256_after'] == rocq.inputs(ROOT, rebuilt=rebuilt), 'Rocq input drift')
    require([row['name'] for row in report['stages']] == stages, 'Rocq stage inventory')
    logs = {}
    rejects = {'rust-model': 'rust', 'sail-model': 'sail', 'sail-repro': 'sail'}
    for row in report['stages']:
        name = row['name']
        require(same(row['exit_code'], 1 if name in rejects else 0) and
                row['status'] == ('expected_rejection' if name in rejects else 'passed') and
                row['log'] == name + '.log', 'unexpected Rocq exit/status')
        logs[name] = linked(out, row['log'], row['log_sha256']).read_text()
        if name in rejects: rocq.check_failure(rejects[name], row['exit_code'], logs[name])
        else: require(not rocq.INFRA_FAILURE.search(logs[name]), 'Rocq infrastructure failure')
    require(rocq.check_packages(logs['packages']) == report['packages'], 'Rocq package record')
    require(logs['version'].strip() == report['rocq_version'] ==
            'The Rocq Prover, version 9.1.1\ncompiled with OCaml 5.2.1', 'Rocq version')
    require('Expands to: Inductive Corelib.Init.Datatypes.result' in logs['rust-repro'], 'Rust repro absent')
    require(set(report['model_sha256']) == {'rust/Primitives.v', 'rust/CkbVmProduction.v',
            'rust/result_shadowing.v', 'sail/rv64d.v', 'sail/rv64d_types.v',
            'sail/riscv_extras.v', 'sail/missing_e_div.v'}, 'Rocq model inventory')
    for name, digest in report['model_sha256'].items(): linked(out, name, digest)
    for name, source_path in {
        'rust/result_shadowing.v': 'proof/rocq/spike/result_shadowing.v',
        'sail/rv64d.v': 'proof/rocq/generated/sail/rv64d.v',
        'sail/rv64d_types.v': 'proof/rocq/generated/sail/rv64d_types.v',
        'sail/riscv_extras.v': 'deps/sail-riscv/handwritten_support/riscv_extras.v',
        'sail/missing_e_div.v': 'proof/rocq/spike/missing_e_div.v',
    }.items():
        require(report['model_sha256'][name] == sha(ROOT / source_path), 'Rocq copied model/repro differs')
    if rebuilt:
        require(report['execution_profile'] == context.PROFILE, 'Rocq execution profile differs')
        env, binaries, home, _ = proof.tools_and_environment(policy)
        installation, _, record = context.resolve(ROOT, env, home)
        require(report['tool_context'] == record and report['opam_switch'] == installation['switch'] and
                report['packages'] == installation['packages'], 'Rocq tool context differs')
        context.check_commands(report, context.commands(ROOT, out, env, binaries, installation))
        require(context.generation_evidence(ROOT, out, report) == report['sail_generation'], 'Rocq generation provenance differs')
        require(report['pre_generation_input_sha256'] == rocq.inputs(ROOT, include_sail=False, rebuilt=True),
                'Rocq pre-generation sources differ')
        primitive = home / 'backends/coq/Primitives.v'
        require(report['rust_primitives']['source'] == str(primitive) and
                report['rust_primitives']['sha256'] == sha(primitive) == sha(out / 'rust/Primitives.v') == context.PRIMITIVES_SHA and
                report['rust_primitives']['installation'] in ('translator_emitted_exact', 'copied_from_verified_source'),
                'Rocq primitives source/copy provenance differs')
    return {'scope': 'existing_specific_Rocq_NO_GO', 'stages': len(stages),
            'extra_proof_coverage': False, 'input_regeneration': report['input_regeneration']}
