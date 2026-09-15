"""Read-only validation of recorded generation/delta review bindings.

Does not rerun the review driver, generators, tools or kernels. In particular,
valid records do not authenticate their author or prove current output identity,
review rationale, CMake/archive semantics, or final candidate approval.
"""
from collections import Counter
from datetime import datetime
from pathlib import Path

import generated_output_inventory as inventory
import record_generation as recorder
import release_evidence as common
import release_worktree_source as source_review

require, same, fields = common.require, common.same, source_review.fields
REVIEW_FLAGS = {'whole_current_output_tree_rehashed', 'candidate_approval_claimed',
                'generated_outputs_audited', 'worktree_audit_closed', 'kernel_executed',
                'release_claimed', 'week6_closed'}
CATEGORIES = {'directory', 'extraction_record', 'build_cache', 'registry_metadata',
              'locked_archive', 'registry_source', 'git_metadata', 'source_copy',
              'retained_original', 'cmake_dependencies', 'transaction_record',
              'relocated_original', 'installed_provenance', 'llbc_representation'}
COMMANDS = [('sail-config', ['/usr/bin/make', 'sail-config']),
            ('generate-rust', ['/usr/bin/python3', 'scripts/generate_rebuilt_rust.py']),
            ('generate-sail-lean', ['/bin/bash', 'scripts/generate_proof_model.sh', 'lean']),
            ('generate-sail-rocq', ['/bin/bash', 'scripts/generate_proof_model.sh', 'rocq'])]
RECORD_FILES = {'before/snapshot.json', 'before-expanded.json', 'after/snapshot.json',
                'delta.json', 'source-before.json', 'source-after.json',
                'evidence-parent-before.json', 'evidence-parent-after.json',
                'formal-inputs-before.json', 'generated-identities.json', 'sail-transactions.json'}
for _name in ['inventory-before', *[n for n, _ in COMMANDS], 'inventory-after']:
    RECORD_FILES.update({_name + suffix for suffix in
                         ['-started.json', '-process.json', '-finished.json', '.log']})


def moment(value):
    require(type(value) is str, 'invalid timestamp')
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, 'timestamp lacks timezone')
    return result


class References:
    def __init__(self):
        self.items = {}

    def link(self, directory, name, digest):
        path = common.linked(directory, name, digest)
        key = (Path(directory), name)
        require(key not in self.items or self.items[key] == digest, 'conflicting reference')
        self.items[key] = digest
        return path

    def recheck(self):
        for (directory, name), digest in self.items.items():
            common.linked(directory, name, digest)


def command_record(read, references, directory, name, argv, cwd):
    row = read(name + '-finished.json')
    base = {'name', 'argv', 'cwd', 'started_at', 'timeout_seconds', 'exit_code', 'status', 'log'}
    fields(row, base | {'pid', 'finished_at', 'log_sha256'}, 'finished command')
    require(row['name'] == name and row['argv'] == argv and row['cwd'] == cwd,
            'unexpected recorded command/working directory')
    require(row['status'] == 'completed' and same(row['exit_code'], 0), 'command not completed')
    require(type(row['pid']) is int and row['pid'] > 0 and
            type(row['timeout_seconds']) is int and row['timeout_seconds'] > 0, 'invalid process record')
    require(row['log'] == name + '.log', 'command log name differs')
    references.link(directory, row['log'], row['log_sha256'])
    initial = {k: row[k] for k in base}
    initial.update(exit_code=None, status='starting')
    require(same(read(name + '-started.json'), initial), 'startup record differs')
    require(same(read(name + '-process.json'), {**initial, 'pid': row['pid']}), 'process record differs')
    require(moment(row['started_at']) <= moment(row['finished_at']), 'command timestamps reversed')
    return row


