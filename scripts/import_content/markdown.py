"""Convert reviewed rendered HTML into readable Hugo Markdown content."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
import re
from urllib.parse import parse_qs, urlsplit


VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
        'param', 'source', 'track', 'wbr'}
RAW_BLOCKS = {'audio', 'canvas', 'object', 'picture', 'svg', 'table', 'video'}
HEADING = re.compile(r'^h([1-6])$')
GIST = re.compile(r'^https?://gist\.github\.com/([A-Za-z0-9_-]+)/([A-Fa-f0-9]+)\.js(?:\?.*)?$', re.I)
YOUTUBE = re.compile(r'^/(?:embed|v)/([A-Za-z0-9_-]+)$')


@dataclass
class Text:
    value: str


@dataclass
class Element:
    tag: str
    attrs: dict[str, str | None]
    children: list = field(default_factory=list)
    start: int = 0
    end: int = 0


class _Tree(HTMLParser):
    """Build a small source-positioned tree so complex HTML can pass through."""

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.line_offsets = [0]
        for line in source.splitlines(keepends=True):
            self.line_offsets.append(self.line_offsets[-1] + len(line))
        self.root = Element('', {})
        self.stack = [self.root]
        self.feed(source)
        self.close()
        for node in self.stack[1:]:
            node.end = len(source)

    def position(self):
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def _close_to(self, tag, end):
        matches = [index for index, node in enumerate(self.stack) if node.tag == tag]
        if not matches:
            return
        index = matches[-1]
        for node in self.stack[index:]:
            node.end = end if node.tag == tag else self.position()
        self.stack = self.stack[:index]

    def _start(self, tag, attrs, self_closing=False):
        start = self.position()
        if tag == 'li' and self.stack[-1].tag == 'li':
            self._close_to('li', start)
        if tag == 'p' and self.stack[-1].tag == 'p':
            self._close_to('p', start)
        raw_start = self.get_starttag_text() or ''
        node = Element(tag, dict(attrs), start=start, end=start + len(raw_start))
        self.stack[-1].children.append(node)
        if tag not in VOID and not self_closing:
            self.stack.append(node)

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag):
        start = self.position()
        match = re.match(r'</\s*' + re.escape(tag) + r'\s*>', self.source[start:], re.I)
        end = start + match.end() if match else start
        self._close_to(tag, end)

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(Text(data))


def _plain(node):
    if isinstance(node, Text):
        return node.value
    return ''.join(_plain(child) for child in node.children)


def _escape_text(value):
    value = re.sub(r'\s+', ' ', value)
    value = re.sub(r'([\\`*_{}\[\]])', r'\\\1', value)
    value = re.sub(r'(?m)^(\s*)([#>])', r'\1\\\2', value)
    value = re.sub(r'(?m)^(\s*)([-+])(?=\s)', r'\1\\\2', value)
    return value


def _destination(value):
    value = (value or '').strip()
    return re.sub(r'[\s<>]', lambda match: f'%{ord(match.group()):02X}', value)


def _shortcode(name, **attrs):
    encoded = ' '.join(f'{key}={json.dumps(str(value), ensure_ascii=False)}'
                       for key, value in attrs.items() if value is not None and value != '')
    return '{{< ' + name + (' ' + encoded if encoded else '') + ' >}}'


def _caption(markup):
    if not markup:
        return ''
    return html_to_markdown(markup).strip()


def _has_shortcode_embed(node):
    if isinstance(node, Text):
        return False
    if node.tag == 'script' and GIST.fullmatch(node.attrs.get('src') or ''):
        return True
    if node.tag == 'iframe':
        parsed = urlsplit(node.attrs.get('src') or '')
        if parsed.hostname and parsed.hostname.lower() in {
                'youtube.com', 'www.youtube.com', 'youtube-nocookie.com',
                'www.youtube-nocookie.com'} and YOUTUBE.fullmatch(parsed.path):
            return True
    return any(_has_shortcode_embed(child) for child in node.children)


def html_to_markdown(source):
    """Convert common article HTML to Markdown, retaining complex media as HTML."""
    tree = _Tree(source)

    def anchor(node):
        identifier = node.attrs.get('id')
        if not identifier:
            return ''
        escaped = identifier.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
        return f'<a id="{escaped}"></a>\n\n'

    def render_children(node, in_pre=False):
        values = [render(child, in_pre) for child in node.children]
        return '\n'.join(value for value in values if value)

    def image_markdown(node):
        source_url = node.attrs.get('src') or node.attrs.get('data-orig-file') or ''
        alt = _escape_text(node.attrs.get('alt') or '')
        if not source_url:
            return alt
        title = node.attrs.get('title')
        title_part = f' "{title.replace(chr(34), chr(92) + chr(34))}"' if title else ''
        return f'![{alt}](<{_destination(source_url)}>{title_part})'

    def shortcode_figure(node):
        images = []

        def collect(current, link=None):
            if isinstance(current, Text):
                return
            if current.tag == 'a' and current.attrs.get('href'):
                link = current.attrs['href']
            if current.tag == 'img':
                images.append((current, link))
            for child in current.children:
                collect(child, link)

        collect(node)
        if len(images) != 1:
            return render_children(node)
        image, link = images[0]
        src = image.attrs.get('src') or image.attrs.get('data-orig-file') or ''
        if not src:
            return render_children(node)
        attrs = {
            'src': src,
            'alt': image.attrs.get('alt') or '',
            'title': image.attrs.get('title'),
            'class': node.attrs.get('class'),
            'imgClass': image.attrs.get('class'),
            'width': image.attrs.get('width'),
            'height': image.attrs.get('height'),
            'style': image.attrs.get('style') or node.attrs.get('style'),
            'link': link,
        }
        opening = _shortcode('figure', **attrs)
        caption_node = next((child for child in node.children
                             if isinstance(child, Element) and child.tag == 'figcaption'), None)
        caption = (render_children(caption_node).strip() if caption_node else
                   _caption(image.attrs.get('data-image-caption', '')))
        return f'{opening}\n{caption}\n{{{{< /figure >}}}}' if caption else f'{opening}\n{{{{< /figure >}}}}'

    def render_list(node, depth=0):
        ordered = node.tag == 'ol'
        start = node.attrs.get('start') or '1'
        try:
            number = max(1, int(start))
        except ValueError:
            number = 1
        lines = []
        for child in node.children:
            if not isinstance(child, Element) or child.tag != 'li':
                continue
            pieces = []
            nested = []
            for item in child.children:
                if isinstance(item, Element) and item.tag in {'ul', 'ol'}:
                    nested.append(render_list(item, depth + 1))
                else:
                    value = render(item).strip()
                    if value:
                        pieces.append(value)
            bullet = f'{number}. ' if ordered else '* '
            number += 1
            indent = '  ' * depth
            main = ' '.join(pieces).strip()
            if main:
                wrapped = main.replace('\n', '\n' + indent + '  ')
                lines.append(indent + bullet + wrapped)
            lines.extend(value for value in nested if value)
        return '\n'.join(lines)

    def render(node, in_pre=False):
        if isinstance(node, Text):
            return node.value if in_pre else _escape_text(node.value)
        tag = node.tag.lower()
        prefix = anchor(node)
        classes = set((node.attrs.get('class') or '').split())
        if tag in {'script', 'style'}:
            src = node.attrs.get('src') or ''
            if tag == 'script':
                match = GIST.fullmatch(src)
                if match:
                    return prefix + _shortcode('gist', user=match.group(1), id=match.group(2))
            return prefix + (tree.source[node.start:node.end] or '')
        if tag == 'iframe':
            src = node.attrs.get('src') or ''
            parsed = urlsplit(src)
            if parsed.hostname and parsed.hostname.lower() in {
                    'youtube.com', 'www.youtube.com', 'youtube-nocookie.com',
                    'www.youtube-nocookie.com'}:
                match = YOUTUBE.fullmatch(parsed.path)
                if match:
                    query = parse_qs(parsed.query)
                    attrs = {'id': match.group(1), 'title': node.attrs.get('title') or 'YouTube video',
                             'start': (query.get('start') or [None])[0]}
                    return prefix + _shortcode('youtube', **attrs)
            return prefix + tree.source[node.start:node.end]
        if tag in RAW_BLOCKS:
            return prefix + tree.source[node.start:node.end]
        if tag == 'pre':
            code = _plain(node)
            classes = set(' '.join((child.attrs.get('class') or '')
                                   for child in node.children if isinstance(child, Element)).split())
            language = ''
            for value in classes:
                match = re.match(r'(?:language|lang)-([A-Za-z0-9_+#.-]+)', value)
                if match:
                    language = match.group(1)
                    break
            fence = '`' * max(3, max((len(run) for run in re.findall(r'`+', code)), default=0) + 1)
            return f'\n\n{fence}{language}\n{code.rstrip(chr(10))}\n{fence}\n\n'
        if tag == 'code':
            if in_pre:
                return _plain(node)
            value = _plain(node)
            fence = '`' * max(1, max((len(run) for run in re.findall(r'`+', value)), default=0) + 1)
            padding = ' ' if value.startswith('`') or value.endswith('`') else ''
            return f'{fence}{padding}{value}{padding}{fence}'
        if tag == 'figure':
            return prefix + shortcode_figure(node)
        if tag == 'div' and classes.intersection({'wp-block-jetpack-tiled-gallery', 'tiled-gallery__gallery'}):
            label = node.attrs.get('aria-label') or 'Photo gallery'
            return prefix + _shortcode('gallery', label=label) + '\n' + render_children(node) + '\n{{< /gallery >}}'
        heading = HEADING.fullmatch(tag)
        if heading:
            level = int(heading.group(1))
            value = render_children(node).strip()
            return prefix + '\n\n' + ('#' * level) + ' ' + value + '\n\n'
        if tag in {'p', 'div', 'article', 'section', 'header', 'footer', 'main'}:
            if tag == 'div' and node.attrs.get('style') and not _has_shortcode_embed(node):
                return prefix + tree.source[node.start:node.end]
            return prefix + '\n\n' + render_children(node).strip() + '\n\n'
        if tag in {'ul', 'ol'}:
            return prefix + '\n\n' + render_list(node) + '\n\n'
        if tag == 'li':
            return prefix + render_children(node).strip()
        if tag == 'a':
            value = render_children(node).strip()
            href = node.attrs.get('href')
            if not href or not value:
                return prefix + value
            destination = _destination(href)
            title = node.attrs.get('title')
            title_part = f' "{title.replace(chr(34), chr(92) + chr(34))}"' if title else ''
            return prefix + f'[{value}](<{destination}>{title_part})'
        if tag == 'img':
            return prefix + image_markdown(node)
        if tag == 'br':
            return '  \n'
        if tag == 'hr':
            return '\n\n---\n\n'
        if tag in {'strong', 'b'}:
            return prefix + '**' + render_children(node, in_pre).strip() + '**'
        if tag in {'em', 'i'}:
            return prefix + '*' + render_children(node, in_pre).strip() + '*'
        if tag in {'del', 's', 'strike'}:
            return prefix + '~~' + render_children(node, in_pre).strip() + '~~'
        if tag == 'blockquote':
            value = render_children(node).strip()
            if any(isinstance(child, Element) and child.tag in RAW_BLOCKS | {'iframe', 'script'}
                   for child in node.children):
                return prefix + tree.source[node.start:node.end]
            return prefix + '\n\n' + '\n'.join('> ' + line if line else '>'
                                                  for line in value.splitlines()) + '\n\n'
        if tag in {'span', 'label', 'cite', 'small', 'abbr'}:
            if node.attrs.get('style') and not _has_shortcode_embed(node):
                return prefix + tree.source[node.start:node.end]
            return prefix + render_children(node, in_pre)
        if tag == 'figcaption':
            return render_children(node).strip()
        if tag in VOID:
            return prefix
        return prefix + render_children(node, in_pre)

    rendered = render_children(tree.root).strip()
    rendered = re.sub(r'\n[ \t]+\n', '\n\n', rendered)
    rendered = re.sub(r'\n{3,}', '\n\n', rendered)
    return rendered + ('\n' if rendered else '')
