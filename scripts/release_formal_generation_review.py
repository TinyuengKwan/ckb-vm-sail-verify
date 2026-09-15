"""Read-only bindings for formal-execution-with-output-delta-v1.

No evidence script is imported/executed. This validates recorded observations,
commands and review membership, not review semantics, authorship, current output
identity or final delivery approval. Lean/Rocq acceptance remains a separate gate.
"""
from collections import Counter
import copy
import json
from pathlib import Path
import re

import release_generation_review as base

common, inventory = base.common, base.inventory
require, same, fields = base.require, base.same, base.fields
PRODUCER_FLAGS = {'worktree_audit_closed', 'week6_closed', 'generated_outputs_audited',
                  'whole_workspace_coverage_claimed', 'clean_room_claimed', 'release_claimed'}
REVIEW_FLAGS = base.REVIEW_FLAGS | {'clean_room_claimed', 'independent_third_party_claimed'}
CATEGORIES = {'directory', 'execution_or_audit_record', 'rocq_build_cache',
              'rocq_model_or_repro_source', 'extracted_model', 'cargo_build_cache',
              'cargo_metadata', 'locked_archive', 'registry_source', 'source_copy',
              'lean_build_cache', 'path_relocated_config', 'build_support_link',
              'git_metadata', 'locked_git_source', 'unmaterialized_gitlink',
              'lake_input_hash_metadata', 'support_source_copy', 'lower_proof_source',
              'recorded_kernel_output', 'extracted_or_linked_model', 'public_harness',
              'negative_fixture', 'retained_original', 'transaction_record',
              'installed_provenance', 'build_log', 'llbc_representation'}
ACCEPTANCE_CODE = ('import json,sys; from pathlib import Path; sys.path.insert(0,"scripts"); '
                   'import release_evidence as e; '
                   'print("FORMAL_FINAL_CHECK_JSON="+json.dumps({"lean":e.check_lean(Path(sys.argv[1])),'
                   '"rocq":e.check_rocq(Path(sys.argv[2]))},sort_keys=True))')
STAGES = ['inventory-before', 'proof-check', 'proof-spike', 'inventory-after', 'independent-acceptance']
RECORD_FILES = {'before/snapshot.json', 'before-expanded.json', 'after/snapshot.json', 'delta.json',
                'source-before.json', 'source-after.json', 'formal-inputs-before.json',
                'evidence-parent-before.json', 'evidence-parent-after.json',
                'generated-after-main.json', 'generated-after-rocq.json',
                'main-archive.json', 'previous-main-archive.json', 'run.py', 'started.json'}
for _stage in STAGES:
    RECORD_FILES.update(_stage + s for s in ['-started.json', '-process.json', '-finished.json', '.log'])
SUPPORT_FILES = {'driver-tests.json', 'test_driver.py', 'post-run-doc-fixes.md'}
for _mode in ['ordinary', 'optimized']:
    SUPPORT_FILES.update('driver-tests-' + _mode + s for s in
                         ['-started.json', '-process.json', '-finished.json', '.log'])


def expand(before, earlier, later):
    inventory.validate(before)
    require(type(earlier) is list and type(later) is list, 'invalid evidence parent inventory')
    for names in [earlier, later]:
        for name in names:
            inventory.safe(name, root_name=True)
            require('/' not in name, 'not a direct evidence child')
        require(names == sorted(set(names)), 'unordered/duplicate evidence parent inventory')
    require(set(earlier) <= set(later), 'existing evidence sibling disappeared')
    added = [base.recorder.PARENT + '/' + n for n in sorted(set(later) - set(earlier))]
    require(len(added) == 2 and sum(Path(n).name.startswith('public-check-') for n in added) == 1 and
            sum(Path(n).name.startswith(base.recorder.PREFIX) for n in added) == 1,
            'unexpected producer output roots')
    result = copy.deepcopy(before)
    result['roots'] = inventory.roots([n for n in before['roots'] if n not in inventory.CANONICAL_ROOTS] + added)
    require(not set(added).intersection(result['entries']), 'new evidence root already observed')
    result['entries'].update(dict.fromkeys(added))
    result['snapshot_sha256'] = inventory.digest({k: v for k, v in result.items() if k != 'snapshot_sha256'})
    inventory.validate(result)
    return result, added


