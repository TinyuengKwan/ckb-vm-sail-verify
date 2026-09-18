"""Produce a complete review of one sealed formal-output delta.

The tracked driver creates a new review directory and invokes byte-identical
copies of this reviewer in record/check modes. Those copies perform read-only
source/blob/archive checks; no generated code is executed and no whole-current-
output, compiler-correctness, delivery or publication claim is made.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tomllib

SCRIPT = Path(__file__).resolve()
if SCRIPT.parent.parent.name == 'boundary-check' and SCRIPT.parent.name.startswith('week6-formal-review-'):
    OUT = SCRIPT.parent
    ROOT = OUT.parents[2]
else:
    OUT = None
    ROOT = SCRIPT.parents[1]
FORMAL = RUST = PUBLIC = ROCQ = CLEAN = None
sys.path.insert(0, str(ROOT / 'scripts'))
import generated_output_inventory as inventory
import source_snapshot
import decoder_harness
import record_generation as recording
import release_formal_generation_review as validator

FLAGS = {'whole_current_output_tree_rehashed': False, 'candidate_approval_claimed': False,
         'generated_outputs_audited': False, 'worktree_audit_closed': False,
         'kernel_executed': False, 'release_claimed': False, 'week6_closed': False,
         'clean_room_claimed': False, 'independent_third_party_claimed': False}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(name, value):
    with (OUT / name).open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def safe(name):
    require(isinstance(name, str) and name and not name.startswith('/') and
            all(p not in ('', '.', '..') for p in name.split('/')), 'unsafe member')
    return name


def relative(path):
    path = Path(path)
    require(path.is_absolute() and path.is_relative_to(ROOT), 'path outside checkout')
    return safe(path.relative_to(ROOT).as_posix())


def regular_bytes(name):
    path = ROOT
    for part in safe(name).split('/'):
        path /= part
        require(not path.is_symlink(), 'symlink member: ' + name)
    require(path.is_file(), 'not a regular file: ' + name)
    return path.read_bytes()


def configure():
    global FORMAL, RUST, PUBLIC, ROCQ, CLEAN
    require(OUT is not None, 'formal review output is not configured')
    config = read(OUT / 'input.json')
    require(type(config) is dict and set(config) == {
        'schema_version', 'kind', 'formal_report', 'formal_report_sha256'
    } and type(config['schema_version']) is int and config['schema_version'] == 1 and
            config['kind'] == 'week6-formal-review-input-v1' and
            re.fullmatch(r'[0-9a-f]{64}', config['formal_report_sha256'] or ''),
            'formal review input fields/identity')
    report_name = safe(config['formal_report'])
    require(report_name.endswith('/report.json') and
            sha(regular_bytes(report_name)) == config['formal_report_sha256'],
            'formal review report reference differs')
    FORMAL = report_name.removesuffix('/report.json')
    producer = read(ROOT / report_name)
    roots = producer.get('new_evidence_roots')
    require(type(roots) is list and len(roots) == 2 and len(set(roots)) == 2,
            'formal producer root inventory')
    rust = [name for name in roots if Path(name).name.startswith('rebuilt-production-rust-')]
    public = [name for name in roots if Path(name).name.startswith('public-check-')]
    require(len(rust) == len(public) == 1, 'formal producer roots differ')
    RUST, PUBLIC = safe(rust[0]), safe(public[0])
    ROCQ, CLEAN = FORMAL + '/rocq', PUBLIC + '/clean'
    return config


if OUT is not None:
    configure()


def llbc_difference(old, new, old_dest, new_dest):
    a, b = json.loads(old), json.loads(new)
    require(a['translated']['options']['dest_file'] == old_dest and
            b['translated']['options']['dest_file'] == new_dest, 'LLBC destination identity')
    x, y = a['translated']['short_names'], b['translated']['short_names']
    require(type(x) is list and type(y) is list and len(x) == len(y), 'short-name inventory')
    left, right = list(map(canonical, x)), list(map(canonical, y))
    require(len(set(left)) == len(left) and len(set(right)) == len(right) and
            set(left) == set(right), 'short-name rows are not a permutation of unique identical rows')
    a['translated']['short_names'] = y
    a['translated']['options']['dest_file'] = new_dest
    require(a == b, 'additional LLBC structural difference')
    return {'short_name_rows': len(x), 'permutation_only': left != right,
            'old_destination': old_dest, 'new_destination': new_dest,
            'other_json_identical': True, 'translator_correctness_proven': False}


def git_blobs(directory, revision):
    """Read blobs/literal symlinks; return gitlink IDs, never their source trees."""
    def git(*args, **kwargs):
        return subprocess.check_output(['git', '-C', str(directory), *args], timeout=120, **kwargs)
    require(git('rev-parse', 'HEAD').decode().strip() == revision, 'dependency HEAD drift')
    rows = []
    for entry in git('ls-tree', '-rz', '--full-tree', revision).split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, kind, oid = header.split()
        require((kind == b'blob' and mode in (b'100644', b'100755', b'120000')) or
                (kind == b'commit' and mode == b'160000'), 'unexpected Git entry mode')
        rows.append((mode.decode(), oid.decode(), safe(name.decode())))
    require(len({r[2] for r in rows}) == len(rows), 'duplicate Git tree path')
    ids = list(dict.fromkeys(row[1] for row in rows if row[0] != '160000'))
    result = subprocess.run(['git', '-C', str(directory), 'cat-file', '--batch'],
                            input=('\n'.join(ids) + '\n').encode(), capture_output=True, timeout=120)
    require(result.returncode == 0, 'Git blob reading failed')
    data, offset, objects = result.stdout, 0, {}
    for oid in ids:
        end = data.index(b'\n', offset)
        actual, kind, size = data[offset:end].split()
        require(actual.decode() == oid and kind == b'blob', 'unexpected batch object')
        size = int(size)
        require(size >= 0, 'negative blob size')
        offset = end + 1
        payload = data[offset:offset + size]
        require(len(payload) == size and data[offset + size:offset + size + 1] == b'\n', 'truncated Git blob')
        objects[oid] = payload
        offset += size + 1
    require(offset == len(data), 'extra Git batch output')
    return [(mode, name, oid.encode() if mode == '160000' else objects[oid]) for mode, oid, name in rows]


def classify(name, change, bindings, git_bases):
    """No catch-all evidence-root classification; unknown files fail closed."""
    safe(name)
    node = change['after']
    require(node is not None, 'unexpected deletion')
    if name in bindings:
        return bindings[name]
    if node['kind'] == 'directory':
        require(change['operation'] == 'added', 'unbound directory modification')
        return {'category': 'directory', 'evidence': 'structural node in the recorded scope'}
    require(change['operation'] == 'added' and node['kind'] == 'file', 'unbound modification or symlink')
    if any(name.startswith(base) for base in git_bases):
        return {'category': 'git_metadata', 'evidence': 'retained clone metadata; not self-contained delivery approval'}
    if any(name.startswith(prefix + '/cargo-target/') for prefix in [RUST, PUBLIC]):
        return {'category': 'cargo_build_cache', 'evidence': 'fresh target of the recorded extraction command'}
    if any(name == prefix + '/cargo/registry/CACHEDIR.TAG' or
           name.startswith(prefix + '/cargo/registry/index/') or
           (name.startswith(prefix + '/cargo/registry/src/') and name.endswith('/.cargo-ok')) or
           name in [prefix + '/cargo/' + n for n in ['.global-cache', '.package-cache', '.package-cache-mutate']]
           for prefix in [RUST, PUBLIC]):
        return {'category': 'cargo_metadata', 'evidence': 'retained registry/cache metadata, not model proof'}
    if ('/.lake/build/' in name or '/.lake/config/' in name) and any(name.startswith(p) for p in [
            CLEAN + '/', 'proof/lean/generated/rust/.lake/', 'proof/lean/generated/sail/.lake/']):
        return {'category': 'lean_build_cache', 'evidence': 'recorded build products, not an approved release payload'}
    if name.startswith(ROCQ + '/') and name.split('/')[-2] in ['rust', 'sail'] and (
            Path(name).suffix in ['.vo', '.vos', '.vok', '.glob', '.aux'] or name.endswith('/.lia.cache')):
        return {'category': 'rocq_build_cache', 'evidence': 'spike artifacts; NO-GO adds no proof coverage'}
    raise RuntimeError('unclassified delta: ' + name)


def validate_summary(report, facts, reviews):
    require(type(report['schema_version']) is int and report['schema_version'] == 1 and
            report['status'] == 'all_recorded_formal_deltas_explained_final_scope_pending', 'review status/schema')
    require(type(report['reviewed_changes']) is int and report['reviewed_changes'] == len(reviews) ==
            facts['reviewed_changes'] and report['categories'] == facts['category_counts'] ==
            dict(Counter(row['category'] for row in reviews.values())), 'review summary inventory')
    require(report['formal_report_sha256'] == facts['formal_report_sha256'] and
            report['delta_sha256'] == facts['delta_sha256'], 'review input binding')
    require(all(report.get(k) is v for k, v in FLAGS.items()), 'review assurance flags changed')


def expected_review_tests(test_source):
    """The self-test count is the number of test methods in the copied test file, not a literal."""
    count = len(re.findall(rb'(?m)^    def test_[A-Za-z0-9_]+\(self\):', test_source))
    require(count >= 26, 'review test file lost coverage')
    return count


def test_evidence():
    test_source = (OUT / 'test_review.py').read_bytes()
    files = {'test_review.py': sha(test_source)}
    expected = expected_review_tests(test_source)
    for name, options in [('ordinary', []), ('optimized', ['-O'])]:
        stage = 'test-review-' + name
        finished = stage + '-finished.json'
        row = read(OUT / finished)
        require(row['status'] == 'completed' and type(row['exit_code']) is int and row['exit_code'] == 0 and
                row['argv'] == ['/usr/bin/python3', '-B', *options, str(OUT / 'test_review.py')],
                'review tests failed or command changed')
        log = stage + '.log'
        data = (OUT / log).read_bytes()
        require(sha(data) == row['log_sha256'] and
                re.findall(rb'(?m)^Ran (\d+) tests? in ', data) == [str(expected).encode()] and
                re.search(rb'(?m)^OK\s*\Z', data), 'review test completion mismatch')
        files[finished], files[log] = sha((OUT / finished).read_bytes()), sha(data)
    return {'tests_per_mode': expected, 'modes': ['ordinary', 'optimized'], 'files': files}


def transaction_mapping(destination, backup):
    """Persist mappings as JSON-native arrays, preserving both exact paths."""
    return [destination, backup]


MANDATORY_MODIFICATIONS = frozenset([
    'proof/lean/generated/rust/SOURCE_BASELINE.json',
    'proof/lean/theorems/.lake/step-build.log',
    'target/CkbVmProduction.llbc',
])
# Sail memoizes Z3 results in the emulator build (--memo-z3-path); regenerating
# the model may rewrite that file in a fresh environment where the cache is
# still cold.  It is solver bookkeeping, not model or proof content.
SOLVER_MEMO_CACHE = 'deps/sail-riscv/build/model/sail_smt_cache'
EXPLAINED_MODIFICATIONS = MANDATORY_MODIFICATIONS | {SOLVER_MEMO_CACHE}


def sail_backup_expectations(paths, flags, before_entries):
    """A Sail transaction must back up exactly what existed before it ran.

    On the producing host both the generation source and the installed
    destination usually pre-exist, so both backups are saved.  In a fresh
    environment the Rocq model is generated for the first time inside the
    formal record and nothing can be backed up; that is legitimate only when the
    before-inventory really has no node under the path.  Returns the mappings
    to retained originals and the first-generation records.
    """
    mappings, first = [], []
    for key, saved, flag in [('source', 'generation_backup', 'old_source_saved'),
                             ('destination', 'installation_backup', 'old_destination_saved')]:
        old = paths[key]
        existed = any(name == old or name.startswith(old + '/') for name in before_entries)
        if flags[flag] is True:
            require(existed, 'Sail backup claimed for a path absent before the run: ' + old)
            mappings.append(transaction_mapping(old, paths[saved] + '/previous'))
        else:
            require(flags[flag] is False, 'Sail backup flag shape')
            require(not existed, 'missing Sail backup for pre-existing ' + key + ': ' + old)
            first.append({key: old, 'first_generation': True})
    return mappings, first


CONFIG_NAME = 'ckb_vm_config.json'


def bind_generation_outputs(paths, record, changes, after, bind, config_bytes, destination_abs):
    """Explain freshly generated Sail model files by the transaction that produced them.

    On the producing host the generated trees pre-exist and regenerating them
    leaves no delta.  In a fresh environment the first generation adds the raw
    Sail output under the transaction source and the adapted copy under the
    destination.  Installed model files must be byte-identical to the raw output;
    the configuration copy must equal the materialized configuration and its
    checksum file must name that digest and the destination path.  Anything
    else under those directories stays unclassified.
    """
    source, destination = paths['source'], paths['destination']
    raw, installed = set(record['raw_files']), set(record['installed_files'])
    require(raw <= installed and installed - raw <= {CONFIG_NAME, CONFIG_NAME + '.sha256'},
            'transaction file inventory shape')
    bound = 0
    for name in sorted(installed):
        target = destination + '/' + name
        if target not in changes:
            continue
        require(changes[target]['operation'] == 'added' and after.get(target, {}).get('kind') == 'file',
                'installed generation output is not a fresh file: ' + target)
        if name == CONFIG_NAME:
            require(after[target]['sha256'] == sha(config_bytes), 'installed configuration differs: ' + target)
            bind(target, 'installed_generation_config', {'transaction_destination': destination})
        elif name == CONFIG_NAME + '.sha256':
            expected = (sha(config_bytes) + '  ' + destination_abs + '/' + CONFIG_NAME + '\n').encode()
            require(after[target]['sha256'] == sha(expected) and after[target]['size'] == len(expected),
                    'installed configuration checksum differs: ' + target)
            bind(target, 'installed_generation_config', {'transaction_destination': destination})
        else:
            raw_node = after.get(source + '/' + name)
            require(raw_node is not None and raw_node['kind'] == 'file' and
                    raw_node['sha256'] == after[target]['sha256'], 'installed output differs from raw output: ' + target)
            bind(target, 'installed_generation_output', {'raw_output': source + '/' + name,
                                                          'sha256': after[target]['sha256']})
        bound += 1
    for name in sorted(raw):
        target = source + '/' + name
        if target not in changes:
            continue
        require(changes[target]['operation'] == 'added' and after.get(target, {}).get('kind') == 'file',
                'raw generation output is not a fresh file: ' + target)
        bind(target, 'raw_generation_output', {'installed_copy': destination + '/' + name,
                                                'sha256': after[target]['sha256']})
        bound += 1
    return bound


def check_operations(changes):
    """Only additions and the explicitly explained modifications may appear; no deletions."""
    operations = Counter(v['operation'] for v in changes.values())
    require(operations and set(operations) <= {'added', 'modified'}, 'unexpected formal operation inventory')
    modified = {name for name, change in changes.items() if change['operation'] == 'modified'}
    require(MANDATORY_MODIFICATIONS <= modified, 'expected formal modifications absent: ' +
            json.dumps(sorted(MANDATORY_MODIFICATIONS - modified)))
    require(modified <= EXPLAINED_MODIFICATIONS, 'unexplained formal modifications: ' +
            json.dumps(sorted(modified - EXPLAINED_MODIFICATIONS)))
    return modified


def compute():
    report_data = regular_bytes(FORMAL + '/report.json')
    config = read(OUT / 'input.json')
    require(sha(report_data) == config['formal_report_sha256'],
            'formal record anchor changed')
    producer = json.loads(report_data)
    require(producer['kernel_and_rocq_records_validated'] is True and producer['errors'] == [],
            'formal execution not independently accepted')
    for name, digest in producer['record_files'].items():
        require(sha(regular_bytes(FORMAL + '/' + name)) == digest, 'bound formal record changed: ' + name)
    before, after = read(ROOT / FORMAL / 'before-expanded.json'), read(ROOT / FORMAL / 'after/snapshot.json')
    delta = read(ROOT / FORMAL / 'delta.json')
    require(inventory.compare(before, after) == delta, 'delta is not the recorded full comparison')
    modified = check_operations(delta['changes'])
    a, b = before['entries'], after['entries']
    source = read(ROOT / FORMAL / 'source-before.json')
    require(source == read(ROOT / FORMAL / 'source-after.json'), 'formal source drift')
    source_files = {('' if repo == '.' else repo + '/') + name: node
                    for repo, state in source['repositories'].items() for name, node in state['files'].items()}
    bindings, facts = {}, {'formal_report_sha256': sha(report_data),
                          'delta_sha256': sha(regular_bytes(FORMAL + '/delta.json')),
                          'formal_source_snapshot_sha256': source['snapshot_sha256']}

    def bytes_at(name):
        data = regular_bytes(name)
        node = b.get(name)
        require(node is not None and node['kind'] == 'file' and node['size'] == len(data) and
                node['sha256'] == sha(data), 'observed/current selected file differs: ' + name)
        return data

    def bind(name, category, evidence):
        require(name in b and b[name] is not None and name not in bindings, 'duplicate/missing review member: ' + name)
        bindings[name] = {'category': category, 'evidence': evidence}

    def match_copy(name, original, category='source_copy'):
        node = b[name]
        require(node['kind'] == 'file' and node['sha256'] == original['sha256'] and
                node['size'] == original['size'], 'copied source content differs: ' + name)
        require(bool(node['mode'] & 0o111) == (original['mode'] == '100755'), 'copied source executable mode')
        bind(name, category, {'source_sha256': original['sha256']})

    # Production clone and payload, against the complete frozen source inventory.
    state = json.loads(bytes_at(RUST + '/source-snapshot.json'))
    require(state == source and source_snapshot.capture(ROOT / RUST / 'checkout') == state,
            'production staged source snapshot differs')
    for name, node in source_files.items():
        for folder in ('checkout', 'source-payload'):
            match_copy(RUST + '/' + folder + '/' + name, node)
    facts['production_source_copy_files'] = 2 * len(source_files)

    # All retained originals, including LLBC, are mapped exactly to pre-run nodes.
    tx_names = [n for n in delta['changes'] if n.endswith('/transaction.json') and not n.startswith('artifacts/')]
    require(len(tx_names) == 3, 'unexpected transaction count')
    retained, mappings, first_generations, generation_bound = {}, [], [], 0
    for name in tx_names:
        tx = json.loads(bytes_at(name))
        require(tx['status'] == 'installed' and tx['policy_changed'] is False, 'transaction status/policy')
        bind(name, 'transaction_record', {'status': 'installed'})
        if 'llbc' in tx:
            require(tx['old_llbc_saved'] is True and tx['old_model_saved'] is True, 'missing Rust backups')
            backup, dest = relative(tx['backup']), relative(tx['destination'])
            mappings.append(transaction_mapping(dest, backup + '/previous'))
            old_llbc = backup + '/previous.llbc'
            require(b[old_llbc] == a[relative(tx['llbc'])], 'old LLBC backup differs')
            retained[old_llbc] = relative(tx['llbc'])
            rust_backup = backup
        else:
            tx_mappings, first = sail_backup_expectations(
                {key: relative(tx[key]) for key in ('source', 'destination', 'generation_backup', 'installation_backup')},
                {key: tx[key] for key in ('old_source_saved', 'old_destination_saved')}, a)
            mappings.extend(tx_mappings)
            first_generations.extend({'transaction': name, **row} for row in first)
            generation_bound += bind_generation_outputs(
                {key: relative(tx[key]) for key in ('source', 'destination')}, tx, delta['changes'], b, bind,
                bytes_at('sail-model/build/' + CONFIG_NAME), tx['destination'])
    for old, backup in mappings:
        for name, node in a.items():
            if name == old or name.startswith(old + '/'):
                new = backup + name[len(old):]
                require(b.get(new) == node, 'retained original differs: ' + name)
                require(new not in retained, 'overlapping backups')
                retained[new] = name
    for name, old in retained.items():
        bind(name, 'retained_original', old)
    facts['retained_original_nodes'] = len(retained)
    facts['transaction_mappings'] = mappings
    facts['first_generations'] = first_generations
    facts['fresh_generation_output_nodes'] = generation_bound

    # Three modified files: exact representation change, new provenance, build log.
    old_prov = rust_backup + '/previous/SOURCE_BASELINE.json'
    old = json.loads(bytes_at(old_prov))
    new = json.loads(bytes_at('proof/lean/generated/rust/SOURCE_BASELINE.json'))
    llbc_old, llbc_new = bytes_at(rust_backup + '/previous.llbc'), bytes_at('target/CkbVmProduction.llbc')
    old_destination = json.loads(llbc_old)['translated']['options']['dest_file']
    new_destination = json.loads(llbc_new)['translated']['options']['dest_file']
    require(new_destination == str(ROOT / RUST / 'CkbVmProduction.llbc'),
            'new LLBC destination differs from current producer')
    facts['llbc'] = llbc_difference(llbc_old, llbc_new, old_destination, new_destination)
    require(facts['llbc']['short_name_rows'] == 611, 'LLBC short-name count')
    rust_report = json.loads(bytes_at(RUST + '/report.json'))
    require(new['rebuilt_extraction']['report'] == RUST + '/report.json' and
            new['rebuilt_extraction']['report_sha256'] == sha(bytes_at(RUST + '/report.json')) and
            old['llbc_sha256'] == sha(llbc_old) and new['llbc_sha256'] == sha(llbc_new), 'provenance/LLBC links')
    changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
    require(changed == {'llbc_sha256', 'rebuilt_extraction'}, 'unexpected provenance change')
    require(new['generated_lean_sha256'] == sha(bytes_at('proof/lean/generated/rust/CkbVmProduction.lean')) ==
            sha(bytes_at(RUST + '/generated/CkbVmProduction.lean')), 'generated Lean model identity')
    bind('target/CkbVmProduction.llbc', 'llbc_representation', facts['llbc'])
    bind('proof/lean/generated/rust/SOURCE_BASELINE.json', 'installed_provenance', {'changed_fields': sorted(changed)})
    log_name = 'proof/lean/theorems/.lake/step-build.log'
    tail = b''.join(bytes_at(log_name).splitlines(keepends=True)[-20:])
    require(tail and tail in regular_bytes(FORMAL + '/main/kernel-step.log'), 'build log tail/stage mismatch')
    bind(log_name, 'build_log', {'stage': FORMAL + '/main/kernel-step.log',
         'last_20_lines_identical': True, 'old_log_bytes_recovered': False})
    if SOLVER_MEMO_CACHE in delta['changes']:
        change = delta['changes'][SOLVER_MEMO_CACHE]
        require(change['after'] is not None and change['after']['kind'] == 'file' and
                change['operation'] in ('added', 'modified'), 'solver memo cache change shape')
        bytes_at(SOLVER_MEMO_CACHE)
        bind(SOLVER_MEMO_CACHE, 'solver_memo_cache', {
            'sail_option': '--memo-z3-path', 'operation': change['operation'],
            'before_sha256': (change.get('before') or {}).get('sha256'),
            'content_is_evidence': False})

    # Cargo archives and every extracted member, checked without unpacking.
    registry_facts = {}
    for prefix, lock_name in [(RUST, RUST + '/checkout/Cargo.lock'), (PUBLIC, PUBLIC + '/outer/Cargo.lock')]:
        lock = tomllib.loads(bytes_at(lock_name).decode())
        locked = {p['name'] + '-' + p['version']: p['checksum'] for p in lock['package'] if 'checksum' in p}
        registry = prefix + '/cargo/registry/'
        archives, members = {}, {}
        for name, node in b.items():
            if not name.startswith(registry + 'cache/') or node is None or node['kind'] != 'file':
                continue
            package = Path(name).name.removesuffix('.crate')
            require(name.endswith('.crate') and locked.get(package) == node['sha256'], 'archive not lock-bound')
            bytes_at(name)
            archives[package] = name
            bind(name, 'locked_archive', {'cargo_lock': lock_name, 'package': package})
            source_base = registry + 'src/' + Path(name).parent.name + '/' + package
            with tarfile.open(ROOT / name, 'r:gz') as archive:
                seen = set()
                for member in archive:
                    safe(member.name.rstrip('/'))
                    require(member.name.startswith(package + '/') and member.name not in seen,
                            'invalid/duplicate archive member')
                    seen.add(member.name)
                    if member.isdir():
                        continue
                    require(member.isfile(), 'nonregular Cargo archive payload')
                    payload = archive.extractfile(member).read()
                    target = source_base + member.name[len(package):]
                    expected = b.get(target)
                    require(expected is not None and expected['kind'] == 'file' and
                            expected['size'] == len(payload) and expected['sha256'] == sha(payload),
                            'extracted Cargo file differs: ' + target)
                    members[target] = name
                    bind(target, 'registry_source', name)
        require(archives, 'missing registry archives')
        for name, node in b.items():
            if name.startswith(registry + 'src/') and node is not None and node['kind'] == 'file':
                require(name in members or name.endswith('/.cargo-ok'), 'unclassified registry source')
        registry_facts[prefix] = {'lock': lock_name, 'archives': len(archives), 'member_files': len(members),
                                  'package_safety_or_semantics_proven': False}
    facts['registries'] = registry_facts

    public = json.loads(bytes_at(PUBLIC + '/report.json'))
    require(sha(bytes_at(PUBLIC + '/report.json')) ==
            read(ROOT / FORMAL / 'main/report.json')['public_decoder']['report_sha256'], 'public/main binding')
    clean = public['clean_dependencies']
    require(clean['status'] == 'passed' and clean['initial_compiled_modules'] == 0, 'clean build not accepted')
    main_rust_config = tomllib.loads(bytes_at('proof/lean/generated/rust/lakefile.toml').decode())
    aeneas_source = Path(main_rust_config['require'][0]['path'])
    aeneas_relative = relative(aeneas_source)
    formal_inputs = read(ROOT / FORMAL / 'formal-inputs-before.json')

    # Clean project copies, including only the recipe's explicit path rewrite.
    clean_prefixes = ['proof/lean/theorems', 'proof/lean/generated/rust', 'proof/lean/generated/sail',
                      'proof/lean/audit', 'proof/lean/compat']
    for name, node in b.items():
        if node is None or node['kind'] != 'file' or not name.startswith(CLEAN + '/') or '/.lake/' in name:
            continue
        suffix = name[len(CLEAN) + 1:]
        payload = bytes_at(name)
        if any(suffix.startswith(p + '/') for p in clean_prefixes):
            if suffix == 'proof/lean/generated/rust/lakefile.toml':
                original = bytes_at(suffix)
                old_path = ('path = "' + str(aeneas_source) + '"').encode()
                new_path = ('path = "' + str(ROOT / CLEAN / 'support/Aeneas') + '"').encode()
                require(original.count(old_path) == 1 and original.replace(old_path, new_path) == payload,
                        'clean Rust config changed beyond the support path')
                bind(name, 'path_relocated_config', suffix)
            else:
                expected = b.get(suffix) or source_files.get(suffix)
                require(expected is not None and expected['sha256'] == sha(payload), 'clean project source differs')
                bind(name, 'source_copy', suffix)
        elif suffix.startswith('support/Aeneas/'):
            local = suffix[len('support/Aeneas/'):]
            require(payload == regular_bytes(aeneas_relative + '/' + local), 'clean Aeneas copy differs')
            if local.endswith('.lean'):
                require(formal_inputs['aeneas_lean_sources'].get(local) == sha(payload), 'support not formal-source-bound')
            bind(name, 'support_source_copy', aeneas_relative + '/' + local)
        else:
            raise RuntimeError('unexpected clean source file: ' + name)

    # Locked dependency source blobs, not just revision strings or cache names.
    git_bases = []
    dependency_facts = {}
    for package, revision in clean['dependency_revisions'].items():
        base = CLEAN + '/proof/lean/theorems/.lake/packages/' + package
        git_bases.append(base + '/.git/')
        blobs = git_blobs(ROOT / base, revision)
        for mode, suffix, payload in blobs:
            name = base + '/' + suffix
            node = b.get(name)
            require(node is not None, 'missing locked Git path')
            if mode == '160000':
                require((package, suffix, payload.decode()) ==
                        ('aesop', 'lean_packages/std', 'c2130e653bc1057f8f21196a9b89987d84fe247b'),
                        'unreviewed dependency gitlink')
                require(node['kind'] == 'directory' and not any(k.startswith(name + '/') for k in b),
                        'gitlink placeholder is populated or not a directory')
                bind(name, 'unmaterialized_gitlink', {'commit': payload.decode(), 'source_materialized': False})
                continue
            if mode == '120000':
                require(node['kind'] == 'symlink' and node['target'] == payload.decode(), 'Git symlink differs')
            else:
                require(node['kind'] == 'file' and node['size'] == len(payload) and node['sha256'] == sha(payload) and
                        bool(node['mode'] & 0o111) == (mode == '100755'), 'locked Git blob differs: ' + name)
            bind(name, 'locked_git_source', {'package': package, 'revision': revision, 'mode': mode})
        alternates = base + '/.git/objects/info/alternates'
        expected_alternate = ROOT / 'proof/lean/theorems/.lake/packages' / package / '.git/objects'
        require(bytes_at(alternates).decode().strip() == str(expected_alternate), 'unexpected shared Git object path')
        dependency_facts[package] = {'revision': revision, 'tracked_entries': len(blobs),
                                     'shared_objects': str(expected_alternate), 'self_contained_clone': False}
    facts['locked_git_dependencies'] = dependency_facts
    widget_lock = CLEAN + '/proof/lean/theorems/.lake/packages/proofwidgets/widget/package-lock.json'
    widget_hash = widget_lock + '.hash'
    marker = bytes_at(widget_hash).strip()
    require(bindings[widget_lock]['category'] == 'locked_git_source' and len(marker) == 16 and
            all(c in b'0123456789abcdef' for c in marker), 'unexpected Lake input-hash marker')
    bind(widget_hash, 'lake_input_hash_metadata', {'input': widget_lock,
         'recipe': CLEAN + '/proof/lean/theorems/.lake/packages/proofwidgets/lakefile.lean',
         'hash_algorithm_recomputed': False, 'production_model_claimed': False})
    aeneas_link = CLEAN + '/proof/lean/theorems/.lake/aeneas'
    require(b[aeneas_link]['kind'] == 'symlink' and b[aeneas_link]['target'] == str(ROOT / CLEAN / 'support/Aeneas'),
            'clean Aeneas symlink target differs')
    bind(aeneas_link, 'build_support_link', {'target': b[aeneas_link]['target'], 'followed': False})

    # Public harness, lower sources, translated/linked models and negative fixture.
    require(decoder_harness.verify(ROOT / PUBLIC / 'outer', ROOT) == public['source_reextraction']['harness_after'],
            'public harness changed')
    for name, digest in public['source_reextraction']['harness_after']['files'].items():
        path = PUBLIC + '/outer/' + name
        require(sha(bytes_at(path)) == digest, 'public harness file hash')
        bind(path, 'public_harness', {'expected_sha256': digest})
    for name, digest in clean['reused_generated_sources'].items():
        path = PUBLIC + '/dependencies/' + name + '.lean'
        require(sha(bytes_at(path)) == digest, 'lower decoder source identity')
        bind(path, 'lower_proof_source', {'expected_sha256': digest})
    for name, record in public['source_reextraction']['inputs'].items():
        path = PUBLIC + '/' + name
        require(sha(bytes_at(path)) == record['sha256'], 'public LLBC identity')
        bind(path, 'extracted_model', {'expected_sha256': record['sha256']})
    generated_public = PUBLIC + '/generated/OuterClosedDepsV3.lean'
    generated_iterator = PUBLIC + '/generated/FnPtrFullMir.lean'
    linked = PUBLIC + '/models/OuterRawLinked.lean'
    iterator = PUBLIC + '/models/FnPtrFullMir.lean'
    text = bytes_at(generated_public)
    require(text.count(b'import Aeneas\n') == 1 and
            bytes_at(linked) == text.replace(b'import Aeneas\n', b'import Aeneas\nimport CkbVmProduction\n', 1) and
            bytes_at(iterator) == bytes_at(generated_iterator), 'public model adapter changed')
    for name in [generated_public, generated_iterator, linked, iterator]:
        bind(name, 'extracted_or_linked_model', {'public_report': PUBLIC + '/report.json'})
    original = regular_bytes('proof/lean/decoder/toolchain/full-entry/OuterPublic.lean').decode()
    anchor = 'theorem public_mop_off {M R : Type}'
    require(original.count(anchor) == 1, 'weakening anchor')
    weak = original.split('/-- Original ADD word', 1)[0].replace(
        anchor, 'theorem public_mop_off (unused : False) {M R : Type}', 1) + '\nend\nend OuterAdd\n'
    require(bytes_at(PUBLIC + '/weakened/OuterPublic.lean').decode() == weak, 'negative fixture differs')
    exporter = ('import OuterPublic\nimport Lean\nopen Lean Elab Command\nrun_cmd do\n'
                '  let info ← getConstInfo ``OuterAdd.public_mop_off\n'
                '  liftIO <| IO.println ("TYPE=" ++ (Lean.Json.str (reprStr info.type)).compress)\n')
    require(bytes_at(PUBLIC + '/weakened/ExportWeakening.lean').decode() == exporter and
            public['weakened_premise_rejected_by_type_audit'] is True, 'weakening exporter/evidence differs')
    for suffix in ['OuterPublic.lean', 'OuterPublic.olean', 'ExportWeakening.lean']:
        bind(PUBLIC + '/weakened/' + suffix, 'negative_fixture', {'not_a_production_theorem': True})

    records = {PUBLIC + '/report.json', RUST + '/report.json', RUST + '/source-snapshot.json', ROCQ + '/report.json'}
    for s in public['stages']:
        log = PUBLIC + '/' + s['stage'] + '.log'
        require(sha(bytes_at(log)) == s['log_sha256'], 'public stage log hash')
        records.add(log)
        argv = s['command']
        if '-o' in argv:
            path = relative(argv[argv.index('-o') + 1])
            if path not in bindings:
                require(path in b and b[path]['kind'] == 'file', 'missing kernel output')
                bind(path, 'recorded_kernel_output', {'stage': s['stage'], 'exit_code': s['exit_code']})
    for s in rust_report['stages']:
        records.add(RUST + '/' + s['log'])
    for label in ['full-mir', 'general', 'public']:
        records.update(PUBLIC + '/' + label + suffix for suffix in ['-audit.json', '-summary.json'])
    records.update(PUBLIC + '/clean-' + label + '-audit.json' for label in ['main', 'field', 'raw'])
    for name in [RUST + '/CkbVmProduction.llbc', RUST + '/generated/CkbVmProduction.lean']:
        bind(name, 'extracted_model', {'production_report': RUST + '/report.json'})
    rocq = json.loads(bytes_at(ROCQ + '/report.json'))
    require(rocq['verdict'] == 'NO-GO' and rocq['extra_proof_coverage'] is False, 'Rocq coverage changed')
    for name, digest in rocq['model_sha256'].items():
        path = ROCQ + '/' + name
        require(sha(bytes_at(path)) == digest, 'Rocq model source identity')
        installed = 'proof/rocq/generated/sail/' + name
        if installed in bindings:
            require(bindings[installed]['category'] == 'installed_generation_output' and
                    bindings[installed]['evidence']['sha256'] == digest, 'installed Rocq model differs from spike input')
        bind(path, 'rocq_model_or_repro_source', {'extra_proof_coverage': False})
    for s in rocq['stages']:
        records.add(ROCQ + '/' + s['log'])
    for name in records:
        bytes_at(name)
        bind(name, 'execution_or_audit_record', {'formal_run': FORMAL})
    for repo in source['repositories']:
        git_bases.append(RUST + '/checkout/' + ('' if repo == '.' else repo + '/') + '.git/')

    reviews, unknown = {}, []
    for name, change in delta['changes'].items():
        try:
            row = classify(name, change, bindings, git_bases)
        except RuntimeError as error:
            unknown.append({'path': name, 'reason': str(error)})
            continue
        reviews[name] = {'change_sha256': sha(canonical(change)), **row, 'candidate_delivery_approved': False}
    require(not unknown, 'unclassified members (' + str(len(unknown)) + '): ' + json.dumps(unknown[:30]))
    require(set(reviews) == set(delta['changes']), 'review membership differs')
    facts['category_counts'] = dict(Counter(r['category'] for r in reviews.values()))
    facts['reviewed_changes'] = len(reviews)
    facts['operation_counts'] = dict(Counter(c['operation'] for c in delta['changes'].values()))
    facts['scope'] = 'complete historical formal delta only; subsequent support outputs and source updates excluded'
    facts['source_update_requirement'] = 'post-formal documentation and support-output differences require separate final-scope review'
    facts['input_sha256'] = sha((OUT / 'input.json').read_bytes())
    require(sha(regular_bytes(FORMAL + '/report.json')) == sha(report_data), 'formal record changed during review')
    return facts, reviews


def review_main():
    require(sys.argv[1:] in [[], ['--dry-run'], ['--check']], 'usage: review.py [--dry-run|--check]')
    mode = sys.argv[1:] or ['record']
    started = datetime.now(timezone.utc).isoformat()
    facts, reviews = compute()
    if mode == ['--check']:
        report = read(OUT / 'report.json')
        validate_summary(report, facts, reviews)
        require(read(OUT / 'facts.json') == facts and read(OUT / 'reviews.json') == reviews, 'recomputed review differs')
        require(sha((OUT / 'facts.json').read_bytes()) == report['facts_sha256'] and
                sha((OUT / 'reviews.json').read_bytes()) == report['reviews_sha256'] and
                sha(Path(__file__).read_bytes()) == report['reviewer_sha256'], 'review record hashes differ')
        require(test_evidence() == report['tests'], 'review test evidence differs')
        print(json.dumps({'status': 'independently_recomputed_record_bindings_match', 'changes': len(reviews), **FLAGS}))
    elif mode == ['--dry-run']:
        print(json.dumps({'status': 'read_only_diagnostic', 'facts': facts, **FLAGS}, indent=2))
    else:
        require(not any((OUT / n).exists() for n in ['facts.json', 'reviews.json', 'report.json']), 'new record only')
        tests = test_evidence()
        write('facts.json', facts)
        write('reviews.json', reviews)
        report = {'schema_version': 1, 'status': 'all_recorded_formal_deltas_explained_final_scope_pending',
                  'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
                  'reviewed_changes': len(reviews), 'categories': facts['category_counts'],
                  'formal_report_sha256': facts['formal_report_sha256'], 'delta_sha256': facts['delta_sha256'],
                  'facts_sha256': sha((OUT / 'facts.json').read_bytes()),
                  'reviews_sha256': sha((OUT / 'reviews.json').read_bytes()),
                  'reviewer_sha256': sha(Path(__file__).read_bytes()), 'tests': tests, **FLAGS}
        validate_summary(report, facts, reviews)
        write('report.json', report)
        print(json.dumps(report, indent=2))


def new_output(path, root=ROOT):
    root, path = Path(root).resolve(), Path(path).absolute()
    parent = root / 'artifacts/boundary-check'
    require(parent.is_dir() and not parent.is_symlink() and path.parent == parent and
            path.name.startswith('week6-formal-review-') and path.name != 'week6-formal-review-' and
            not path.exists() and not path.is_symlink(), 'new Week6 formal review output required')
    path.mkdir()
    return path


def copy_regular(source, destination):
    source = Path(source).absolute()
    require(source.is_file() and not source.is_symlink() and
            all(not parent.is_symlink() for parent in source.parents),
            'missing/linked formal review source')
    data = source.read_bytes()
    before = sha(data)
    with Path(destination).open('xb') as stream:
        stream.write(data)
    require(sha(source.read_bytes()) == before == sha(Path(destination).read_bytes()),
            'formal review source copy changed')


def prepare(formal_report, formal_sha, output):
    global OUT
    require(type(formal_sha) is str and re.fullmatch(r'[0-9a-f]{64}', formal_sha),
            'formal report SHA-256')
    formal_report = Path(formal_report)
    formal_report = formal_report if formal_report.is_absolute() else ROOT / formal_report
    formal_report = formal_report.absolute()
    require(formal_report.is_relative_to(ROOT) and
            sha(regular_bytes(formal_report.relative_to(ROOT).as_posix())) == formal_sha,
            'formal report input differs')
    OUT = new_output(output)
    config = {'schema_version': 1, 'kind': 'week6-formal-review-input-v1',
              'formal_report': formal_report.relative_to(ROOT).as_posix(),
              'formal_report_sha256': formal_sha}
    write('input.json', config)
    copy_regular(Path(__file__), OUT / 'review.py')
    copy_regular(ROOT / 'scripts/tests/test_week6_formal_review_logic.py', OUT / 'test_review.py')
    env = dict(os.environ)
    commands = [
        ('test-review-ordinary', ['/usr/bin/python3', '-B', str(OUT / 'test_review.py')]),
        ('test-review-optimized', ['/usr/bin/python3', '-B', '-O', str(OUT / 'test_review.py')]),
        ('record-review', ['/usr/bin/python3', '-B', '-O', str(OUT / 'review.py')]),
        ('check-review', ['/usr/bin/python3', '-B', '-O', str(OUT / 'review.py'), '--check']),
    ]
    for name, argv in commands:
        row = recording.command(OUT, name, argv, env, 7200, ROOT)
        require(row['status'] == 'completed' and row['exit_code'] == 0,
                'formal review stage failed: ' + name)
    checked = validator.check(formal_report, OUT / 'report.json', root=ROOT)
    require(checked['reviewed_changes'] > 0 and checked['fresh_execution_claimed'] is False,
            'formal review validator boundary differs')
    print(json.dumps({'status': 'formal_delta_review_validated',
                      'report': str(OUT / 'report.json'), 'checked': checked}, sort_keys=True))
    return 0


def driver_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--formal-report', type=Path, required=True)
    parser.add_argument('--formal-report-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        return prepare(args.formal_report, args.formal_report_sha256, args.out)
    except (Exception, KeyboardInterrupt) as error:
        print('week6 formal review rejected: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if OUT is None:
        sys.exit(driver_main())
    review_main()
