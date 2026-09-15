"""Exact historical-scope projection of a larger current observation.

Additional roots have no invented historical baseline. A missing child under an
observed directory is an observed absent root; a root outside coverage is not.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve()
ROOT = (HERE.parent.parents[2] if HERE.parent.parent.name == 'boundary-check' else HERE.parent.parent)
sys.path.insert(0, str(ROOT / 'scripts'))
import generated_output_inventory as inventory


def project(observed, selected):
    inventory.validate(observed)
    inventory.require(selected == inventory.roots([r for r in selected if r not in inventory.CANONICAL_ROOTS]),
                      'invalid projection scope')
    for root in selected:
        owners = [r for r in observed['roots'] if root == r or root.startswith(r + '/')]
        inventory.require(len(owners) == 1, 'projection root not covered by current observation')
        ancestor = owners[0]
        while ancestor != root:
            node = observed['entries'].get(ancestor)
            if node is None:
                break
            inventory.require(node['kind'] == 'directory',
                              'projection crosses a non-directory or symlink ancestor')
            ancestor = root[:root.find('/', len(ancestor) + 1)] if '/' in root[len(ancestor) + 1:] else root
    entries = {name: row for name, row in observed['entries'].items()
               if any(name == r or name.startswith(r + '/') for r in selected)}
    for root in selected:
        if root not in entries:
            # Coverage is established by complete traversal of its owner above;
            # absence is current observation only, never a fabricated old state.
            entries[root] = None
    result = {k: observed[k] for k in ['schema_version', 'kind', 'symlinks_followed',
                                      'whole_workspace_coverage_claimed']}
    result.update(roots=list(selected), entries=entries)
    result['snapshot_sha256'] = inventory.digest(result)
    inventory.validate(result)
    return result
