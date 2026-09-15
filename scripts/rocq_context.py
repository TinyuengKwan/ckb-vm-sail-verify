"""Explicit rebuilt Rocq context and generation provenance for production entry.

Uses admitted compiler sources and separately pinned private installations.
No candidate-directory/probe imports, ambient switch fallback or proof claim.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil

PROFILE = 'rebuilt-rocq-v1'
INSTALL_REPORT = 'artifacts/boundary-check/isolated-rocq-ac54t6f8/report.json'
INSTALL_SHA = '3f1f43ebd12cee85cd7f5a49cc6da4dd944a409f46acd928a6881511d1916540'
CLOSURE_SHA = 'e03a37b1c376dfe9305c5a991c65ef6ff104ad14bfe96bda4aa7da6fe8a13e72'
PRIMITIVES_SHA = '45d1909de822a99f9f8685fc504d6622b86959e6e0bacaae3443b426ef977c16'
SOURCE_FILES = ['scripts/rocq_context.py', 'scripts/tests/test_rocq_context.py']
MODEL_STAGES = ['packages', 'version', 'rust-generate', 'rust-primitives', 'rust-model',
                'rust-repro', 'sail-support', 'sail-types', 'sail-model', 'sail-repro']


def require(value, message):
    if not value: raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected(policy):
    if 'main_toolchain' not in policy: return False
    require(policy['main_toolchain'] == 'rebuilt-main-v1', 'unknown Rocq main toolchain profile')
    return True


def environment(env, installation):
    require(installation['switch'] == 'isolated-rocq', 'unreviewed Rocq switch')
    result = {k: v for k, v in env.items() if not k.startswith(('OPAM', 'OCAML', 'CAML', 'COQ', 'ROCQ'))}
    result.update(OPAMROOT=installation['opam_root'], OPAMSWITCH=installation['switch'],
                  PATH='/usr/bin:/bin', OPAMNOENVNOTICE='true', DUNE_CACHE='disabled')
    return result


def opam_exec(opam, root, switch):
    require(Path(opam).is_absolute() and Path(root).is_absolute() and switch and
            not switch.startswith('-') and '/' not in switch, 'non-explicit OPAM selection')
    return [str(opam), 'exec', '--root=' + str(root), '--switch=' + switch, '--set-switch', '--']


def resolve(root, main_env, home):
    import rebuilt_main_tools as tools
    path = root / INSTALL_REPORT
    require(sha(path) == INSTALL_SHA, 'Rocq installation report drift')
    installation = json.loads(path.read_bytes())
    require(installation['status'] == 'isolated_rocq_rebuild_and_existing_input_nogo_passed' and
            installation['installed_closure']['sha256'] == CLOSURE_SHA, 'unapproved Rocq installation')
    require(tools.locations.installation_inventory(Path(installation['opam_root']) / installation['switch'],
            tools.INSTALL_FOLDERS) == installation['installed_closure'], 'Rocq installation closure drift')
    for row in [installation['opam_bootstrap'], *installation['binaries'].values()]:
        require(sha(row['path']) == row['sha256'], 'Rocq/bootstrap binary drift')
    aeneas = tools.read(tools.locations.OPAM_REPORT)
    require(main_env['OPAMROOT'] == aeneas['opam_root'] and main_env['OPAMSWITCH'] == aeneas['switch'] and
            aeneas['bootstrap'] == installation['opam_bootstrap'], 'Aeneas OPAM context differs')
    primitive = home / 'backends/coq/Primitives.v'
    require(primitive.resolve() == primitive and sha(primitive) == PRIMITIVES_SHA, 'Rocq primitive source drift')
    record = {'profile': PROFILE, 'installation_report_sha256': INSTALL_SHA,
              'installed_closure_sha256': CLOSURE_SHA, 'opam_bootstrap': installation['opam_bootstrap'],
              'rocq_opam_root': installation['opam_root'], 'rocq_switch': installation['switch'],
              'aeneas_opam_root': main_env['OPAMROOT'], 'aeneas_switch': main_env['OPAMSWITCH'],
              'binaries': installation['binaries'], 'primitive_source': str(primitive),
              'primitive_sha256': PRIMITIVES_SHA, 'packages': installation['packages']}
    return installation, environment(main_env, installation), record


def commands(root, out, env, binaries, installation):
    opam = installation['opam_bootstrap']['path']
    rocq = opam_exec(opam, installation['opam_root'], installation['switch'])
    aeneas = opam_exec(opam, env['OPAMROOT'], env['OPAMSWITCH'])
    compiler = installation['binaries']['rocq']['path']
    result = {
        'sail-generate': (['bash', 'scripts/generate_proof_model.sh', 'rocq'], root),
        'packages': ([opam, 'list', '--root=' + installation['opam_root'],
                      '--switch=' + installation['switch'], '--installed', '--short', '--columns=name,version'], out),
        'version': (rocq + [compiler, '--version'], out),
        'rust-generate': (aeneas + [str(binaries['aeneas']), '-backend', 'rocq', '-dest', str(out / 'rust'),
                                    str(root / 'target/CkbVmProduction.llbc')], out),
    }
    for name, folder, file in [('rust-primitives', 'rust', 'Primitives.v'),
        ('rust-model', 'rust', 'CkbVmProduction.v'), ('rust-repro', 'rust', 'result_shadowing.v'),
        ('sail-support', 'sail', 'riscv_extras.v'), ('sail-types', 'sail', 'rv64d_types.v'),
        ('sail-model', 'sail', 'rv64d.v'), ('sail-repro', 'sail', 'missing_e_div.v')]:
        result[name] = (rocq + [compiler, 'compile', '-Q', '.', '', file], out / folder)
    require(list(result) == ['sail-generate', *MODEL_STAGES], 'rebuilt Rocq command inventory')
    return result


def check_commands(report, expected):
    require([r['name'] for r in report['stages']] == list(expected), 'rebuilt Rocq stage inventory')
    for row in report['stages']:
        argv, cwd = expected[row['name']]
        require(row['command'] == argv and row['cwd'] == str(cwd), 'Rocq command/context differs: ' + row['name'])


def install_primitives(source, destination, expected=PRIMITIVES_SHA):
    require(source.resolve() == source and source.is_file() and sha(source) == expected, 'Rocq primitive source identity differs')
    require(destination.resolve() == destination and not destination.is_symlink(), 'linked Rocq primitives output')
    existed = destination.exists()
    if existed:
        require(destination.is_file() and sha(destination) == expected, 'unexpected translator primitives; not overwritten')
    else: shutil.copyfile(source, destination)
    require(sha(destination) == expected, 'Rocq primitive copy differs')
    return {'source': str(source), 'sha256': expected,
            'installation': 'translator_emitted_exact' if existed else 'copied_from_verified_source'}


def generation_evidence(root, out, report):
    row = report['stages'][0]
    require(row['name'] == 'sail-generate' and row['command'] == ['bash', 'scripts/generate_proof_model.sh', 'rocq'] and
            row['cwd'] == str(root) and row['status'] == 'passed' and type(row['exit_code']) is int and row['exit_code'] == 0 and
            row['log'] == 'sail-generate.log', 'fresh Sail Rocq generation not completed')
    log = out / row['log']
    require(log.resolve() == log and sha(log) == row['log_sha256'], 'Sail Rocq generation log drift')
    records = [json.loads(line[len('SAIL_INSTALL_JSON='):]) for line in log.read_text().splitlines()
               if line.startswith('SAIL_INSTALL_JSON=')]
    require(len(records) == 1, 'missing/duplicate Sail Rocq generation transaction')
    record = records[0]
    destination = root / 'proof/rocq/generated/sail'
    backup = Path(record['installation_backup'])
    require(record['source'] == str(root / 'deps/sail-riscv/build/rocq') and record['destination'] == str(destination) and
            record['status'] == 'installed' and record['published'] is True and record['policy_changed'] is False and
            backup.parent == destination.parent and backup.name.startswith('.sail-install-'), 'wrong Sail Rocq transaction')
    transaction = backup / 'transaction.json'
    require(transaction.resolve() == transaction and json.loads(transaction.read_bytes()) == record, 'Sail transaction/log mismatch')
    files = {}
    for path in sorted(destination.rglob('*')):
        require(path.resolve() == path, 'linked Sail Rocq output')
        if path.is_dir(): continue
        require(path.is_file() and path.stat().st_nlink == 1, 'nonregular/shared Sail Rocq output')
        files[str(path.relative_to(destination))] = sha(path)
    require(list(files) == record['installed_files'] and {'rv64d.v', 'rv64d_types.v'} <= files.keys(), 'Sail Rocq file inventory drift')
    return {'transaction': str(transaction), 'transaction_sha256': sha(transaction), 'installed_files_sha256': files}
