"""Rendered WordPress HTML converts into editable Markdown post bodies."""

import unittest

from scripts.import_content.markdown import html_to_markdown


class MarkdownConversionTests(unittest.TestCase):
    def test_common_article_content_becomes_markdown_and_keeps_embeds(self):
        source = '''
<h2 id="history">History</h2>
<p>A <strong>bold</strong> and <em>clear</em> paragraph with
<a href="/about/#bio">a local link</a>.</p>
<ul><li>first<ul><li>nested</li></ul></li><li>second</li></ul>
<pre><code class="language-python">if x &lt; 2:
    print("hello")
</code></pre>
<figure class="aligncenter size-large"><a href="/photo/"><img src="/media/photo.webp" width="640" height="480" alt="A photo"></a><figcaption><em>Caption text</em></figcaption></figure>
<div class="wp-block-jetpack-tiled-gallery aligncenter"><figure class="tiled-gallery__item"><img src="/media/one.webp" alt="First"></figure><figure class="tiled-gallery__item"><img src="/media/two.webp" alt="Second"></figure></div>
<p><script src="https://gist.github.com/Pujolsluis/abc123.js"></script></p>
<iframe src="https://www.youtube-nocookie.com/embed/abcdefghijk?start=90" title="Talk"></iframe>
<table><tbody><tr><td>Keep complex table</td></tr></tbody></table>
'''
        markdown = html_to_markdown(source)
        self.assertIn('<a id="history"></a>', markdown)
        self.assertIn('## History', markdown)
        self.assertIn('**bold**', markdown)
        self.assertIn('*clear*', markdown)
        self.assertIn('[a local link](</about/#bio>)', markdown)
        self.assertIn('* first', markdown)
        self.assertIn('  * nested', markdown)
        self.assertIn('```python\nif x < 2:\n    print("hello")\n```', markdown)
        self.assertIn('{{< figure src="/media/photo.webp"', markdown)
        self.assertIn('width="640"', markdown)
        self.assertIn('*Caption text*', markdown)
        self.assertIn('{{< gallery label="Photo gallery" >}}', markdown)
        self.assertIn('{{< figure src="/media/one.webp" alt="First"', markdown)
        self.assertIn('{{< gist user="Pujolsluis" id="abc123" >}}', markdown)
        self.assertIn('{{< youtube id="abcdefghijk" title="Talk" start="90" >}}', markdown)
        self.assertIn('<table>', markdown)
        self.assertIn('Keep complex table', markdown)

    def test_text_is_escaped_so_literals_do_not_turn_into_markdown(self):
        markdown = html_to_markdown('<p>* literal_ text</p><p># not a heading</p>')
        self.assertIn(r'\* literal\_ text', markdown)
        self.assertIn(r'\# not a heading', markdown)

    def test_link_destination_trims_surrounding_whitespace(self):
        markdown = html_to_markdown('<p><a href=" https://example.com/watch?v=1 ">video</a></p>')
        self.assertIn('[video](<https://example.com/watch?v=1>)', markdown)


if __name__ == '__main__':
    unittest.main()
