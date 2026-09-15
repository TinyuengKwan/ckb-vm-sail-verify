"""Complete source-snapshot increment bindings, not semantic/delivery approval.

Both endpoints must match independently validated generation/current-source
components. No arbitrary subset, base change, omitted reversal or mode-only
change may disappear. Evidence commands are never executed.
"""
from collections import Counter
from pathlib import Path
import re

import release_evidence as common
import release_generation_review as generation
import release_worktree_source as source

require, same, fields = common.require, common.same, source.fields
FLAGS = source.BOUNDARIES | {'fresh_execution_claimed', 'historical_generation_source_replaced',
                            'current_outputs_verified'}


def validate_snapshot(snapshot):
    fields(snapshot, {'schema_version', 'identity_kind', 'repositories', 'ckb_source_baseline',
                      'ignored_build_and_evidence_files_included', 'semantic_review_claimed',
                      'snapshot_sha256'}, 'source increment snapshot')
    require(same(snapshot['schema_version'], 1) and
            snapshot['identity_kind'] == 'HEAD-plus-byte-inventoried-working-tree-not-a-commit' and
            snapshot['ignored_build_and_evidence_files_included'] is False and
            snapshot['semantic_review_claimed'] is False, 'source increment snapshot assurance/schema differs')
    require(snapshot['snapshot_sha256'] == source.source.digest(source.source.canonical(
        {k: v for k, v in snapshot.items() if k != 'snapshot_sha256'})), 'source increment snapshot digest differs')
    fields(snapshot['repositories'], source.source.REPOS, 'source increment repositories')
    for repo, state in snapshot['repositories'].items():
        fields(state, {'head', 'gitlinks', 'files', 'changes_from_head'}, 'source increment repository')
        require(type(state['head']) is str and re.fullmatch(r'[0-9a-f]{40}', state['head']), 'invalid source HEAD')
        require(type(state['gitlinks']) is dict and type(state['files']) is dict and
                type(state['changes_from_head']) is dict, 'invalid source repository inventory')
        for name, node in state['files'].items():
            source.source.safe(name)
            fields(node, {'mode', 'size', 'sha256'}, 'source increment file')
            require(node['mode'] in ['100644', '100755'] and type(node['size']) is int and node['size'] >= 0 and
                    type(node['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', node['sha256']), 'invalid source file identity')
        if repo == '.':
            fields(state['gitlinks'], source.source.REPOS[1:], 'root source gitlinks')
            for child, revision in state['gitlinks'].items():
                require(revision == snapshot['repositories'][child]['head'], 'source submodule revision differs')
        else:
            require(not state['gitlinks'], 'nested source gitlinks not supported')


def compare(before, after):
    for snapshot in [before, after]: validate_snapshot(snapshot)
    require(same(before['ckb_source_baseline'], after['ckb_source_baseline']), 'source increment changes adopted baseline')
    changes = {}
    for repo in source.source.REPOS:
        left, right = before['repositories'][repo], after['repositories'][repo]
        require(left['head'] == right['head'] and same(left['gitlinks'], right['gitlinks']),
                'source increment changes Git base or submodule pins')
        changes[repo] = {}
        for name in sorted(left['files'].keys() | right['files'].keys()):
            old, new = left['files'].get(name), right['files'].get(name)
            if same(old, new): continue
            changes[repo][name] = {'operation': 'added' if old is None else 'deleted' if new is None else 'modified',
                                   'before': old, 'after': new}
    return changes


def check(path, candidate, before_identity, after_identity, root=None):
    root = common.ROOT if root is None else Path(root)
    path = Path(path)
    refs = generation.References()
    refs.link(path.parent, path.name, common.sha(path))
    report = common.read(path)
    fields(report, {'schema_version', 'kind', 'candidate', 'before', 'after', 'changes', 'reviews', 'boundaries'},
           'source increment review')
    require(same(report['schema_version'], 1) and report['kind'] == 'worktree-source-increment-review-v1',
            'unknown source increment schema/kind')
    source.text(candidate, 'candidate')
    require(report['candidate'] == candidate, 'source increment belongs to a different candidate')
    fields(report['boundaries'], FLAGS, 'source increment boundaries')
    require(all(v is False for v in report['boundaries'].values()), 'source increment assurance upgrade')

    def reference(row):
        fields(row, {'path', 'sha256'}, 'source increment reference')
        return refs.link(root, row['path'], row['sha256'])

    before, after = [common.read(reference(report[key])) for key in ['before', 'after']]
    changes = compare(before, after)
    require(before['snapshot_sha256'] == before_identity and after['snapshot_sha256'] == after_identity,
            'source increment endpoints differ from validated components')
    require(same(after, source.source.capture(root)), 'source increment after is not the complete current source')
    require(same(changes, report['changes']), 'source increment is not the complete snapshot comparison')
    fields(report['reviews'], source.source.REPOS, 'source increment review repositories')
    count, operations = 0, Counter()
    for repo in source.source.REPOS:
        rows = report['reviews'][repo]
        fields(rows, changes[repo], 'source increment review membership')
        for name, change in changes[repo].items():
            row = rows[name]
            fields(row, {'change_sha256', 'category', 'rationale', 'reviewed_by', 'evidence'}, 'source increment review row')
            require(row['change_sha256'] == source.source.digest(source.source.canonical(change)), 'source increment change digest differs')
            require(type(row['category']) is str and row['category'] in source.KINDS, 'unknown source increment category')
            source.text(row['rationale'], 'increment rationale')
            source.text(row['reviewed_by'], 'increment reviewer record')
            require(type(row['evidence']) is list and row['evidence'], 'missing increment review evidence')
            names = []
            for item in row['evidence']:
                reference(item)
                names.append(item['path'])
            require(len(names) == len(set(names)), 'duplicate increment support reference')
            count += 1
            operations[change['operation']] += 1
    refs.recheck()
    require(same(after, source.source.capture(root)), 'source changed during increment validation')
    return {'scope': 'complete_source_increment_and_review_bindings_only', 'candidate': candidate,
            'before_snapshot_sha256': before_identity, 'after_snapshot_sha256': after_identity,
            'reviewed_changes': count, 'operations': dict(operations), 'reference_files': len(refs.items),
            'review_semantics_revalidated': False, 'record_authorship_authenticated': False,
            **dict.fromkeys(FLAGS, False)}
