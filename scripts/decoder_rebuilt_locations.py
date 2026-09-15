"""Explicit v2 proof inputs and reviewed lower-model policy; no v1 fallback."""
import json
import copy
import os
from pathlib import Path

import decoder_rebuilt_inputs as admitted
import decoder_input_locations as legacy
import check_raw_add as raw

ROOT = admitted.ROOT
RAW_POLICY = ROOT / 'proof/lean/decoder/raw-rebuilt-policy.json'
RUST_REPORT = ROOT / 'artifacts/boundary-check/isolated-rust-lean-ad7o1fsn/report.json'
OPAM_REPORT = ROOT / 'artifacts/boundary-check/aeneas-opam-finalize-mj9dgb4h/report.json'
require, sha, read, load = admitted.require, admitted.sha, admitted.read, admitted.load
# These two bodies were kernel-proved extensionally equal to the archived
# definitions, for all Result outcomes. No other raw body/type/axiom may vary.
MAP_DEFINITIONS = {
    'RawDecodeFactory.core.option.Option.map': 'a74085a72240faa6c09145a9902e139a18a39c94d1491b5eea2a0b9ee698b8c3',
    'decoder_shared_closure.core.option.Option.map': '168e09602a0a048c47577d912bb4482b7ef357577b46982c1fb0ec5b150e5f3f',
}
MAP_RAW_AUDIT_SHA = '2d400d57ef6fc84ef77d4ff32a88b82bd49051cfc2939ac63a32a261f67dda9d'
MAP_EQUIVALENCE_AUDIT_SHA = '733245c1e5ae5ac8034de1fac53b65f33e36a9c543d9bab7816122275f8549f3'


def configuration(directory):
    installed = load(directory)
    return installed, read(Path(installed['payload']) / 'candidate/extraction.json')


def check_extraction(fresh, directory, name='OuterClosedDepsV3.llbc'):
    require(name in {'OuterClosedDepsV3.llbc', 'FnPtrFullMir.llbc'}, 'unknown extraction root')
    payload = Path(load(directory)['payload'])
    return legacy._compare_metadata(read(payload / 'llbc' / name), fresh, payload / 'sysroot')


def lower_policy(directory):
    payload = Path(load(directory)['payload'])
    require(sha(raw.POLICY) == '407909ee4584c3d1a45dcbf123fa2019d70b2eaac4f22b962caf3dea37596951', 'legacy raw reference drift')
    old, new = read(raw.POLICY), read(RAW_POLICY)
    allowed = {'generated_normalized_sha256', 'regression_model_normalized_sha256',
               'tool_binary_path', 'tool_binary_sha256', 'rebuilt_admission', 'audit'}
    require({k: v for k, v in old.items() if k not in allowed} ==
            {k: v for k, v in new.items() if k not in allowed}, 'raw theorem/type/body/axiom policy changed')
    expected_audit = copy.deepcopy(old['audit'])
    require(set(MAP_DEFINITIONS) <= set(expected_audit['definitions']), 'reviewed map definition absent')
    expected_audit['definitions'].update(MAP_DEFINITIONS)
    require(new['audit'] == expected_audit, 'raw theorem/type/body/axiom policy changed')
    policy, catalogue = admitted.load_policy()
    map_report_path = payload / 'evidence/map_equivalence.json'
    require(sha(map_report_path) == catalogue['files']['evidence/map_equivalence.json']['sha256'],
            'map equivalence report identity differs')
    map_report = read(map_report_path)
    require(map_report['status'] == 'lower_map_equivalence_and_raw_kernel_checked_admission_pending' and
            map_report['raw_audit_sha256'] == MAP_RAW_AUDIT_SHA and
            map_report['map_audit_sha256'] == MAP_EQUIVALENCE_AUDIT_SHA and
            map_report['changed_raw_definitions'] == sorted(MAP_DEFINITIONS), 'reviewed map audit differs')
    require(new['rebuilt_admission'] == {'profile': admitted.PROFILE,
            'policy_sha256': sha(admitted.POLICY), 'map_equivalence_sha256':
            catalogue['files']['evidence/map_equivalence.json']['sha256'],
            'raw_audit_sha256': MAP_RAW_AUDIT_SHA,
            'map_audit_sha256': MAP_EQUIVALENCE_AUDIT_SHA,
            'original_negatives_sha256': catalogue['files']['evidence/lower_negatives.json']['sha256']},
            'raw semantic migration evidence differs')
    for stem, key in [('FactoryScoped', 'generated_normalized_sha256'), ('MiniComplete', 'regression_model_normalized_sha256')]:
        require(new[key] == policy['lower_model_identity'][stem]['normalized_sha256'] ==
                raw.normalized_model(payload / 'models' / (stem + '.lean')), 'new lower model identity differs')
    require(new['tool_binary_path'] == 'artifacts/decoder-inputs/rebuilt-v2/payload/bin/join/aeneas' and
            new['tool_binary_sha256'] == catalogue['files']['bin/join/aeneas']['sha256'], 'join translator identity differs')
    return new


