"""Validate v1 bundles with JSON Schema and cross-record integrity checks."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

SCHEMAS = Path(__file__).parent / 'v1'


class ContractError(ValueError):
    """A bundle cannot be consumed safely by migration tasks."""


def validate_document(name, document):
    schema = json.loads((SCHEMAS / f'{name}.schema.json').read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda e: str(e.path))
    if errors:
        error = errors[0]
        raise ContractError(f'{name}: {list(error.path)}: {error.message}')


def unique(records, field, label):
    values = [record[field] for record in records]
    if len(values) != len(set(values)):
        raise ContractError(f'duplicate {label}')
    return set(values)


def validate_bundle(content, assets, routes):
    """Reject broken references/collisions in addition to structural errors."""
    for name, document in [('content', content), ('assets', assets), ('routes', routes)]:
        validate_document(name, document)
    items, media, paths = content['items'], assets['assets'], routes['routes']
    content_ids = unique(items, 'sourceId', 'content source ID')
    asset_ids = unique(media, 'assetId', 'asset ID')
    unique(items, 'path', 'content path')
    unique(media, 'localPath', 'asset destination')
    route_keys = [(r['path'], r['query']) for r in paths]
    if len(route_keys) != len(set(route_keys)):
        raise ContractError('duplicate route path/query')
    destinations = {r['path'] for r in paths if not r['query']}
    content_routes = {(r['contentId'], r['path']) for r in paths if r['kind'] == 'content'}
    for item in items:
        if urlsplit(item['canonicalUrl']).path != item['path']:
            raise ContractError(f'canonical path differs: {item["sourceId"]}')
        if set(item['assetIds']) - asset_ids:
            raise ContractError(f'unknown asset reference: {item["sourceId"]}')
        if (item['sourceId'], item['path']) not in content_routes:
            raise ContractError(f'missing content route: {item["sourceId"]}')
    for route in paths:
        if 'contentId' in route and route['contentId'] not in content_ids:
            raise ContractError('unknown route content ID')
        if 'target' in route and route['target'] not in destinations:
            raise ContractError('unknown route target')
        if route.get('target') == route['path'] and not route['query']:
            raise ContractError('route redirects to itself')


def load_bundle(directory):
    directory = Path(directory)
    documents = [json.loads((directory / f'{name}.json').read_text())
                 for name in ('content', 'assets', 'routes')]
    validate_bundle(*documents)
    return documents


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    load_bundle(args.directory)
    print('Contract bundle is valid; source completeness is a separate gate.')