def check(producer_path, review_path, root=None):
    root = (common.ROOT if root is None else Path(root)).absolute()
    producer_path, review_path = Path(producer_path).absolute(), Path(review_path).absolute()
    refs = base.References()
    for path in [producer_path, review_path]:
        common.member(root, path.relative_to(root).as_posix())
        refs.link(path.parent, path.name, common.sha(path))
    producer_sha = common.sha(producer_path)
    producer, review = common.read(producer_path), common.read(review_path)
    fields(producer, {'schema_version', 'kind', 'started_at', 'finished_at', 'status', 'stages', 'errors',
                     'kernel_and_rocq_records_validated', 'policy_sha256', 'source_snapshot_sha256',
                     'environment_sha256', 'new_evidence_roots', 'output_summary', 'output_changes',
                     'main_records', 'previous_main_records', 'formal_acceptance', 'record_files',
                     *PRODUCER_FLAGS}, 'formal generation record')
    require(same(producer['schema_version'], 1) and producer['kind'] == 'formal-execution-with-output-delta-v1'
            and producer['status'] == 'formal_execution_and_delta_recorded_pending_worktree_review',
            'unknown/failed formal generation record')
    require(producer['errors'] == [] and producer['kernel_and_rocq_records_validated'] is True and
            all(producer[k] is False for k in PRODUCER_FLAGS), 'formal generation assurance/status differs')
    require(type(producer['record_files']) is dict, 'invalid formal reference inventory')
    directory = producer_path.parent
    paths = {n: refs.link(directory, n, h) for n, h in producer['record_files'].items()}
    required = set(RECORD_FILES)
    for label, key in [('main', 'main_records'), ('previous-main', 'previous_main_records')]:
        archive = producer[key]
        fields(archive, {'files', 'unscanned_historical_directories', 'nested_historical_builds_copied'}, 'archive')
        require(type(archive['files']) is dict and 'report.json' in archive['files'] and
                type(archive['unscanned_historical_directories']) is list and
                archive['nested_historical_builds_copied'] is False, 'archive scope differs')
        for name in [*archive['files'], *archive['unscanned_historical_directories']]:
            inventory.safe(name)
            require('/' not in name, 'archive is not top-level')
        for name, digest in archive['files'].items():
            member = label + '/' + name
            require(producer['record_files'].get(member) == digest, 'archive reference differs')
            required.add(member)
    require(required <= paths.keys() <= required | SUPPORT_FILES, 'formal reference inventory differs')
    read = lambda n: common.read(paths[n])
    require(same(read('started.json'), {
        'schema_version': 1, 'kind': producer['kind'], 'started_at': producer['started_at'],
        'status': 'running', 'stages': [], 'errors': [], 'kernel_and_rocq_records_validated': False,
        **dict.fromkeys(PRODUCER_FLAGS, False)}), 'formal startup summary differs')
    require(type(producer['environment_sha256']) is str and
            re.fullmatch(r'[0-9a-f]{64}', producer['environment_sha256']), 'invalid recorded environment digest')
    for label, key in [('main', 'main_records'), ('previous-main', 'previous_main_records')]:
        require(same(read(label + '-archive.json'), producer[key]), 'archive summary differs')
    before, after = read('before/snapshot.json'), read('after/snapshot.json')
    rocq_root = (directory / 'rocq').relative_to(root).as_posix()
    extras = ['artifacts/rebuilt-main-runtime', rocq_root]
    require(before['roots'] == inventory.roots(extras), 'formal initial output scope differs')
    expanded, added = expand(before, read('evidence-parent-before.json'), read('evidence-parent-after.json'))
    require(same(expanded, read('before-expanded.json')) and added == producer['new_evidence_roots'],
            'expanded formal baseline differs')
    delta = inventory.compare(expanded, after)
    require(same(delta, read('delta.json')) and same(producer['output_summary'], inventory.summary(after)) and
            same(producer['output_changes'], len(delta['changes'])), 'formal delta/counters differ')
    commands = []
    for name in STAGES:
        if name.startswith('inventory-'):
            label = name.removeprefix('inventory-')
            argv = ['/usr/bin/python3', '-B', '-O', 'scripts/generated_output_inventory.py', 'capture',
                    '--out', str(directory / label)]
            for extra in (extras if label == 'before' else
                          [n for n in expanded['roots'] if n not in inventory.CANONICAL_ROOTS]):
                argv.extend(['--extra-root', extra])
        elif name == 'independent-acceptance':
            argv = ['/usr/bin/python3', '-B', '-O', '-c', ACCEPTANCE_CODE,
                    str(directory / 'main/report.json'), str(directory / 'rocq/report.json')]
        else:
            argv = ['/usr/bin/make', name] + (['BACKEND=lean'] if name == 'proof-check' else [])
        commands.append(base.command_record(read, refs, directory, name, argv, str(root)))
    require(same(commands, producer['stages']), 'formal stage inventory differs')
    previous = base.moment(producer['started_at'])
    for row in commands:
        require(previous <= base.moment(row['started_at']), 'formal stages overlap/out of order')
        previous = base.moment(row['finished_at'])
    require(previous <= base.moment(producer['finished_at']), 'formal completion precedes commands')
    marker = 'FORMAL_FINAL_CHECK_JSON='
    values = [json.loads(line[len(marker):]) for line in paths['independent-acceptance.log'].read_text().splitlines()
              if line.startswith(marker)]
    require(len(values) == 1 and same(values[0], producer['formal_acceptance']), 'acceptance log/summary differs')
    fields(values[0], {'lean', 'rocq'}, 'formal acceptance inventory')
    require(values[0]['lean']['fresh_kernel_run_claimed'] is False and
            values[0]['rocq']['extra_proof_coverage'] is False, 'record checker assurance upgrade')
    source = read('source-before.json')
    fields(source, {'schema_version', 'identity_kind', 'repositories', 'ckb_source_baseline',
                    'ignored_build_and_evidence_files_included', 'semantic_review_claimed',
                    'snapshot_sha256'}, 'historical formal source')
    require(same(source['schema_version'], 1) and
            source['identity_kind'] == 'HEAD-plus-byte-inventoried-working-tree-not-a-commit' and
            source['ignored_build_and_evidence_files_included'] is False and source['semantic_review_claimed'] is False,
            'historical formal source schema/assurance differs')
    fields(source['repositories'], base.source_review.source.REPOS, 'historical formal repositories')
    require(same(source, read('source-after.json')) and source['snapshot_sha256'] == producer['source_snapshot_sha256'] ==
            inventory.digest({k: v for k, v in source.items() if k != 'snapshot_sha256'}), 'formal source bookends/digest differ')
    files = source['repositories']['.']['files']
    require(files['proof/lean/audit/step-policy.json']['sha256'] == producer['policy_sha256'], 'formal policy/source differs')
    for name, digest in read('formal-inputs-before.json')['local_sources'].items():
        inventory.safe(name)
        require(files[name]['sha256'] == digest, 'formal input/source differs')
    generated = read('generated-after-main.json')
    require(same(generated, read('generated-after-rocq.json')), 'main/Rocq generated bookends differ')
    main = read('main/report.json')
    rocq_node = after['entries'][rocq_root + '/report.json']
    require(rocq_node['kind'] == 'file', 'Rocq report not a regular recorded file')
    rocq = common.read(refs.link(root, rocq_root + '/report.json', rocq_node['sha256']))
    for report in [main, rocq]:
        require(report['status'] == 'passed' and report['policy_sha256'] == producer['policy_sha256'] and
                same(report['generated'], generated), 'formal report/generated identity differs')
    require(rocq['verdict'] == 'NO-GO' and rocq['extra_proof_coverage'] is False, 'unsupported Rocq assurance')
    fields(generated['models'], {'rust', 'sail'}, 'generated model families')
    for family, models in generated['models'].items():
        require(type(models) is dict and models, 'empty formal model inventory')
        for name, digest in models.items():
            inventory.safe(name)
            node = after['entries']['proof/lean/generated/' + family + '/' + name]
            require(node['kind'] == 'file' and node['sha256'] == digest, 'formal model/output identity differs')
    provenance = generated['rust_provenance']
    require(generated['llbc_sha256'] == provenance['llbc_sha256'] ==
            after['entries']['target/CkbVmProduction.llbc']['sha256'], 'formal LLBC identity differs')
    extraction = provenance['rebuilt_extraction']
    require(extraction['report'] == next(n for n in added if Path(n).name.startswith(base.recorder.PREFIX)) + '/report.json'
            and after['entries'][extraction['report']]['sha256'] == extraction['report_sha256'], 'formal extraction binding differs')
    result = finish_review(review_path, review, producer, producer_sha, source, delta, expanded, after, refs, root)
    # These exact references were already verified above. The aggregate may
    # discharge execution linkage only after its independent Lean/Rocq checkers
    # have accepted the same references; this component alone cannot do that.
    result['formal_reports'] = {
        'lean': {'path': (directory / 'main/report.json').relative_to(root).as_posix(),
                 'sha256': producer['record_files']['main/report.json']},
        'rocq': {'path': rocq_root + '/report.json', 'sha256': rocq_node['sha256']}}
    return result