def installation_inventory(prefix, folders):
    """Same file/permission/link identity as the original fixed installation reports."""
    prefix = Path(prefix).resolve(); files = {}
    for folder in folders:
        directory = prefix / folder
        require(not directory.is_symlink(), 'linked installation directory')
        if not directory.exists(): continue
        for path in sorted(directory.rglob('*')):
            name = path.relative_to(prefix).as_posix()
            if path.is_symlink():
                require(path.resolve(strict=True).is_relative_to(prefix), 'external installed symlink')
                files[name] = {'symlink': os.readlink(path)}
            elif path.is_file():
                files[name] = {'sha256': sha(path), 'size': path.stat().st_size, 'mode': path.stat().st_mode & 0o777}
            else: require(path.is_dir(), 'special installed file')
    require(files, 'empty installed runtime')
    return {'files': files, 'sha256': admitted.digest(files)}


def runtime(directory):
    payload = Path(load(directory)['payload'])
    components = read(payload / 'evidence/joint_extraction.json')['components']
    require(sha(RUST_REPORT) == components['rust_report_sha256'] and
            sha(OPAM_REPORT) == components['opam']['report_sha256'], 'runtime installation report drift')
    rust, opam = read(RUST_REPORT), read(OPAM_REPORT)
    rust_home = Path(rust['private_homes']['RUSTUP_HOME'])
    require(str(rust_home) == components['rustup_home'] and
            installation_inventory(rust_home, ['toolchains']) == rust['installed_closures']['rustup'], 'Rust installation drift')
    prefix = Path(opam['opam_root']) / opam['switch']
    require(installation_inventory(prefix, ['bin', 'sbin', 'lib', 'libexec', 'share', 'etc', 'doc', 'man', 'include']) ==
            opam['installed_closure'], 'OPAM installation drift')
    require(sha(Path(components['rustc'])) == components['rustc_sha256'] and
            sha(Path(opam['bootstrap']['path'])) == opam['bootstrap']['sha256'], 'runtime executable drift')
    return {'rustup_home': str(rust_home), 'rustc': components['rustc'],
            'rustc_sha256': components['rustc_sha256'], 'rust_closure_sha256': rust['installed_closures']['rustup']['sha256'],
            'opam_root': opam['opam_root'], 'opam_switch': opam['switch'],
            'opam_bootstrap': opam['bootstrap'], 'opam_closure_sha256': opam['installed_closure']['sha256']}


def environment(out, runtime, config):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('CARGO', 'RUST', 'OPAM', 'OCAML', 'CHARON', 'AENEAS', 'MIRI', 'GIT_', 'SCCACHE', 'CCACHE'))
           and k not in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'MAKEFLAGS', 'LEAN_PATH')}
    env.update(PATH='/usr/bin:/bin', RUSTUP_HOME=runtime['rustup_home'], RUSTUP_TOOLCHAIN=config['rust_toolchain'],
               CARGO_HOME=str(out / 'cargo'), CARGO_TARGET_DIR=str(out / 'cargo-target'),
               CHARON_CACHE_DIR=str(out / 'charon-cache'), CARGO_INCREMENTAL='0', CARGO_BUILD_JOBS='4',
               CARGO_TERM_COLOR='never', RUSTUP_NO_UPDATE_CHECK='1', OPAMROOT=runtime['opam_root'],
               OPAMSWITCH=runtime['opam_switch'], GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
    return env


def translator_command(runtime, binary, arguments):
    return [runtime['opam_bootstrap']['path'], 'exec', '--switch=' + runtime['opam_switch'],
            '--set-switch', '--', binary, *arguments]
