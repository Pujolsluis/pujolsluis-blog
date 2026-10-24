import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { parseFragment, serialize } from 'parse5';
import { configuration, withBase } from './config.mjs';

export function safePath(value) {
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('\\') || /[?#\x00-\x1f]/.test(value)) throw new Error(`Unsafe route path: ${value}`);
  let decoded;
  try { decoded = decodeURIComponent(value); } catch { throw new Error(`Invalid encoded route: ${value}`); }
  if (decoded.split('/').some(p => p === '.' || p === '..') || decoded.includes('\\') || /[\x00-\x1f\x7f]/.test(decoded) || /%2f|%5c/i.test(value)) throw new Error(`Unsafe encoded path: ${value}`);
  if (value !== '/' && !value.endsWith('/')) throw new Error(`Renderer requires directory routes ending in /: ${value}`);
  return value;
}

function unique(values, label) {
  if (new Set(values).size !== values.length) throw new Error(`Duplicate ${label}.`);
}

export function loadBundle(config = configuration()) {
  // v1 conditionals inherit parent property/type constraints. Disable only
  // Ajv's extra schema-authoring warnings for those valid JSON Schema forms.
  const ajv = new Ajv2020({ allErrors: true, strict: true, strictRequired: false, strictTypes: false });
  addFormats(ajv);
  const data = {};
  for (const name of ['content', 'assets', 'routes']) {
    const schema = JSON.parse(fs.readFileSync(`docs/contracts/v1/${name}.schema.json`, 'utf8'));
    const document = JSON.parse(fs.readFileSync(path.join(config.inputDir, `${name}.json`), 'utf8'));
    const valid = ajv.compile(schema);
    if (!valid(document)) throw new Error(`${name} contract invalid: ${ajv.errorsText(valid.errors)}`);
    data[name] = document;
  }
  unique(data.content.items.map(i => i.sourceId), 'content sourceId');
  unique(data.content.items.map(i => i.path), 'content path');
  unique(data.assets.assets.map(i => i.assetId), 'assetId');
  unique(data.assets.assets.map(i => i.sourceUrl), 'asset source URL');
  unique(data.assets.assets.map(i => i.localPath), 'asset local path');
  unique(data.routes.routes.map(i => `${i.path}?${i.query}`), 'route path/query');
  for (const item of data.content.items) {
    safePath(item.path);
    if (new URL(item.canonicalUrl).pathname !== item.path) throw new Error(`Canonical path mismatch: ${item.sourceId}`);
    for (const field of ['html', 'original']) {
      if (crypto.createHash('sha256').update(item.content[field]).digest('hex') !== item.content.provenance[`${field}Sha256`]) throw new Error(`Provenance mismatch: ${item.sourceId} ${field}`);
    }
  }
  for (const route of data.routes.routes) safePath(route.path);
  const items = data.content.items.filter(i => i.status === 'publish' && Date.parse(i.publishedAt) <= config.buildTime.getTime());
  const itemsById = new Map(items.map(i => [i.sourceId, i]));
  const routes = data.routes.routes.filter(r => ['content', 'archive'].includes(r.kind) && !r.query && (r.kind !== 'content' || itemsById.has(r.contentId)));
  if (routes.some(r => r.kind === 'archive' && r.path !== '/')) throw new Error('Non-home archives require MIG-05 archive selection metadata.');
  unique(routes.map(r => r.path), 'rendered route path');
  unique(routes.map(r => decodeURIComponent(r.path)), 'decoded output route path');
  for (const item of items) {
    if (!routes.some(r => r.kind === 'content' && r.contentId === item.sourceId && r.path === item.path)) throw new Error(`Missing matching content route for ${item.sourceId}`);
  }
  for (const route of data.routes.routes.filter(r => r.kind === 'content')) {
    if (!data.content.items.some(i => i.sourceId === route.contentId && i.path === route.path)) throw new Error(`Unresolved content route: ${route.path}`);
  }
  const assetIds = new Set(items.flatMap(i => [...i.assetIds, ...(i.sourceMetadata.featuredAssetId ? [i.sourceMetadata.featuredAssetId] : [])]));
  const assets = data.assets.assets.filter(a => assetIds.has(a.assetId));
  for (const id of assetIds) if (!assets.some(a => a.assetId === id)) throw new Error(`Unresolved assetId: ${id}`);
  for (const route of data.routes.routes) {
    if (route.target && !data.routes.routes.some(r => r.path === route.target && !r.query)) throw new Error(`Unresolved route target: ${route.target}`);
  }
  unique(assets.map(a => a.localPath), 'public asset path');
  const origins = new Set(data.content.items.map(i => new URL(i.canonicalUrl).origin));
  return { config, items, routes, assets, origins, allRoutes: data.routes.routes };
}

export function assetFile(asset, inputDir) {
  if (!asset.localPath.startsWith('media/') || asset.localPath.includes('\\') || asset.localPath.split('/').some(s => s === '..' || s === '.' || !s) || /[%?#\x00-\x1f]/.test(asset.localPath)) throw new Error(`Unsafe media path: ${asset.localPath}`);
  const filename = path.resolve(inputDir, asset.localPath);
  const real = fs.realpathSync(filename);
  if (!real.startsWith(`${fs.realpathSync(inputDir)}${path.sep}`)) throw new Error(`Asset escapes input directory: ${asset.localPath}`);
  const bytes = fs.readFileSync(real);
  if (bytes.length !== asset.bytes || crypto.createHash('sha256').update(bytes).digest('hex') !== asset.sha256) throw new Error(`Asset integrity mismatch: ${asset.assetId}`);
  return { filename: real, bytes };
}

export function rewriteUrl(value, bundle) {
  const asset = bundle.assets.find(a => a.sourceUrl === value);
  if (asset) return withBase(`/${asset.localPath}`, bundle.config.base);
  if (value.startsWith('/') && !value.startsWith('//')) return withBase(value, bundle.config.base);
  try {
    const url = new URL(value);
    if (bundle.origins.has(url.origin)) return withBase(`${url.pathname}${url.search}${url.hash}`, bundle.config.base);
  } catch { /* Fragment and relative URLs remain relative to the preserved route. */ }
  return value;
}

function resourceUrl(value, bundle, allowEmbed = false) {
  const protocol = new URL(value, 'https://renderer.invalid').protocol;
  if (!['http:', 'https:'].includes(protocol)) throw new Error(`Unsafe resource protocol: ${protocol}`);
  const mapped = bundle.assets.find(a => a.sourceUrl === value || `/${a.localPath}` === value);
  if (mapped) return withBase(`/${mapped.localPath}`, bundle.config.base);
  if (value.startsWith('/') && !value.startsWith('//')) throw new Error(`Unmapped local resource: ${value}`);
  if (allowEmbed && bundle.items.some(item => item.embeds.some(embed => embed.url === value))) return value;
  throw new Error(`Unmapped source resource: ${value}`);
}

export function renderHtml(html, bundle) {
  const fragment = parseFragment(html);
  function walk(node) {
    if (['script', 'base', 'object', 'embed', 'meta', 'link', 'style', 'form'].includes(node.tagName)) throw new Error(`Unsupported active HTML element: ${node.tagName}`);
    for (const attr of node.attrs || []) {
      if (/^on/i.test(attr.name) || ['srcdoc', 'style'].includes(attr.name)) throw new Error(`Unsupported active HTML attribute: ${attr.name}`);
      if (['href', 'src', 'poster', 'action', 'xlink:href'].includes(attr.name)) {
        const protocol = new URL(attr.value, 'https://renderer.invalid').protocol;
        if (!['http:', 'https:', 'mailto:', 'tel:'].includes(protocol)) throw new Error(`Unsafe URL in ${attr.name}`);
        attr.value = ['src', 'poster'].includes(attr.name) ? resourceUrl(attr.value, bundle, node.tagName === 'iframe') : rewriteUrl(attr.value, bundle);
      }
      if (attr.name === 'srcset') {
        if (attr.value.includes('data:')) throw new Error('Data URL srcset needs importer normalization.');
        attr.value = attr.value.split(',').map(candidate => {
          const parts = candidate.trim().split(/\s+/);
          parts[0] = resourceUrl(parts[0], bundle);
          return parts.join(' ');
        }).join(', ');
      }
    }
    for (const child of node.childNodes || []) walk(child);
    if (node.content) walk(node.content);
  }
  walk(fragment);
  return serialize(fragment);
}

export function dateLabel(value) {
  // Format the original calendar date without changing it via the builder's timezone.
  const date = value.slice(0, 10);
  return new Intl.DateTimeFormat('en', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' }).format(new Date(`${date}T12:00:00Z`));
}
