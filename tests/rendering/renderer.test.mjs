import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { parse } from 'parse5';
import crypto from 'node:crypto';
import { configuration, withBase } from '../../site/lib/config.mjs';
import { assetFile, dateLabel, loadBundle, renderHtml, safePath } from '../../site/lib/content.mjs';
import { verifyOutput } from '../../site/lib/storage.mjs';

const fixedTime = '2026-01-01T00:00:00Z';
const baseConfig = configuration({ BUILD_TIME: fixedTime });
const fixture = loadBundle(baseConfig);
function temporaryBundle(callback) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'blog-rendering-'));
  fs.cpSync('fixtures/v1', directory, { recursive: true });
  try { return callback(directory); } finally { fs.rmSync(directory, { recursive: true, force: true }); }
}
function edit(directory, name, transform) {
  const filename = path.join(directory, `${name}.json`);
  const value = JSON.parse(fs.readFileSync(filename, 'utf8'));
  transform(value);
  fs.writeFileSync(filename, JSON.stringify(value));
}
function nodes(root, predicate) {
  return [...(predicate(root) ? [root] : []), ...(root.childNodes || []).flatMap(child => nodes(child, predicate))];
}
function text(node) { return node.value || (node.childNodes || []).map(text).join(''); }
function attribute(node, name) { return node.attrs?.find(attr => attr.name === name)?.value; }

test('base configuration rejects malformed paths and dangerous output directories', () => {
  for (const base of ['relative', '//other/', '/x/../', '/x', '/%2e%2e/']) assert.throws(() => configuration({ SITE_BASE: base }));
  for (const dir of ['.', '..', '/', 'site/generated-dist', 'public/generated-dist', 'fixtures/v1/generated-dist', 'tests/generated-dist', 'node_modules/generated-dist']) assert.throws(() => configuration({ SITE_OUTPUT_DIR: dir }));
  temporaryBundle(directory => {
    fs.symlinkSync(path.resolve('site'), path.join(directory, 'linked'));
    assert.throws(() => configuration({ SITE_OUTPUT_DIR: path.join(directory, 'linked', 'generated-dist') }), /overlap/);
  });
  assert.equal(withBase('/about/#biography', '/preview/'), '/preview/about/#biography');
  assert.equal(withBase('//external.test/image', '/preview/'), '//external.test/image');
  assert.equal(withBase('/about/', '/'), '/about/');
});

test('paths preserve encoding but reject traversal, aliases and file output ambiguity', () => {
  assert.equal(safePath('/caf%C3%A9/'), '/caf%C3%A9/');
  for (const route of ['/../', '/%2e%2e/', '//host/', '/a%2fb/', '/a%0ab/', '/a\\b/', '/post?x=1', '/post']) assert.throws(() => safePath(route));
});

test('contract version, provenance and missing media references fail closed', () => {
  temporaryBundle(directory => {
    edit(directory, 'content', c => { c.schemaVersion = '9.0.0'; });
    assert.throws(() => loadBundle({ ...baseConfig, inputDir: directory }), /contract invalid/);
  });
  temporaryBundle(directory => {
    edit(directory, 'content', c => { c.items[0].content.html += '<p>Changed</p>'; });
    assert.throws(() => loadBundle({ ...baseConfig, inputDir: directory }), /Provenance mismatch/);
  });
  temporaryBundle(directory => {
    edit(directory, 'assets', a => { a.assets = []; });
    assert.throws(() => loadBundle({ ...baseConfig, inputDir: directory }), /Unresolved assetId/);
  });
});

test('duplicate, missing and mismatched content routes fail closed', () => {
  temporaryBundle(directory => {
    edit(directory, 'routes', r => { r.routes.push(r.routes[0]); });
    assert.throws(() => loadBundle({ ...baseConfig, inputDir: directory }), /Duplicate/);
  });
  temporaryBundle(directory => {
    edit(directory, 'routes', r => { r.routes = r.routes.filter(x => x.contentId !== 'wp:101'); });
    assert.throws(() => loadBundle({ ...baseConfig, inputDir: directory }), /Missing matching content route/);
  });
  temporaryBundle(directory => {
    edit(directory, 'routes', r => { r.routes[0].path = '/wrong/'; });
    assert.throws(() => loadBundle({ ...baseConfig, inputDir: directory }), /Missing matching content route/);
  });
  temporaryBundle(directory => {
    edit(directory, 'content', c => { c.items.push({ ...structuredClone(c.items[1]), sourceId: 'wp:103', path: '/%61bout/', canonicalUrl: 'https://example.invalid/%61bout/' }); });
    edit(directory, 'routes', r => { r.routes.push({ path: '/%61bout/', kind: 'content', contentId: 'wp:103', query: '', fragments: [] }); });
    assert.throws(() => loadBundle({ ...baseConfig, inputDir: directory }), /Duplicate decoded output route/);
  });
});

