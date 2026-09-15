"""Explicit rebuilt main-tool resolution; no ambient or legacy fallback.

The formal main gate selects this module with main_toolchain=rebuilt-main-v1
and pins its source identity. Source baseline,
theorem policy and installed input admission remain separate identities.
"""
import os
from pathlib import Path

import check_proof as proof
import decoder_rebuilt_locations as locations
import source_snapshot as snapshot

PROFILE = 'rebuilt-main-v1'
TOOLCHAIN = 'leanprover/lean4:v4.31.0'
BINARIES = {
    'aeneas': '98b7f9727b6296a41d2732bdb5a054937869fb1f9f776d6f2de47be17247953d',
    'charon': '59363fdaa771e300f576c458c6faab0b9d9fa0ae80706e04f5eae760ed7fb523',
    'charon-driver': 'e10cea3b756de291fff060e7eac3d58868468fe71c1b2a85162a2ac02be14441',
    'sail': '783dd162807daafcab8f61afe29e64d7431eb8d8365cc22feb9f74f1633314cf',
}
VERSIONS = {
    'aeneas': 'aeneas 379890b5',
    'charon': '0.1.247 (89ac118194b978d8cf753222c19f313521377aa0)',
    'sail': 'Sail 0.20.2 (HEAD @ 8eb1fb6b5bf9f18c0f89f71e94ff0c5894acd7c1)',
}
LEAN_CLOSURE = '5bacb7efb8a49f13344b136b88a75b595013216ad85760d2645fcb912d9430e7'
SUPPORT = 'b82fe07c458c93c93aa63b69f745b4e9fed3c209fb6fbbbac244a1d14b20f401'
SAIL_REPORT = 'artifacts/boundary-check/isolated-sail-nrdi23ds/report.json'
SAIL_REPORT_SHA = 'a765bc5f4cbaa9af62909ea9cd1e1d2af50a5b9f8437aaf80a7be0cf91b88739'
INSTALL_FOLDERS = ['bin', 'sbin', 'lib', 'libexec', 'share', 'etc', 'doc', 'man', 'include']
# Explicit main-generator Python closure, plus regression tests. No historical
# probe module is imported by the production path.
SOURCES = [
    'scripts/check_proof.py', 'scripts/check_raw_add.py', 'scripts/check_raw_add_fields.py',
    'scripts/ckb_source_baseline.py', 'scripts/decoder_input_bundle.py',
    'scripts/decoder_input_locations.py', 'scripts/decoder_public_source.py',
    'scripts/decoder_rebuilt_inputs.py', 'scripts/decoder_rebuilt_locations.py',
    'scripts/generate_rebuilt_rust.py', 'scripts/rebuilt_main_tools.py',
    'scripts/rebuilt_production_rust.py', 'scripts/sail_model_transaction.py', 'scripts/source_snapshot.py',
    'scripts/tests/test_generate_rebuilt_rust.py', 'scripts/tests/test_rebuilt_main_tools.py',
    'scripts/tests/test_rebuilt_production_rust.py', 'scripts/tests/test_source_snapshot.py',
]
require, sha, read = locations.require, locations.sha, locations.read


def policy_identity(policy):
    require(policy.get('main_toolchain') == PROFILE, 'rebuilt main profile not explicitly selected')
    require(policy.get('tool_binaries') == BINARIES, 'rebuilt main binary policy differs')
    require(policy.get('translator_versions') == VERSIONS, 'rebuilt main version policy differs')
    require(policy.get('lean_toolchain') == TOOLCHAIN and
            policy.get('aeneas_lean_sources_sha256') == SUPPORT, 'rebuilt Lean/support policy differs')


def lean_install(report):
    home = Path(report['private_homes']['ELAN_HOME'])
    expected = report['installed_closures']['elan']
    require(expected['sha256'] == LEAN_CLOSURE, 'unreviewed Lean installation closure')
    require(locations.installation_inventory(home, ['toolchains']) == expected, 'private Lean installation drift')
    prefix = home / 'toolchains/leanprover--lean4---v4.31.0'
    for name in ('lake', 'lean'):
        path = prefix / 'bin' / name
        require(path.is_file() and not path.is_symlink() and os.access(path, os.X_OK),
                'private Lean executable absent: ' + name)
    return home, prefix


