# Static renderer foundation

This is a fixture-driven MIG-04 foundation, not a migrated production archive or a fidelity-approved replacement. The existing Python preview remains the deployed artifact. CI now checks the renderer in isolation, then builds the Python placeholder last. Astro is locked for this prototype. Final architecture acceptance still depends on archive/media sizing and complete feature inventory.

## Run

Use Node **>=22.23.4** and npm >=9.6.5, as required by the locked Astro 7.4.2 package. Node 24 LTS is the proposed CI runtime; the local checks recorded in `evidence.md` ran on Node 26.0.0. Astro's own published package is the precise version-specific source: [Astro 7.4.2 metadata](https://registry.npmjs.org/astro/7.4.2), [Astro configuration](https://docs.astro.build/en/reference/configuration-reference/), [static routing](https://docs.astro.build/en/guides/routing/).

```sh
npm ci --ignore-scripts
npm run lint
npm run test:rendering
npm run build
npm run dev -- --host 127.0.0.1 --port 4321
```

`dev` rebuilds and serves the static artifact with Astro preview, so integrity-checked fixture media is present. It does not watch files. Open the printed URL ending in `/pujolsluis-blog/`. Stop the server with Ctrl-C.

```sh
# Root deployment layout, still a noindex migration preview.
SITE_BASE=/ BUILD_TIME=2026-01-01T00:00:00Z npm run build

# Another fully normalized v1 bundle (keep private input outside the repository).
MIGRATION_INPUT_DIR=/absolute/path/to/bundle npm run build
```

| Setting | Default | Meaning |
| --- | --- | --- |
| `MIGRATION_INPUT_DIR` | `fixtures/v1` | Directory containing `content.json`, `assets.json`, `routes.json`, and referenced `media/` files |
| `SITE_BASE` | `/pujolsluis-blog/` | `/` or a slash-delimited repository prefix ending in `/` |
| `SITE_URL` | `https://pujolsluis.github.io` | Preview canonical HTTP(S) origin; no path or credentials |
| `SITE_OUTPUT_DIR` | `dist` | Build artifact directory; cannot overlap input or source directories |
| `BUILD_TIME` | Start of build | Fixed ISO timestamp for publication filtering and reproducibility |

## Contract and output

Consumes committed `docs/contracts/v1` schemas, validates schema version and structure, original/rendered HTML provenance hashes, identities, canonical paths and content routes. Only `status=publish` records whose publication time is at or before `BUILD_TIME` enter routes, navigation, article HTML or copied media. Referenced originals are copied without transformation after byte length and SHA-256 verification; symlinks outside the input directory fail.

Astro emits directory `index.html` files for content and the root archive. URL paths, fragments and query strings retain their source identity while deployment prefixes are added. Encoded Unicode routes use decoded filesystem directories and encoded public URLs. Article HTML is parsed and serialized without collapsing code whitespace; resource URLs are mapped to the media manifest, and external iframe sources must match a declared embed. No conversion through Markdown is performed. The home archive uses the preserved excerpt when available. Approved comments can be displayed with original WordPress-style comment anchors; threaded presentation and interaction fidelity are pending.

Every HTML page carries a prominent synthetic-preview notice and `noindex, nofollow`; `robots.txt` disallows crawling. No sitemap or CNAME is emitted. Root mode does not enable indexing or approve cutover. `renderer-report.json` reports public rendered paths, published content/media counts, deferred route counts and `fidelityVerified: false`. It does not reveal deferred/private route paths or excluded record text.

Failures return a nonzero exit status with a descriptive error: invalid JSON/schema/version/provenance, duplicate identities/routes/media destinations, missing content routes or media IDs, unsafe paths, checksum/size mismatches, active HTML requiring normalization, unmapped resources or undeclared iframe URLs. Validation failures are intentional blockers for importer normalization; they do not authorize dropping content.

## Boundaries and remaining work

Only the root archive is implemented. Category/tag/date/author archives and pagination need MIG-05 selection metadata. Feed, redirect and query-alias routes are explicitly deferred in the report for MIG-05 rather than represented as functioning HTTP compatibility. Inline CSS, scripts, forms, plugin interactions, active embed elements and unresolved resource references fail instead of passing through silently. This renderer is not a general HTML sanitizer and production imports require review. Featured-image alt text/captions need a richer approved contract; featured images are archived but not inserted by guessing missing semantics. Production logos, author widgets, likes, search, subscriptions, comment submission, galleries/lightboxes, shop/cart/checkout/account functionality and other discovered features need source-specific implementation and compatibility decisions.

Structural checks and synthetic snapshots cannot establish visual fidelity to real posts. The owner has now supplied the WXR, uploads and theme backup. They remain outside the public repository and integration/verification is in progress. Settings/custom CSS, frozen screenshots at all target viewports and complete behavior verification remain required. The supplied theme can be used locally for this site's migration; public redistribution of the reusable commercial package is a separate issue. See `evidence.md`, `theme-observations.md` and `../public/theme/LICENSES.md`.
