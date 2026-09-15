#!/usr/bin/env python3
"""Read-only main translator identity preflight; never adopts or generates.

Exercises the real source-evidence checker with the old policy (must reject)
and an in-memory candidate containing only four binary hashes and one version
change. Runtime installation checks are additional, not a clean-room claim.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_proof as proof
import decoder_rebuilt_locations as locations
from probes import probe_rebuilt_sail_cpp as sail

require, sha, read = locations.require, locations.sha, locations.read
OLD_POLICY = 'ca6e062b62c448e428fb016a0442d1b271872c26539573077d494b84d074a79f'
STAGED = ROOT / 'artifacts/boundary-check/rebuilt-production-rust-efnnej7p/report.json'
STAGED_SHA = '3c7ff79877367c3854bcf98c6c04fc3bda91c51351c53a8e2c65470a47773cee'


def candidate_policy(old, hashes, version):
    require(set(hashes) == {'sail', 'aeneas', 'charon', 'charon-driver'}, 'translator inventory')
    require(all(hashes[k] != old['tool_binaries'][k] for k in hashes), 'not four rebuilt translators')
    require(version == 'aeneas 379890b5', 'unexpected rebuilt Aeneas version')
    result = copy.deepcopy(old)
    result['tool_binaries'] = hashes.copy()
    result['translator_versions']['aeneas'] = version
    return result


def run(out):
    report = {'status': 'running', 'started_at': sail.model.now(),
              **dict.fromkeys(('policy_changed', 'generated_outputs_changed', 'kernel_executed',
                              'main_tools_adopted', 'clean_room_claimed', 'release_claimed'), False)}
    try:
        require(sha(proof.POLICY) == OLD_POLICY and sha(STAGED) == STAGED_SHA, 'starting evidence drift')
        staged = read(STAGED)
        require(staged['status'] == 'production_rust_staged_identity_verified_main_adoption_pending' and
                staged['inputs_before'] == staged['inputs_after'], 'staged extraction incomplete')
        for row in staged['stages']:
            require(type(row['exit_code']) is int and row['exit_code'] == 0 and
                    sha(STAGED.parent / row['log']) == row['log_sha256'], 'staged log drift')
        require(sha(STAGED.parent / 'generated/CkbVmProduction.lean') == staged['model_identity']['sha256'],
                'staged model drift')
        directory = ROOT / 'artifacts/decoder-inputs/rebuilt-v2'
        installed = locations.load(directory)
        runtime = locations.runtime(directory)
        require(sha(sail.model.INSTALL_REPORT) == sail.model.INSTALL_SHA, 'Sail installation report drift')
        sail_report = read(sail.model.INSTALL_REPORT)
        prefix = sail.check_install(sail_report)
        payload = Path(installed['payload'])
        home = directory / 'sources/base/aeneas'
        binaries = {name: payload / 'bin/base' / name for name in ('charon', 'charon-driver', 'aeneas')}
        binaries['sail'] = prefix / 'bin/sail'
        old = read(proof.POLICY)
        files = {Path(__file__).resolve(), proof.POLICY, locations.admitted.POLICY,
                 locations.admitted.CATALOGUE, STAGED, sail.model.INSTALL_REPORT}
        files.update(Path(m.__file__).resolve() for m in list(sys.modules.values())
                     if getattr(m, '__file__', None) and
                     Path(m.__file__).resolve().is_relative_to(ROOT / 'scripts'))
        report['inputs_before'] = {str(p): sha(p) for p in sorted(files)}
        report['original_generated'] = proof.generated_evidence(old)
        try:
            proof.source_evidence(old, binaries, home)
        except RuntimeError as error:
            require(str(error).startswith('translator binaries differs from reviewed policy'),
                    'old checker rejected for an unrelated reason')
            report['old_policy_rejection'] = str(error)
        else:
            raise RuntimeError('old policy unexpectedly accepted rebuilt translators')
        hashes = {k: sha(v) for k, v in binaries.items()}
        candidate = candidate_policy(old, hashes, 'aeneas 379890b5')
        report['candidate_source_evidence'] = proof.source_evidence(candidate, binaries, home)
        require(proof.local_sources() == old['local_sources'], 'formal source drift')
        require(proof.generated_evidence(old) == report['original_generated'], 'formal model drift')
        require(locations.load(directory) == installed and locations.runtime(directory) == runtime,
                'rebuilt payload/runtime drift')
        require(sail.check_install(sail_report) == prefix, 'Sail installation drift')
        report['inputs_after'] = {str(p): sha(p) for p in sorted(files)}
        require(report['inputs_before'] == report['inputs_after'], 'preflight input drift')
        report.update(status='main_rebuilt_identity_preflight_passed_integration_pending',
                      runtime=runtime, installed=installed, candidate_tool_binaries=hashes,
                      candidate_policy_sha256=proof.digest(proof.canonical(candidate)),
                      remaining=['generator integration and provenance', 'explicit private Lean selection',
                                 'Sail CMake/compiler/plugin integration', 'complete fresh proof-check',
                                 'formal policy review and adoption', 'complete Week6 release obligations'])
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='failed', error=str(error), error_type=type(error).__name__)
        code = 1
    report['finished_at'] = sail.model.now()
    proof.write_json(out / 'report.json', report)
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    directory = Path(tempfile.mkdtemp(prefix='main-rebuilt-preflight-', dir=ROOT / 'artifacts/boundary-check'))
    print(directory, flush=True)
    sys.exit(run(directory))