test('only published content at or before the fixed build time can enter public output', () => {
  temporaryBundle(directory => {
    edit(directory, 'content', c => {
      const template = c.items[0];
      for (const [index, status] of ['draft', 'future', 'private', 'pending', 'publish'].entries()) {
        c.items.push({ ...structuredClone(template), sourceId: `wp:${300 + index}`, status, path: `/secret-${index}/`, canonicalUrl: `https://example.invalid/secret-${index}/`, publishedAt: status === 'publish' ? '2099-01-01T00:00:00Z' : template.publishedAt });
      }
    });
    edit(directory, 'routes', r => {
      for (let i = 0; i < 5; i++) r.routes.push({ path: `/secret-${i}/`, kind: 'content', contentId: `wp:${300 + i}`, query: '', fragments: [] });
    });
    const result = loadBundle({ ...baseConfig, inputDir: directory });
    assert.deepEqual(result.items.map(i => i.sourceId), ['wp:101', 'wp:102']);
    assert.ok(result.routes.every(r => !r.path.includes('secret')));
  });
});

test('media bytes are verified and asset symlinks cannot escape the input bundle', () => {
  assert.equal(assetFile(fixture.assets[0], baseConfig.inputDir).bytes.length, 135);
  temporaryBundle(directory => {
    fs.appendFileSync(path.join(directory, 'media/example.svg'), 'corrupt');
    assert.throws(() => assetFile(fixture.assets[0], directory), /integrity mismatch/);
    assert.throws(() => assetFile({ ...fixture.assets[0], localPath: '../outside.svg' }, directory), /Unsafe media path/);
    fs.unlinkSync(path.join(directory, 'media/example.svg'));
    fs.symlinkSync('/etc/hosts', path.join(directory, 'media/example.svg'));
    assert.throws(() => assetFile(fixture.assets[0], directory), /escapes input/);
  });
});

test('unresolved LFS pointers fail even when a mistaken manifest hashes the pointer bytes', () => {
  temporaryBundle(directory => {
    const pointer = `version https://git-lfs.github.com/spec/v1\noid sha256:${'a'.repeat(64)}\nsize 135\n`;
    fs.writeFileSync(path.join(directory, 'media/example.svg'), pointer);
    const asset = { ...fixture.assets[0], bytes: Buffer.byteLength(pointer), sha256: crypto.createHash('sha256').update(pointer).digest('hex') };
    assert.throws(() => assetFile(asset, directory), /Unresolved LFS asset/);
    assert.throws(() => verifyOutput(directory), /Unresolved LFS pointer/);
  });
});

test('HTML keeps code whitespace, Unicode, captions and provider embed identity', () => {
  const html = renderHtml(fixture.items[0].content.html, fixture);
  assert.ok(html.includes('Café, 日本語 &amp; código 👋'));
  assert.ok(html.includes('if x &lt; 2:\n    print("hola")\n'));
  assert.ok(html.includes('Sanitized gallery caption'));
  assert.ok(html.includes('https://www.youtube-nocookie.com/embed/fixture-video'));
  assert.ok(html.includes('/pujolsluis-blog/about/#biography'));
  assert.ok(html.includes('/pujolsluis-blog/media/example.svg'));
  assert.equal(dateLabel('2020-01-02T00:04:05+14:00'), 'January 2, 2020');
});

test('all mapped image candidates, poster and canonical-origin links use deployment base', () => {
  const html = renderHtml('<a href="https://example.invalid/about/?a=1#biography">About</a><video poster="/media/example.svg"><source srcset="https://example.invalid/wp-content/uploads/example.svg 1x, /media/example.svg 2x"></video>', fixture);
  assert.ok(html.includes('/pujolsluis-blog/about/?a=1#biography'));
  assert.ok(html.includes('srcset="/pujolsluis-blog/media/example.svg 1x, /pujolsluis-blog/media/example.svg 2x"'));
  assert.ok(html.includes('poster="/pujolsluis-blog/media/example.svg"'));
});

test('active HTML and unmapped owned resources require importer normalization', () => {
  for (const html of ['<script>alert(1)</script>', '<img src="x" onerror="bad()">', '<a href="java&#10;script:bad()">x</a>', '<iframe srcdoc="x"></iframe>', '<img srcset="javascript:bad 1x">', '<img src="/missing.svg">', '<img src="https://example.invalid/wp-content/missing.png">', '<form action="https://example.invalid/"></form>']) assert.throws(() => renderHtml(html, fixture));
});

