"""Owner-directed CKB Spark delivery scope, not evidence of recipient acceptance.

On 2026-09-28 the owner moved third-party reproduction to post-delivery CKB
review. No manifest switch can defer any other slot or waive supplied evidence.
The old twelve-slot inventory is retained for transparent evidence accounting.
"""

SCOPE = 'ckb-spark-delivery-v1'


def third_party_deferred():
    return {'status': 'deferred_to_recipient',
            'recipient': 'CKB official', 'timing': 'post_delivery',
            'reproduction_status': 'not_verified',
            'reason': 'Owner-directed post-delivery reproduction; not a claim of CKB acceptance or execution.'}


def boundary(checks):
    """Derive blocking and non-blocking gaps from validated slot results."""
    deferred = []
    for name, row in checks.items():
        if row.get('status') == 'deferred_to_recipient':
            if name != 'third_party' or row != third_party_deferred():
                raise RuntimeError('unauthorized delivery deferral: ' + name)
            deferred.append(name)
    outstanding = [name for name, row in checks.items()
                   if row.get('status') != 'verified_existing_evidence']
    return {'acceptance_scope': SCOPE,
            'delivery_outstanding': [name for name in outstanding if name not in deferred],
            'post_delivery': deferred,
            'third_party_reproduced': checks.get('third_party', {}).get('status') == 'verified_existing_evidence'}


def validate_boundary(report):
    """Consumers must not turn a deferred slot into verified or hide other gaps."""
    expected = boundary(report['checks'])
    for name, value in expected.items():
        actual = report.get(name)
        if type(actual) is not type(value) or actual != value:
            raise RuntimeError('delivery boundary differs: ' + name)
    return expected
