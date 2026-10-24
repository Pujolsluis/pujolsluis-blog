import path from 'node:path';

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
  const inputDir = path.resolve(env.MIGRATION_INPUT_DIR || 'fixtures/v1');
  const outDir = path.resolve(env.SITE_OUTPUT_DIR || 'dist');
  if (outDir === path.parse(outDir).root) throw new Error('SITE_OUTPUT_DIR cannot be a filesystem root.');
  for (const protectedDir of [process.cwd(), inputDir, path.resolve('site'), path.resolve('public'), path.resolve('.git')]) {
    if (protectedDir === outDir || protectedDir.startsWith(`${outDir}${path.sep}`) || outDir.startsWith(`${protectedDir}${path.sep}`) && protectedDir !== process.cwd()) {
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
