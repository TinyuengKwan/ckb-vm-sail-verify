#!/usr/bin/env python3
"""Source-only review freshness preflight, NOT the public-claims release gate.

No generated files or installed toolchains are needed. This never updates the
review inventory, validates execution evidence, or closes an acceptance slot.
The full public-claims checker still runs after regeneration in the guest.
"""
import argparse
import json
from pathlib import Path

import release_public_claims as claims

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'docs/release/public-claims-current-v1.json'


def check(root=ROOT):
    root = Path(root).resolve()
    before = claims.source.capture(root)
    path = claims.common.member(root, MANIFEST)
    digest = claims.sha(path)
    manifest = claims.common.read(path)
    claims.require(claims.same(manifest.get('schema_version'), 1) and
                   manifest.get('kind') == 'public-claims-review-v1' and
                   manifest.get('review_complete') is True, 'source review schema/completion differs')
    documents = manifest.get('documents')
    expected = claims.markdown_files(before)
    claims.require(type(documents) is dict and sorted(documents) == expected,
                   'source review Markdown inventory differs')
    bodies, paragraphs = [], 0
    for name in expected:
        body, rows = claims.validate_document_record(root, name, documents[name])
        bodies.append(body)
        paragraphs += len(rows)
    forbidden = manifest.get('forbidden_overclaims')
    claims.require(type(forbidden) is list and forbidden and
                   all(type(item) is str and item.strip() for item in forbidden),
                   'source review forbidden claim inventory differs')
    combined = '\n'.join(bodies)
    for phrase in [*claims.STALE_EXACT, *forbidden]:
        claims.require(phrase not in combined, 'forbidden/stale public claim: ' + phrase)
    claims.require(claims.source.capture(root) == before and claims.sha(path) == digest,
                   'source review inputs changed during preflight')
    return {'status': 'source_review_freshness_verified', 'documents': len(expected),
            'claim_paragraphs': paragraphs, 'review_manifest_sha256': digest,
            'source_snapshot_sha256': before['snapshot_sha256'],
            'scope': 'source_document_hashes_paragraphs_classification_and_review_only',
            'generated_links_checked': False, 'execution_evidence_checked': False,
            'public_claims_slot_closed': False, 'release_claimed': False, 'week6_closed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(check(args.root), indent=2))


if __name__ == '__main__':
    main()
