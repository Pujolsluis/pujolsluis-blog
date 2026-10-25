"""Derive exact content routes and anchor identities from rendered HTML."""

from html.parser import HTMLParser

from docs.contracts.validate import validate_document


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for value in dict.fromkeys((attrs.get('id'), attrs.get('name') if tag == 'a' else None)):
            if value:
                if value in self.values:
                    raise ValueError(f'duplicate rendered anchor {value}')
                self.values.append(value)

    handle_startendtag = handle_starttag


def routes_from_content(bundle):
    """Return only WXR-backed content routes; archive/alias routes are MIG-05's work."""
    validate_document('content', bundle)
    routes = []
    seen = set()
    for item in bundle['items']:
        if item['status'] != 'publish':
            raise ValueError(f'{item["sourceId"]}: nonpublic route is forbidden')
        if item['path'] in seen:
            raise ValueError(f'{item["sourceId"]}: duplicate source path')
        seen.add(item['path'])
        anchors = Anchors()
        try:
            anchors.feed(item['content']['html'])
            anchors.close()
        except ValueError as error:
            raise ValueError(f'{item["sourceId"]}: {error}') from error
        routes.append({'path': item['path'], 'kind': 'content',
                       'contentId': item['sourceId'], 'query': '',
                       'fragments': anchors.values})
    routes.sort(key=lambda route: int(route['contentId'].split(':')[1]))
    document = {'schemaVersion': '1.0.0', 'routes': routes}
    validate_document('routes', document)
    return document
