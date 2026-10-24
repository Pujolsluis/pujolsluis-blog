import { defineConfig } from 'astro/config';
import { configuration } from './site/lib/config.mjs';

const config = configuration();
export default defineConfig({
  srcDir: './site/src',
  publicDir: './public',
  outDir: config.outDir,
  site: config.siteUrl,
  base: config.base,
  output: 'static',
  trailingSlash: 'always',
  build: { format: 'directory' },
  compressHTML: false,
  devToolbar: { enabled: false },
});
