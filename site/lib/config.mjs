import path from 'node:path';
import fs from 'node:fs';

function physicalPath(value) {
  if (fs.existsSync(value)) return fs.realpathSync(value);
  return path.join(physicalPath(path.dirname(value)), path.basename(value));
}

function contains(parent, child) {
  const relative = path.relative(parent, child);
  return relative === '' || !relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative);
}

export function normalizeBase(value = '/pujolsluis-blog/') {
  if (!/^\/(?:[A-Za-z0-9_-]+\/)*$/.test(value)) {
    throw new Error('SITE_BASE must be / or a slash-delimited repository path, ending in /.');
  }
  return value;
}

export function configuration(env = process.env) {
  const siteUrl = env.SITE_URL || 'https://pujolsluis.github.io';
  const url = new URL(siteUrl);
  if (!['http:', 'https:'].includes(url.protocol) || url.pathname !== '/' || url.search || url.hash || url.username || url.password) {
    throw new Error('SITE_URL must be an HTTP(S) origin without a path or credentials.');
  }
  const buildTime = new Date(env.BUILD_TIME || Date.now());
  if (!Number.isFinite(buildTime.getTime())) throw new Error('BUILD_TIME must be an ISO date.');
  const inputDir = physicalPath(path.resolve(env.MIGRATION_INPUT_DIR || 'fixtures/v1'));
  const outDir = physicalPath(path.resolve(env.SITE_OUTPUT_DIR || 'dist'));
  if (outDir === path.parse(outDir).root) throw new Error('SITE_OUTPUT_DIR cannot be a filesystem root.');
  if (!/(?:^|-)dist$/.test(path.basename(outDir))) throw new Error('SITE_OUTPUT_DIR must name a dedicated dist or *-dist directory.');
  const repository = physicalPath(process.cwd());
  const protectedPaths = [repository, inputDir, ...['site', 'public', '.git', '.github', 'docs', 'tests', 'scripts', 'fixtures', 'node_modules', '.astro'].map(dir => physicalPath(path.resolve(dir)))];
  for (const protectedDir of protectedPaths) {
    if (contains(outDir, protectedDir) || protectedDir !== repository && contains(protectedDir, outDir)) {
      throw new Error('SITE_OUTPUT_DIR must not overlap source, input or repository metadata.');
    }
  }
  return {
    base: normalizeBase(env.SITE_BASE),
    siteUrl: url.origin,
    buildTime,
    inputDir,
    outDir,
  };
}

export function withBase(value, base) {
  if (!value.startsWith('/') || value.startsWith('//')) return value;
  return `${base}${value.slice(1)}`;
}

export function publicUrl(value, config) {
  return new URL(withBase(value, config.base), config.siteUrl).href;
}
