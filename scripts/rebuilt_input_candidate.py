#!/usr/bin/env python3
"""Materialize, archive and independently unpack rebuilt decoder candidate inputs.

This is NOT a replacement for the approved public-v1 bundle. Exact files are
selected from hash-pinned completed reports. The separately hashed catalogue
is the verifier's trust input, not the archive's own manifest. Qualification
report bytes are included, but their entire historical log/cache closure is not.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import decoder_input_bundle as bundle
from probes import probe_rebuilt_public_kernel as kernel

require, sha, read = kernel.require, kernel.sha, kernel.read
BASE = ROOT / 'artifacts/boundary-check'
QUALIFICATIONS = {
    'public_clean': ('rebuilt-public-kernel-kahdzauc', 'e94b2e9f59e41fffb2e4d2c525cef42e6bc7a786393e842879e053f89d01bf08', 'rebuilt_public_kernel_checked_admission_pending'),
    'borrow': ('rebuilt-borrows-_rl7vzss', '624413e13a949f9b3a56442e097dcff9bd5853e5bf193c3828308918a2e62120', 'rebuilt_borrow_regressions_checked_admission_pending'),
    'fnptr': ('rebuilt-fnptr-_j1r1xm7', '1ad2d7355f6f517e1f8d1c05b5373e59a5b659fec33ba336c8f617032f061315', 'rebuilt_fnptr_regressions_checked_admission_pending'),
    'charon_ui': ('rebuilt-charon-ui-jtet5h5k', '325e6f340bd365dcea0992309d38a6635b264a198ce70afd8999c9cd8b563e00', 'rebuilt_charon_ui_differential_completed_qualification_pending'),
    'charon_diagnostics': ('rebuilt-charon-diagnostics-9mde362w', '066d19a38522d3cef48d33be73c6c74dbb6660207403ea6f2f50e75dd3ec63f4', 'rebuilt_diagnostics_classified_tests_still_failed_admission_pending'),
    'guard_equivalence': ('rebuilt-guard-qyes6caj', '7d60a0d39587f6d5f5af310ef3ed02ea8acba6778cb58720ec5a35c8856093ce', 'rebuilt_guard_regression_checked_admission_pending'),
    'loop_equivalence': ('rebuilt-loop-4psnamoz', 'd95e3a00022699e8a773b1aa11458ff7cd34259c066c18206dab4e59d35ec1f2', 'rebuilt_loop_regression_checked_admission_pending'),
}
SUPPORT = {
    'joint_extraction': ('rebuilt-extraction-chain-18z20fdd', 'db0ddb324274e9ab1fa69650eed19ea661ef5b4f68face18aa72113c96414c9e', 'rebuilt_tools_three_models_match_qualification_pending'),
    'lower_extraction': ('rebuilt-lower-models-tt2j7xeu', '5009ba00993188373dd2d502024486884aa8f67f5982495b64516d98e71d0f35', 'lower_models_reextracted_identity_review_required'),
    'map_equivalence': ('lower-map-kernel-0v7r0ook', '57cb243c8742513062547a8983b6cafeca689907250146e78f46cbea3d8101cd', 'lower_map_equivalence_and_raw_kernel_checked_admission_pending'),
    'lower_negatives': ('lower-original-negatives-qridxngh', '1b045c976d4d8de26fbb26443a1d74eb3f7bab320b7a7d2a2939da1dc9e3ad9e', 'original_lower_negatives_and_runtime_completed_admission_pending'),
    'sail_cpp': ('rebuilt-sail-cpp-p7x1idhj', '197438f259cba13b82c4c9cf9a636872050f428b5b8f6663021b561a40d65542', 'rebuilt_sail_cpp_compiled_config_checked_admission_pending'),
    'sail_runtime': ('rebuilt-sail-runtime-6t_ouoxe', '5f24f40a2b034c40193a917e052171bf70e5732eb6e2a223af55a5e3a80465ed', 'rebuilt_sail_runtime_mutations_replays_checked_admission_pending'),
}
BOUNDARIES = {
    'tool_adopted': False, 'policy_changed': False, 'kernel_executed_by_packager': False,
    'fresh_extraction_executed_by_packager': False, 'full_qualification_reexecuted_by_packager': False,
    'entire_historical_evidence_closure_included': False, 'old_report_paths_rewritten': False,
    'upstream_visitors_constraint_satisfied': False, 'full_upstream_suite_passed': False,
    'clean_room_claimed': False, 'release_claimed': False,
}


def record(pin):
    directory, digest, status = pin
    path = BASE / directory / 'report.json'
    value = kernel.pinned(path, digest)
    require(value['status'] == status, 'candidate report disposition differs: ' + directory)
    return path, value


def selection(components):
    sources, reports = {}, {}
    def add(name, path, digest):
        require(name not in sources and Path(path).is_file() and not Path(path).is_symlink() and sha(Path(path)) == digest,
                'duplicate/missing/drifted candidate input: ' + name)
        sources[name] = {'source': str(path), 'sha256': digest}
    for group, pins in (('qualification', QUALIFICATIONS), ('evidence', SUPPORT)):
        for label, pin in pins.items():
            path, value = record(pin); reports[label] = value
            add(group + '/' + label + '.json', path, pin[1])
    for side in ('base', 'public'):
        for name, info in components['tools'][side].items():
            if name in ('aeneas', 'charon', 'charon-driver'):
                add('bin/' + ('' if side == 'public' else 'base/') + name, Path(info['path']), info['sha256'])
    low = reports['lower_extraction']; joint = reports['joint_extraction']
    add('bin/join/aeneas', Path(low['join_binary']['path']), low['join_binary']['sha256'])
    require(kernel.lower.check_join_source(BASE / 'rebuilt-lower-models-tt2j7xeu/aeneas-source') == low['join_source_before'],
            'join source differs from extraction input')
    for stem, row in low['models'].items():
        add('models/' + stem + '.lean', Path(row['model']), row['identity']['raw_sha256'])
        add('llbc/' + stem + '.llbc', Path(row['llbc']), row['llbc_sha256'])
    for label, row in joint['models'].items():
        add('models/' + Path(row['model']).name, Path(row['model']), row['raw_sha256'])
        add('llbc/' + Path(row['llbc']).name, Path(row['llbc']), row['llbc_sha256'])
    original = Path(kernel.chain.PUBLIC)
    approved = bundle.verify_payload(original)
    for name in ('patches/aeneas.patch', 'patches/charon.patch', 'harness/lib.rs', 'harness/Cargo.lock',
                 'sources/aeneas.bundle', 'sources/charon.bundle'):
        add(name, original / name, approved['files'][name]['sha256'])
    add('patches/aeneas-join.patch', kernel.lower.PATCH, kernel.lower.PATCH_SHA)
    for name, digest in components['libraries'].items():
        add('sysroot/' + str(kernel.chain.MIR.LIB_SUFFIX / name), Path(components['sysroot']) / kernel.chain.MIR.LIB_SUFFIX / name, digest)
    add('qualification/sysroot.json', kernel.chain.previous.MIR_REPORT, kernel.chain.previous.MIR_SHA)
    # Preserve the old policy/config as labelled reference inputs, never silently
    # turn an adopted-v1 file into the new candidate configuration.
    for path in (kernel.gate.POLICY, kernel.public_gate.POLICY, kernel.lower.raw.POLICY,
                 kernel.lower.fields.POLICY, kernel.chain.CONFIG):
        add('reference/' + str(path.relative_to(ROOT)), path, sha(path))
    config = read(kernel.chain.CONFIG)
    new_config = dict(config, status='candidate-rv64-add-public-rebuilt-v2',
                      aeneas_binary_sha256=components['tools']['public']['aeneas']['sha256'],
                      charon_binary_sha256=components['tools']['public']['charon']['sha256'],
                      charon_driver_sha256=components['tools']['public']['charon-driver']['sha256'],
                      llbc_sha256=joint['models']['public']['llbc_sha256'],
                      archived_inputs='../llbc/OuterClosedDepsV3.llbc', outer_root_source='../harness/lib.rs',
                      aeneas_patch='../patches/aeneas.patch', charon_patch='../patches/charon.patch',
                      charon_common=['--preset=aeneas', '--sysroot', '<candidate-payload>/sysroot'],
                      full_public_decode_root_status='candidate body extracted and kernel checked; formal tool admission pending')
    allowed = {'status', 'aeneas_binary_sha256', 'charon_binary_sha256', 'charon_driver_sha256', 'llbc_sha256',
               'archived_inputs', 'outer_root_source', 'aeneas_patch', 'charon_patch', 'charon_common',
               'full_public_decode_root_status'}
    require({k for k in config if config[k] != new_config[k]} == allowed, 'unexpected candidate configuration change')
    return sources, new_config, approved['source_commits']


def verify(payload, catalogue):
    require(catalogue['kind'] == 'rebuilt-decoder-candidate-catalogue' and catalogue['boundaries'] == BOUNDARIES,
            'catalogue cannot grant adoption')
    require(all(type(v) is bool for v in catalogue['boundaries'].values()), 'boundary flags must be booleans')
    manifest = read(payload / 'package.json')
    expected = {'schema_version': 1, 'kind': 'rebuilt-decoder-candidate-inputs',
                'boundaries': BOUNDARIES, 'files': catalogue['files'], 'source_commits': catalogue['source_commits']}
    require(json.dumps(manifest, sort_keys=True) == json.dumps(expected, sort_keys=True),
            'candidate manifest differs from external catalogue')
    bundle.check_files(payload, {k: v['sha256'] for k, v in catalogue['files'].items()}, catalogue['files'])
    require(all((payload / name).stat().st_nlink == 1 for name in [*catalogue['files'], 'package.json']),
            'candidate input is hardlinked')
    for name, commit in catalogue['source_commits'].items():
        require(bundle.git(payload, 'bundle', 'list-heads', payload / 'sources' / (name + '.bundle')).decode().splitlines() ==
                [commit + ' HEAD'], 'source bundle revision drift')
    return {'files': len(catalogue['files']), 'bytes': sum(v['bytes'] for v in catalogue['files'].values())}


def unpack(archive, digest, destination, catalogue):
    require(len(digest) == 64 and all(c in '0123456789abcdef' for c in digest) and sha(archive) == digest,
            'explicit archive identity required')
    with tarfile.open(archive, 'r:gz') as stream:
        members = stream.getmembers(); bundle.check_members(members)
        require({m.name for m in members} == set(catalogue['files']) | {'package.json'}, 'archive file inventory differs')
        destination.mkdir(parents=True, exist_ok=False)
        for member in members:
            path = destination / member.name; path.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, path.open('xb') as target:
                shutil.copyfileobj(source, target)
            path.chmod(member.mode)
    return verify(destination, catalogue)


def run(out):
    result = {'status': 'running', 'started_at': kernel.chain.now(), **BOUNDARIES}
    try:
        components = kernel.chain.verify_components()
        sources, config, commits = selection(components)
        paths = {Path(__file__), *(Path(v['source']) for v in sources.values())}
        paths.update(Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                     and Path(m.__file__).resolve().is_relative_to(ROOT / 'scripts'))
        result['inputs_before'] = {str(p): sha(p) for p in sorted(paths)}
        payload = out / 'payload'; payload.mkdir()
        for name, info in sources.items():
            path = payload / name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(info['source'], path); path.chmod(0o755 if name.startswith('bin/') else 0o644)
            require(sha(path) == info['sha256'], 'copy changed candidate input')
        (payload / 'candidate').mkdir()
        kernel.gate.write_json(payload / 'candidate/extraction.json', config)
        (payload / 'candidate/extraction.json').chmod(0o644)
        files = {name: {'sha256': sha(payload / name), 'bytes': (payload / name).stat().st_size,
                         'mode': (payload / name).stat().st_mode & 0o777}
                 for name in sorted(bundle.regular_files(payload))}
        catalogue = {'kind': 'rebuilt-decoder-candidate-catalogue', 'boundaries': BOUNDARIES,
                     'source_commits': commits, 'files': files, 'provenance': sources}
        kernel.gate.write_json(out / 'catalogue.json', catalogue)
        kernel.gate.write_json(payload / 'package.json', {'schema_version': 1,
                               'kind': 'rebuilt-decoder-candidate-inputs', 'boundaries': BOUNDARIES,
                               'files': files, 'source_commits': commits})
        (payload / 'package.json').chmod(0o644)
        result['payload'] = verify(payload, catalogue)
        archive = out / 'rebuilt-decoder-candidate.tar.gz'
        with tarfile.open(archive, 'w:gz', compresslevel=3) as stream:
            for name in sorted(bundle.regular_files(payload)):
                path = payload / name; info = stream.gettarinfo(str(path), arcname=name)
                info.uid = info.gid = info.mtime = 0; info.uname = info.gname = ''
                with path.open('rb') as source:
                    stream.addfile(info, source)
        result.update(archive_sha256=sha(archive), catalogue_sha256=sha(out / 'catalogue.json'),
                      manifest_sha256=sha(payload / 'package.json'))
        # Exercise actual tar validation/unpacking in another absent directory.
        result['unpacked'] = unpack(archive, result['archive_sha256'], out / 'unpacked/payload', catalogue)
        require(result['unpacked'] == result['payload'], 'unpacked inventory differs')
        require(kernel.chain.verify_components() == components, 'tool component drift during packaging')
        result['inputs_after'] = {str(p): sha(p) for p in sorted(paths)}
        require(result['inputs_before'] == result['inputs_after'], 'source/report/policy drift during packaging')
        require(sha(archive) == result['archive_sha256'] and sha(out / 'catalogue.json') == result['catalogue_sha256'],
                'archive/catalogue changed')
        result['status'] = 'rebuilt_candidate_inputs_packaged_unpacked_admission_pending'; code = 2
    except (Exception, KeyboardInterrupt) as error:
        result.update(status='failed', error=str(error), error_type=type(error).__name__); code = 1
    result['finished_at'] = kernel.chain.now(); kernel.gate.write_json(out / 'report.json', result)
    print(json.dumps({'status': result['status'], 'report': str(out / 'report.json')}), flush=True)
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-payload', type=Path)
    parser.add_argument('--catalogue', type=Path)
    parser.add_argument('--catalogue-sha256')
    args = parser.parse_args()
    if args.verify_payload:
        require(args.catalogue is not None and args.catalogue_sha256 is not None and
                len(args.catalogue_sha256) == 64 and all(c in '0123456789abcdef' for c in args.catalogue_sha256)
                and sha(args.catalogue) == args.catalogue_sha256, 'externally pinned catalogue required')
        print(json.dumps(verify(args.verify_payload.resolve(), read(args.catalogue))))
    else:
        require(args.catalogue is None and args.catalogue_sha256 is None, 'catalogue options need --verify-payload')
        out = Path(tempfile.mkdtemp(prefix='rebuilt-input-candidate-', dir=BASE))
        print(out, flush=True)
        sys.exit(run(out))