def sail_install(root):
    path = root / SAIL_REPORT
    require(sha(path) == SAIL_REPORT_SHA, 'Sail installation report drift')
    report = read(path)
    prefix, source = Path(report['prefix']), Path(report['source'])
    require(locations.installation_inventory(prefix, INSTALL_FOLDERS) == report['installed_closure'],
            'Sail installation closure drift')
    require(locations.installation_inventory(Path(report['opam_root']) / report['switch'], INSTALL_FOLDERS) ==
            report['opam_installed_closure'], 'Sail OPAM closure drift')
    actual = snapshot.inventory(source)
    require(actual == report['source_after'] and actual['head'] == '8eb1fb6b5bf9f18c0f89f71e94ff0c5894acd7c1'
            and not actual['gitlinks'] and not actual['changes_from_head'], 'Sail compiler source drift')
    snapshot.independent(source)
    return prefix


def cmake_compiler(root, compiler):
    cache = root / 'deps/sail-riscv/build/CMakeCache.txt'
    require(cache.is_file() and not cache.is_symlink(), 'candidate Sail CMake cache missing')
    settings = {}
    for line in cache.read_text().splitlines():
        if '=' not in line or line.startswith(('#', '//')): continue
        key, value = line.split('=', 1)
        require(key not in settings, 'duplicate CMake cache key')
        settings[key] = value
    require(settings.get('CMAKE_HOME_DIRECTORY:INTERNAL') == str(root / 'deps/sail-riscv'),
            'Sail CMake source differs')
    require(settings.get('SAIL_BIN:FILEPATH') == str(compiler), 'Sail CMake compiler differs')


def environment(root, runtime, config, prefix, elan_home, lean_prefix, support_home, binaries):
    env = locations.environment(root / 'artifacts/rebuilt-main-runtime', runtime, config)
    # Fixed compiler and plugin selection is not meaningful while ambient
    # startup scripts, Lean paths, compiler flags or caches can replace it.
    for key in list(env):
        if key.startswith(('LEAN', 'ELAN', 'SAIL_', 'DUNE_', 'CMAKE_', 'GIT_', 'CCACHE', 'SCCACHE')) or key in (
                'BASH_ENV', 'ENV', 'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS',
                'LIBRARY_PATH', 'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'COMPILER_PATH',
                'GCC_EXEC_PREFIX', 'CONFIG_SITE', 'MFLAGS'):
            env.pop(key)
    env.update(PATH=os.pathsep.join([str(lean_prefix / 'bin'), str(prefix / 'bin'), '/usr/bin', '/bin']),
               ELAN_HOME=str(elan_home), ELAN_TOOLCHAIN=TOOLCHAIN, LEAN_ABORT_ON_PANIC='1',
               LEAN_NUM_THREADS='8', AENEAS_HOME=str(support_home),
               AENEAS=str(binaries['aeneas']), CHARON=str(binaries['charon']),
               SAIL_DIR=str(prefix / 'share/sail'), SAIL_PLUGIN_DIR=str(prefix / 'share/libsail/plugins'),
               SAIL_RISCV_DIR=str(root / 'deps/sail-riscv'),
               SAIL_BIN=str(root / 'deps/sail-riscv/build/c_emulator/sail_riscv_sim'),
               SAIL_CONFIG_OVERRIDE=str(root / 'sail-model/ckb_vm_config.json'),
               SAIL_CONFIG=str(root / 'sail-model/build/ckb_vm_config.json'),
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', DUNE_CACHE='disabled')
    return env


def resolve(root, policy):
    root = Path(root).resolve()
    policy_identity(policy)
    directory = root / 'artifacts/decoder-inputs/rebuilt-v2'
    installed, config = locations.configuration(directory)
    runtime = locations.runtime(directory)
    rust_report = read(locations.RUST_REPORT)  # Its identity was checked by runtime().
    elan_home, lean_prefix = lean_install(rust_report)
    prefix = sail_install(root)
    payload = Path(installed['payload'])
    home = directory / 'sources/base/aeneas'
    binaries = {name: payload / 'bin/base' / name for name in ('charon', 'charon-driver', 'aeneas')}
    binaries['sail'] = prefix / 'bin/sail'
    require({k: sha(v) for k, v in binaries.items()} == BINARIES, 'installed main binary identity differs')
    require(proof.digest(proof.canonical(proof.tree_files(home / 'backends/lean', proof.lean_sources))) == SUPPORT,
            'installed Aeneas Lean support differs')
    cmake_compiler(root, binaries['sail'])
    env = environment(root, runtime, config, prefix, elan_home, lean_prefix, home, binaries)
    return env, binaries, home, str(lean_prefix / 'bin/lake')