for (const base of ['/', '/pujolsluis-blog/']) {
  test(`full static output renders at ${base} with working local resources and preview safeguards`, () => temporaryBundle(directory => {
    edit(directory, 'content', content => {
      content.items.push({ ...structuredClone(content.items[0]), sourceId: 'wp:999', path: '/secret-draft/', canonicalUrl: 'https://example.invalid/secret-draft/', title: 'SECRET_DRAFT_SENTINEL', status: 'private', assetIds: ['wp:998'] });
      content.items.push({ ...structuredClone(content.items[1]), sourceId: 'wp:997', path: '/caf%C3%A9/', canonicalUrl: 'https://example.invalid/caf%C3%A9/' });
      content.schemaVersion = '1.1.0';
      for (const item of content.items) item.sourceMetadata.sourceType = item.kind;
      const portfolio = { ...structuredClone(content.items[1]), sourceId: 'wp:996', kind: 'portfolio', title: 'Synthetic portfolio', path: '/portfolio/synthetic/', canonicalUrl: 'https://example.invalid/portfolio/synthetic/' };
      portfolio.sourceMetadata.sourceType = 'portfolio';
      content.items.push(portfolio);
    });
    edit(directory, 'assets', assets => { assets.assets.push({ ...assets.assets[0], assetId: 'wp:998', localPath: 'media/secret.svg', sourceUrl: 'https://example.invalid/secret.svg' }); });
    edit(directory, 'routes', routes => { routes.routes.push({ path: '/secret-draft/', kind: 'content', contentId: 'wp:999', query: '', fragments: [] }, { path: '/caf%C3%A9/', kind: 'content', contentId: 'wp:997', query: '', fragments: [] }, { path: '/portfolio/synthetic/', kind: 'content', contentId: 'wp:996', query: '', fragments: [] }); });
    const outDir = path.join(directory, '..', `${path.basename(directory)}-dist`);
    try {
      const result = spawnSync(process.execPath, ['site/build.mjs'], { encoding: 'utf8', env: { ...process.env, ASTRO_TELEMETRY_DISABLED: '1', BUILD_TIME: fixedTime, SITE_BASE: base, MIGRATION_INPUT_DIR: directory, SITE_OUTPUT_DIR: outDir } });
      assert.equal(result.status, 0, result.stdout + result.stderr);
      const report = JSON.parse(fs.readFileSync(path.join(outDir, 'renderer-report.json')));
      assert.equal(report.renderedContent, 4);
      assert.equal(report.copiedAssets, 1);
      assert.equal(report.fidelityVerified, false);
      assert.equal(report.base, base);
      assert.equal(fs.readFileSync(path.join(outDir, 'robots.txt'), 'utf8'), 'User-agent: *\nDisallow: /\n');
      assert.ok(!fs.existsSync(path.join(outDir, 'CNAME')));
      assert.ok(!fs.existsSync(path.join(outDir, 'sitemap.xml')));
      for (const route of report.renderedRoutes) {
        const html = fs.readFileSync(path.join(outDir, decodeURIComponent(route), 'index.html'), 'utf8');
        assert.ok(!html.includes('SECRET_DRAFT_SENTINEL'));
        assert.ok(!html.includes('secret-draft'));
        const document = parse(html);
        assert.ok(html.includes('Synthetic fixtures'));
        assert.equal(nodes(document, n => n.tagName === 'meta' && attribute(n, 'name') === 'robots').map(n => attribute(n, 'content'))[0], 'noindex, nofollow');
        assert.equal(nodes(document, n => n.tagName === 'link' && attribute(n, 'rel') === 'canonical').map(n => attribute(n, 'href'))[0], `https://pujolsluis.github.io${base}${route.slice(1)}`);
        for (const node of nodes(document, n => ['a', 'img', 'link', 'script'].includes(n.tagName))) {
          const url = attribute(node, 'src') || attribute(node, 'href');
          if (!url?.startsWith('/') || url.startsWith('//')) continue;
          assert.ok(url.startsWith(base), `${url} must use ${base}`);
          const resource = decodeURIComponent(url.slice(base.length).split(/[?#]/)[0]);
          assert.ok(fs.existsSync(path.join(outDir, resource)), `Missing local output ${resource}`);
        }
      }
      const article = parse(fs.readFileSync(path.join(outDir, '2020/01/02/fixture-post/index.html'), 'utf8'));
      assert.equal(text(nodes(article, n => n.tagName === 'pre')[0]), 'if x < 2:\n    print("hola")\n');
      assert.deepEqual(fs.readFileSync(path.join(outDir, 'media/example.svg')), fs.readFileSync('fixtures/v1/media/example.svg'));
      assert.ok(!fs.existsSync(path.join(outDir, 'secret-draft')));
      assert.ok(!fs.existsSync(path.join(outDir, 'media/secret.svg')));
      assert.ok(!fs.readFileSync(path.join(outDir, 'index.html'), 'utf8').includes('Synthetic portfolio'));
    } finally { fs.rmSync(outDir, { recursive: true, force: true }); }
  }));
}