def finish_review(path, review, producer, producer_sha, source, delta, before, after, refs, root):
    fields(review, {'schema_version', 'started_at', 'finished_at', 'status', 'formal_report_sha256', 'delta_sha256',
                    'reviewed_changes', 'categories', 'facts_sha256', 'reviews_sha256', 'reviewer_sha256', 'tests',
                    *REVIEW_FLAGS}, 'formal delta review')
    require(same(review['schema_version'], 1) and
            review['status'] == 'all_recorded_formal_deltas_explained_final_scope_pending' and
            all(review[k] is False for k in REVIEW_FLAGS), 'formal review status/assurance differs')
    require(base.moment(producer['finished_at']) <= base.moment(review['started_at']) <=
            base.moment(review['finished_at']), 'formal review precedes execution completion')
    require(review['formal_report_sha256'] == producer_sha and
            review['delta_sha256'] == producer['record_files']['delta.json'], 'review bound to another formal run')
    directory = path.parent
    paths = {n: refs.link(directory, n, review[k]) for n, k in
             [('facts.json', 'facts_sha256'), ('reviews.json', 'reviews_sha256'), ('review.py', 'reviewer_sha256')]}
    facts, rows = common.read(paths['facts.json']), common.read(paths['reviews.json'])
    require(facts['formal_report_sha256'] == producer_sha and facts['delta_sha256'] == review['delta_sha256'] and
            facts['formal_source_snapshot_sha256'] == source['snapshot_sha256'], 'formal facts input binding differs')
    fields(rows, delta['changes'], 'exact formal review member inventory')
    for name, change in delta['changes'].items():
        row = rows[name]
        fields(row, {'change_sha256', 'category', 'evidence', 'candidate_delivery_approved'}, 'formal review entry')
        require(row['change_sha256'] == inventory.digest(change) and row['candidate_delivery_approved'] is False,
                'formal change identity/approval differs')
        require(type(row['category']) is str and row['category'] in CATEGORIES, 'unknown formal review category')
        node = change['after']
        require(node is not None and change['operation'] in ['added', 'modified'], 'unsupported formal review operation')
        if row['category'] == 'directory':
            require(node['kind'] == 'directory' and change['operation'] == 'added', 'not an added directory')
        if row['category'] == 'retained_original':
            inventory.safe(row['evidence'])
            require(same(before['entries'].get(row['evidence']), node), 'formal retained original differs')
        require(type(row['evidence']) in [str, dict] and bool(row['evidence']), 'empty formal review support')
    counts = dict(Counter(r['category'] for r in rows.values()))
    require(same(review['categories'], counts) and same(facts['category_counts'], counts) and
            same(review['reviewed_changes'], len(rows)) and same(facts['reviewed_changes'], len(rows)) and
            same(facts['operation_counts'], dict(Counter(c['operation'] for c in delta['changes'].values()))),
            'formal review counters differ')
    tests = review['tests']
    fields(tests, {'tests_per_mode', 'modes', 'files'}, 'formal review tests')
    require(type(tests['tests_per_mode']) is int and tests['tests_per_mode'] > 0 and
            tests['modes'] == ['ordinary', 'optimized'], 'formal review test inventory differs')
    required = {'test_review.py'} | {f'test-review-{mode}{suffix}' for mode in tests['modes']
                                  for suffix in ['-finished.json', '.log']}
    fields(tests['files'], required, 'formal review test references')
    for name, digest in tests['files'].items():
        refs.link(directory, name, digest)

    def read_event(name):
        return common.read(refs.link(directory, name, common.sha(common.member(directory, name))))

    stages = []
    for name, options, script in [('test-review-ordinary', [], 'test_review.py'),
                                  ('test-review-optimized', ['-O'], 'test_review.py'),
                                  ('record-review', ['-O'], 'review.py'),
                                  ('check-review', ['-O'], 'review.py')]:
        argv = ['/usr/bin/python3', '-B', *options, str(directory / script)]
        if name == 'check-review': argv.append('--check')
        row = base.command_record(read_event, refs, directory, name, argv, str(root))
        stages.append(row)
        log = common.member(directory, row['log']).read_text()
        if script == 'test_review.py':
            require(re.findall(r'(?m)^Ran (\d+) tests? in ', log) == [str(tests['tests_per_mode'])] and
                    re.search(r'(?m)^OK\s*\Z', log), 'formal review tests not completed')
        elif name == 'record-review':
            require(same(json.loads(log), review), 'record-review log differs')
        else:
            require(same(json.loads(log), {'status': 'independently_recomputed_record_bindings_match',
                                          'changes': len(rows), **dict.fromkeys(REVIEW_FLAGS, False)}),
                    'independent review completion marker differs')
    for first, second in zip(stages, stages[1:]):
        require(base.moment(first['finished_at']) <= base.moment(second['started_at']), 'review stages overlap/out of order')
    require(base.moment(producer['finished_at']) <= base.moment(stages[0]['started_at']),
            'review tests precede formal completion')
    require(base.moment(stages[2]['started_at']) <= base.moment(review['started_at']) <=
            base.moment(review['finished_at']) <= base.moment(stages[2]['finished_at']), 'review outside recorded command')
    refs.recheck()
    return {'scope': 'historical_formal_execution_and_complete_delta_review_bindings_only',
            'reviewed_changes': len(rows), 'reference_files': len(refs.items),
            'source_snapshot_sha256': source['snapshot_sha256'],
            'generated_identities_sha256': producer['record_files']['generated-after-rocq.json'],
            'recorded_main_rocq_generated_identity_matches': True,
            'review_semantics_revalidated': False, 'record_authorship_authenticated': False,
            'fresh_execution_claimed': False, **dict.fromkeys(REVIEW_FLAGS, False)}
