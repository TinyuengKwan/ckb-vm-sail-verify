"""Validate the source portion of a worktree review; never close its release slot.

Recompute the complete source snapshot, not just the formal policy's file list.
Every HEAD delta must have a byte-bound review entry and supporting references.
References and reviewer names are records, not authenticated semantic approval.
Ignored generated outputs, regeneration deltas and candidate approval require
separate evidence; accepting this component cannot certify a release.
"""
from pathlib import Path

import release_evidence as common
import source_snapshot as source

ROOT = common.ROOT
require, same = common.require, common.same
KINDS = {'production', 'proof', 'test', 'build', 'documentation', 'historical', 'mixed'}
BOUNDARIES = {'release_claimed', 'week6_closed', 'generated_outputs_audited',
              'candidate_approval_claimed', 'semantic_correctness_proven'}
REMAINING = ['ignored_generated_output_inventory_and_regeneration_deltas',
             'final_delivery_scope_and_semantic_approval']


def fields(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), 'invalid ' + label + ' fields')


def text(value, label):
    require(type(value) is str and value.strip(), 'missing ' + label)


def check(path, candidate, root=None):
    """Read-only, source-only validation. Caller must keep worktree_audit incomplete."""
    root = ROOT if root is None else Path(root)
    path = Path(path)
    text(candidate, 'candidate')
    report_sha = common.sha(path)
    report = common.read(path)
    fields(report, {'schema_version', 'kind', 'candidate', 'snapshot', 'reviews', 'boundaries'},
           'source review')
    require(same(report['schema_version'], 1) and report['kind'] == 'worktree-source-review-v1',
            'unknown source review schema/kind')
    require(report['candidate'] == candidate, 'source review belongs to a different candidate')
    fields(report['boundaries'], BOUNDARIES, 'source review boundary')
    require(all(value is False for value in report['boundaries'].values()),
            'source review cannot claim generated/semantic/candidate/release approval')

    references = {}

    def reference(row):
        fields(row, {'path', 'sha256'}, 'source review reference')
        linked = common.linked(root, row['path'], row['sha256'])
        require(row['path'] not in references or references[row['path']] == row['sha256'],
                'conflicting source review reference')
        references[row['path']] = row['sha256']
        return linked

    recorded = common.read(reference(report['snapshot']))
    current = source.capture(root)
    require(same(recorded, current), 'source review snapshot differs from current complete source inventory')
    # capture() independently checks Git bases, submodules, byte/mode changes and
    # the adopted CKB patch; the report cannot choose a smaller repository scope.
    fields(report['reviews'], source.REPOS, 'repository review inventory')
    changes = 0
    for repo in source.REPOS:
        expected = current['repositories'][repo]['changes_from_head']
        reviews = report['reviews'][repo]
        fields(reviews, expected, 'HEAD change review inventory: ' + repo)
        for name, delta in expected.items():
            row = reviews[name]
            fields(row, {'change_sha256', 'category', 'rationale', 'reviewed_by', 'evidence'},
                   'change review: ' + repo + '/' + name)
            require(row['change_sha256'] == source.digest(source.canonical(delta)),
                    'review bound to a different source change: ' + name)
            require(type(row['category']) is str and row['category'] in KINDS,
                    'unknown source review category')
            text(row['rationale'], 'change rationale')
            text(row['reviewed_by'], 'reviewer record')
            require(type(row['evidence']) is list and row['evidence'], 'missing change review evidence')
            paths = []
            for item in row['evidence']:
                reference(item)
                paths.append(item['path'])
            require(len(paths) == len(set(paths)), 'duplicate change review evidence')
            changes += 1

    # Recheck all referenced paths (including symlink checks), the top-level
    # report and the full current tree after traversal. No recorded commands run.
    for name, digest in references.items():
        common.linked(root, name, digest)
    require(common.sha(path) == report_sha, 'source review report changed during validation')
    require(same(source.capture(root), current), 'source changed during review validation')
    return {'scope': 'existing_complete_source_inventory_and_review_records_only',
            'candidate': candidate, 'source_snapshot_sha256': current['snapshot_sha256'],
            'source_files': sum(len(r['files']) for r in current['repositories'].values()),
            'reviewed_head_changes': changes, 'reference_files': len(references),
            'remaining': list(REMAINING), 'worktree_audit_closed': False,
            'reviewer_identity_authenticated': False,
            'fresh_execution_claimed': False, **{key: False for key in BOUNDARIES}}
