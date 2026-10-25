"""Compare a frozen source inventory to normalized bundles without claiming fidelity."""
from collections import Counter

from docs.contracts.validate import ContractError, load_bundle

DIMENSIONS = ('contentIds', 'assetIds', 'routeKeys')
REQUIRED_INPUTS = ('wxr', 'uploads', 'renderedSnapshots', 'themeSettings')


def difference(expected, actual):
    """Keep denominators and duplicate evidence; set equality alone hides duplicates."""
    wanted, found = Counter(expected), Counter(actual)
    return {
        'expectedCount': len(expected), 'actualCount': len(actual),
        'missing': sorted(wanted.keys() - found.keys()),
        'unexpected': sorted(found.keys() - wanted.keys()),
        'duplicateExpected': sorted(k for k, count in wanted.items() if count > 1),
        'duplicateActual': sorted(k for k, count in found.items() if count > 1),
    }


def reconcile(baseline, documents):
    """The owner baseline is separate from public discovery; absent input is unknown."""
    if baseline.get('schemaVersion') != '1.0.0':
        raise ContractError('inventory: unsupported schemaVersion')
    for dimension in DIMENSIONS:
        value = baseline.get(dimension)
        if value is not None and (
            not isinstance(value, list) or any(not isinstance(v, str) for v in value)
        ):
            raise ContractError(f'inventory: {dimension} must be a string array or null')
    content, assets, routes = documents
    actual = {
        'contentIds': [r['sourceId'] for r in content['items'] if r['status'] == 'publish'],
        'assetIds': [r['assetId'] for r in assets['assets']],
        'routeKeys': [r['path'] + ('?' + r['query'] if r['query'] else '')
                      for r in routes['routes']],
    }
    comparisons = {
        name: difference(baseline[name], actual[name]) if baseline.get(name) is not None
        else {'status': 'unknown', 'actualCount': len(actual[name])}
        for name in DIMENSIONS
    }
    missing_inputs = [name for name in REQUIRED_INPUTS
                      if not baseline.get('inputs', {}).get(name)]
    if not baseline.get('sourceFrozenAt'):
        missing_inputs.append('sourceFrozenAt')
    expected_bytes = baseline.get('totalMediaBytes')
    if expected_bytes is not None and (
        isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int)
        or expected_bytes < 0
    ):
        raise ContractError('inventory: totalMediaBytes must be a nonnegative integer or null')
    measured_bytes = sum(a['bytes'] for a in assets['assets'] if a['owned'])
    matched = all(
        'status' not in item and not any(item[key] for key in (
            'missing', 'unexpected', 'duplicateExpected', 'duplicateActual'
        )) for item in comparisons.values()
    )
    return {
        'schemaVersion': '1.0.0',
        'sourceCompleteness': 'unverified',
        'comparisons': comparisons,
        'media': {'expectedBytes': expected_bytes, 'manifestOwnedBytes': measured_bytes,
                  'matches': expected_bytes is not None and expected_bytes == measured_bytes},
        'missingInputs': missing_inputs,
        'readyForSourceAudit': matched and not missing_inputs and expected_bytes == measured_bytes,
    }


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    report = reconcile(json.loads(args.baseline.read_text()), load_bundle(args.bundle))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report['readyForSourceAudit'] else 1)
