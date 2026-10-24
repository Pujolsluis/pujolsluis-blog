import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { configuration } from './lib/config.mjs';
import { assetFile, loadBundle } from './lib/content.mjs';

const config = configuration();
const bundle = loadBundle(config);
// Validate all bytes before Astro touches the output directory.
const assets = bundle.assets.map(asset => ({ asset, ...assetFile(asset, config.inputDir) }));
const result = spawnSync(process.execPath, ['node_modules/astro/bin/astro.mjs', 'build'], { stdio: 'inherit', env: { ...process.env, BUILD_TIME: config.buildTime.toISOString() } });
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status || 1);
for (const { asset, bytes } of assets) {
  const output = path.join(config.outDir, asset.localPath);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, bytes);
}
fs.writeFileSync(path.join(config.outDir, 'robots.txt'), 'User-agent: *\nDisallow: /\n');
fs.writeFileSync(path.join(config.outDir, '.nojekyll'), '');
fs.writeFileSync(path.join(config.outDir, 'renderer-report.json'), `${JSON.stringify({
  schemaVersion: '1.0.0', mode: 'migration-preview', base: config.base,
  builtAt: config.buildTime.toISOString(), renderedContent: bundle.items.length,
  renderedRoutes: bundle.routes.map(r => r.path), copiedAssets: assets.length,
  deferredRouteCounts: Object.fromEntries(['feed', 'redirect', 'query-alias'].map(kind => [kind, bundle.allRoutes.filter(r => r.kind === kind).length])),
  fidelityVerified: false,
}, null, 2)}\n`);