def check(producer_path, review_path, root=None):
    """Validate historical records only. root supplies recorded command cwd."""
    root = (common.ROOT if root is None else Path(root)).absolute()
    producer_path, review_path = Path(producer_path).absolute(), Path(review_path).absolute()
    for path in [producer_path, review_path]:
        common.member(root, path.relative_to(root).as_posix())
    refs = References()
    producer_sha, review_sha = common.sha(producer_path), common.sha(review_path)
    refs.link(producer_path.parent, producer_path.name, producer_sha)
    refs.link(review_path.parent, review_path.name, review_sha)
    producer, review = common.read(producer_path), common.read(review_path)
    if type(producer) is dict and producer.get('kind') == 'formal-execution-with-output-delta-v1':
        import release_formal_generation_review as formal
        return formal.check(producer_path, review_path, root=root)
    fields(producer, {'schema_version', 'kind', 'started_at', 'finished_at', 'status', 'stages',
                     'generation_commands_completed', 'policy_sha256', 'environment_sha256',
                     'environment_values_published', 'new_staging_roots', 'source_bookends_match',
                     'output_summary', 'changes', 'output_scope_is_whole_workspace', 'references',
                     *recorder.FLAGS}, 'generation record')
    require(same(producer['schema_version'], 1) and producer['kind'] == 'generation-execution-record-v1'
            and producer['status'] == 'generation_sequence_recorded_pending_review', 'unknown/failed generation record')
    require(all(producer[k] is False for k in (*recorder.FLAGS, 'environment_values_published',
                                             'output_scope_is_whole_workspace')), 'generation assurance upgrade')
    require(producer['generation_commands_completed'] is True and producer['source_bookends_match'] is True,
            'generation sequence/source bookends incomplete')
    fields(producer['references'], RECORD_FILES, 'generation reference inventory')
    paths = {n: refs.link(producer_path.parent, n, d) for n, d in producer['references'].items()}
    read = lambda name: common.read(paths[name])
    before, after = read('before/snapshot.json'), read('after/snapshot.json')
    inventory.validate(before)
    require(before['roots'] == inventory.roots(recorder.EXTRAS), 'initial output scope differs')
    expanded, added = recorder.expand_before(before, read('evidence-parent-before.json'),
                                             read('evidence-parent-after.json'))
    require(len(added) == 1 and added == producer['new_staging_roots'], 'fresh staging root differs')
    require(same(expanded, read('before-expanded.json')), 'invented expanded baseline')
    delta = inventory.compare(expanded, after)
    require(same(delta, read('delta.json')), 'recorded delta differs from complete observations')
    require(same(producer['output_summary'], inventory.summary(after)) and
            same(producer['changes'], len(delta['changes'])), 'output counters differ')
    commands = []
    for label, extras in [('before', recorder.EXTRAS), ('after', [*recorder.EXTRAS, *added])]:
        argv = ['/usr/bin/python3', '-B', '-O', 'scripts/generated_output_inventory.py', 'capture',
                '--out', str(producer_path.parent / label)]
        for name in extras:
            argv.extend(['--extra-root', name])
        # Recorder sorts extras when constructing the final capture command.
        if label == 'after':
            argv = argv[:7]
            for name in expanded['roots']:
                if name not in inventory.CANONICAL_ROOTS:
                    argv.extend(['--extra-root', name])
        commands.append(command_record(read, refs, producer_path.parent, 'inventory-' + label, argv, str(root)))
    stages = [command_record(read, refs, producer_path.parent, n, a, str(root)) for n, a in COMMANDS]
    require(same(stages, producer['stages']), 'generation stage inventory differs')
    previous = moment(producer['started_at'])
    for row in [commands[0], *stages, commands[1]]:
        require(previous <= moment(row['started_at']), 'recorded stages overlap/out of order')
        previous = moment(row['finished_at'])
    require(previous <= moment(producer['finished_at']), 'generation ends before stages')
    source = read('source-before.json')
    fields(source, {'schema_version', 'identity_kind', 'repositories', 'ckb_source_baseline',
                    'ignored_build_and_evidence_files_included', 'semantic_review_claimed',
                    'snapshot_sha256'}, 'historical source snapshot')
    require(same(source['schema_version'], 1) and
            source['identity_kind'] == 'HEAD-plus-byte-inventoried-working-tree-not-a-commit' and
            source['ignored_build_and_evidence_files_included'] is False and
            source['semantic_review_claimed'] is False, 'historical source assurance/schema differs')
    require(same(source, read('source-after.json')), 'generation source snapshots differ')
    require(source['snapshot_sha256'] == inventory.digest({k: v for k, v in source.items()
                                                          if k != 'snapshot_sha256'}), 'source digest differs')
    fields(source['repositories'], source_review.source.REPOS, 'recorded source repositories')
    require(source['repositories']['.']['files']['proof/lean/audit/step-policy.json']['sha256'] ==
            producer['policy_sha256'], 'recorded policy/source mismatch')
    generated = read('generated-identities.json')
    extraction = generated['rust_provenance']['rebuilt_extraction']
    require(extraction['report'] == added[0] + '/report.json', 'provenance points to another extraction')
    require(after['entries'][extraction['report']]['sha256'] == extraction['report_sha256'],
            'extraction report identity differs')
    require(generated['llbc_sha256'] == generated['rust_provenance']['llbc_sha256'] ==
            after['entries']['target/CkbVmProduction.llbc']['sha256'], 'LLBC identity differs')
    fields(generated['models'], {'rust', 'sail'}, 'model families')
    for family, models in generated['models'].items():
        require(type(models) is dict and models, 'empty recorded model inventory')
        for name, digest in models.items():
            inventory.safe(name)
            require(after['entries']['proof/lean/generated/' + family + '/' + name]['sha256'] == digest,
                    'model identity differs from output observation')
    fields(review, {'started_at', 'finished_at', 'status', 'producer_report_sha256', 'delta_sha256',
                    'reviewed_changes', 'categories', 'facts_sha256', 'reviews_sha256', 'driver_sha256',
                    *REVIEW_FLAGS}, 'generated review')
    require(review['status'] == 'all_recorded_deltas_explained_delivery_and_kernel_pending' and
            all(review[k] is False for k in REVIEW_FLAGS), 'review status/assurance upgrade')
    require(moment(producer['finished_at']) <= moment(review['started_at']) <= moment(review['finished_at']),
            'review precedes generation completion')
    require(review['producer_report_sha256'] == producer_sha and
            review['delta_sha256'] == producer['references']['delta.json'], 'review bound to another generation')
    review_files = {n: refs.link(review_path.parent, n, review[k]) for n, k in
                   [('facts.json', 'facts_sha256'), ('reviews.json', 'reviews_sha256'), ('review.py', 'driver_sha256')]}
    # The driver and facts are hash-bound supporting records, never executed or
    # treated as independently verified semantic facts by this validator.
    reviews = common.read(review_files['reviews.json'])
    fields(reviews, delta['changes'], 'exact generated review member inventory')
    for name, change in delta['changes'].items():
        row = reviews[name]
        fields(row, {'change_sha256', 'category', 'rationale', 'evidence', 'candidate_delivery_approved'},
               'generated review entry')
        require(row['change_sha256'] == inventory.digest(change), 'review change digest differs')
        require(type(row['category']) is str and row['category'] in CATEGORIES, 'unknown review category')
        source_review.text(row['rationale'], 'review rationale')
        require(row['candidate_delivery_approved'] is False, 'review claims delivery approval')
        category, support = row['category'], row['evidence']
        if category == 'directory':
            require(support is None and change['after'] is not None and
                    change['after']['kind'] == 'directory', 'not a directory change')
        elif category in {'retained_original', 'relocated_original'}:
            inventory.safe(support)
            observed, nodes = ((change['after'], expanded['entries']) if category == 'retained_original'
                               else (change['before'], after['entries']))
            require(observed is not None and support in nodes and same(observed, nodes[support]), 'backup mapping differs')
        elif category == 'source_copy':
            fields(support, {'repository', 'source', 'sha256'}, 'source copy evidence')
            require(support['repository'] in source['repositories'], 'unknown copied repository')
            inventory.safe(support['source'])
            original = source['repositories'][support['repository']]['files'][support['source']]
            node = change['after']
            require(node['kind'] == 'file' and node['sha256'] == original['sha256'] == support['sha256']
                    and same(node['size'], original['size']) and
                    bool(node['mode'] & 0o111) == (original['mode'] == '100755'), 'source copy differs')
        elif support is not None:
            inventory.safe(support)
            require(support in after['entries'] or support in expanded['entries'], 'unbound review support path')
    require(same(review['categories'], dict(Counter(r['category'] for r in reviews.values()))) and
            same(review['reviewed_changes'], len(reviews)), 'review counters differ')
    refs.recheck()
    return {'scope': 'historical_generation_records_and_complete_delta_review_bindings_only',
            'reviewed_changes': len(reviews), 'reference_files': len(refs.items),
            'source_snapshot_sha256': source['snapshot_sha256'],
            'generated_identities_sha256': producer['references']['generated-identities.json'],
            'review_semantics_revalidated': False, 'record_authorship_authenticated': False,
            'fresh_execution_claimed': False, **dict.fromkeys(REVIEW_FLAGS, False)}
