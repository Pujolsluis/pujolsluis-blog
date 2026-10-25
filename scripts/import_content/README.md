# WXR importer (MIG-02)

Run from the repository root with Python 3.12 and `requirements-dev.txt` installed:

```sh
python -m scripts.import_content /private/source/site.xml /private/migration/import-01 \
  --manifest /private/source/render-evidence.json \
  --assets /private/migration/assets.json
```

The positional input is a **complete WXR 1.2 export**, including posts, pages, authors, categories/tags and attachment records. Partial post-only exports do not establish completeness. `--assets` is optional when attachment identities are present in WXR; supplying MIG-03's v1 manifest also resolves references to assets outside that export. The WXR import makes no HTTP requests, media downloads, path rewrites or deployment changes.

Output must be a dedicated private directory outside every Git checkout. New directories use mode 700; existing directories must already have private permissions. Files use mode 600. `content.json` follows the shared content 1.1.0 contract and includes only status `publish`, non-password-protected posts/pages/portfolio records. Draft, pending, private, future, trash, auto-draft and inherited records are excluded before parsing their content. A renderer must additionally filter publication time against its fixed build time. `routes.json` follows the MIG-01 v1 route contract and contains WXR-backed content paths with rendered HTML fragment IDs. `private-report.json` contains input checksum, per-record disposition, aggregate reconciliation, attachment identities and **private** source metadata. Retain the original export privately; the report records its exact byte SHA-256 and opaque evidence reference without copying the WXR into public content.

The CLI rejects output in repositories even under an ignored `private-export/` directory. This makes it harder to commit or publish private metadata accidentally. The API `import_wxr(bytes, manifest=..., assets=..., previous=...)` returns `(public_bundle, private_report)` and raises `ImportFailure` with private diagnostics; callers have the same responsibility to protect reports and source inputs. A normalized bundle may retain owner-authored HTML, scripts and embeds; it is trusted source content and must be reviewed before publishing.

## Rendering evidence

WXR body text is the decoded XML/CDATA string, retaining Unicode, HTML, anchors, ordering and code whitespace. XML's mandatory newline normalization applies; the whole original export checksum separately retains byte identity. The importer does not implement WordPress filters, `wpautop`, block serialization or plugin shortcode expansion. Every nonempty body needs either a frozen rendered body snapshot or an explicit source-hash-bound attestation that the complete rendered body equals the original HTML. Plain text, shortcodes and blocks always need snapshots. Unresolved shortcode/block syntax in rendered HTML fails. Rendered bracket syntax inside code/pre/script/style is treated as literal and preserved exactly. Ambiguous bracket syntax in ordinary text still requires source review; there is no silent passthrough option.

Supply a manifest with exactly this top-level shape (checksums below are placeholders to replace, not valid fixture evidence):

```json
{
  "schemaVersion": "1.0.0",
  "sourceReference": "owner-export-initial-01",
  "items": {
    "wp:101": {
      "originalSha256": "SHA256_OF_EXACT_DECODED_WXR_BODY",
      "html": "<p>Exact frozen rendered article body, excluding theme shell.</p>",
      "htmlSha256": "SHA256_OF_EXACT_HTML_UTF8",
      "reference": "frozen-snapshot-101-initial-01"
    },
    "wp:102": {
      "originalSha256": "SHA256_OF_EXACT_DECODED_WXR_BODY",
      "directHtmlReference": "reviewed-complete-rendered-equals-original-102"
    }
  }
}
```

The manifest's `html` is preserved exactly and bound to the source's `originalSha256`. A mismatch fails rather than using a stale snapshot after an edit. References are opaque evidence IDs, never private paths, credentials or raw export text. Snapshot extraction/freezing is an owner-controlled preparation step; a hash establishes the binding, not independent visual or rendering correctness. The importer rejects stale manifest IDs absent from the complete export and unknown manifest properties.

An optional `excerptHtml` requires `originalExcerptSha256` bound to the exact decoded excerpt. Otherwise the original excerpt HTML is preserved; unresolved shortcode/block syntax fails. An optional per-item `reviewedPostMeta` object maps a metadata key to an opaque review/disposition evidence ID. Every non-core metadata key must have an explicit disposition; `_edit_lock`, `_edit_last` and the mapped `_thumbnail_id` are recognized. This is a review record, not an automatic declaration that a plugin field is irrelevant. Exact values and disposition references remain only in the private report. Keep fields affecting rendering, URLs or behavior unresolved until the relevant migration task reproduces them.

## Preservation and diagnostics

Source IDs, exact canonical paths/encoded slugs, opaque GUIDs, author display identity, category/tag source IDs/names/slugs, excerpt HTML, comment/ping settings, featured attachment identity and rendered iframe placement are retained. WXR local/GMT date pairs produce explicit offsets without inventing timezone names. Empty/invalid GMT pairs fail for public records. All published author and taxonomy references must resolve to WXR definitions. Attachment records are delegated to MIG-03; this importer does not fabricate bytes or claim that a WXR URL is archived. `assetIds` includes resolvable HTML URL/class and featured references; exhaustive URL/srcset/CSS discovery and byte verification belong to MIG-03's later gate.

Approved ordinary comments retain source/parent IDs, display author, date and exact safe HTML. Emails, IPs, user agents and unapproved comments never enter the public bundle. A conservative HTML allowlist rejects unsafe or unsupported markup instead of silently changing comments. Missing/nonpublic parents, cycles, duplicate IDs and approved pingbacks/trackbacks fail for explicit review. `portfolio` records and their `portfolio-category` terms retain distinct source types and IDs under content 1.1.0. Other published structures (custom post types/taxonomies, duplicate fields, unresolved post metadata) fail with record-level diagnostics and the unresolved public canonical URL in the private report. Successful unrelated records are counted, but no partial bundle is emitted on failure.

The content schema has no separate fields for menu order, page parents, sticky state or plugin metadata. These source values remain private; nonzero parent/menu/sticky values also appear in `unresolvedBehavior`. A successful structural import does not mean these behaviors have been reproduced. Preserve the WXR and resolve those issues with MIG-04/05/06/08. The renderer must provide portfolio routes and presentation separately.

On success, both public bundle and private report serialize deterministically. Record order is numeric WordPress ID; internal body/taxonomy order is preserved. Reordering WXR items does not change the content bundle. A report identifies the exact source bytes, so its checksum changes when export bytes/order change. Individual writes use atomic replacement. `contentBundleSha256` and `routesBundleSha256` bind the success report to both normalized files; consumers must verify this before using a pair after an interrupted write. On failure the CLI exits 1, writes only `failure-report.json`, and leaves any previous successful pair intact. The presence of that failure report invalidates the current run. A successful rerun removes it. Input/filesystem errors exit 2.

## Final delta and verification

After the owner freezes editing, export **all content again** and pass the earlier public bundle:

```sh
python -m scripts.import_content /private/source/final-all-content.xml /private/migration/final \
  --manifest /private/source/final-render-evidence.json \
  --previous /private/migration/import-01/content.json
python -m unittest discover -s tests/import_content -v
python -m unittest discover -s tests -v
ruff check .
```

`delta` lists added, changed, removed and unchanged stable IDs. The new bundle is a complete replacement: edits and newly private/deleted records cannot survive through an upsert cache. This deliberately does not accept incremental WXR chunks: WordPress exports cannot reliably express deletions, and omission means removal. Completeness remains `unverified` until owner input sets, media, routes and rendered evidence reconcile through MIG-01/08. Synthetic regression evidence is in `tests/import_content/fixtures/source.xml`.

## Hugo handoff

After reviewing `content.json` and reconciling its checksum against `private-report.json`, produce Hugo files in a dedicated generated directory:

```sh
python -m scripts.import_content.hugo /private/migration/import-01/content.json \
  /private/migration/hugo-content --build-time 2026-10-25T00:00:00-07:00
```

The explicit build time filters future-dated records and records every exclusion. Each post, page, portfolio and captured attachment page receives a stable `<kind>/wp-<ID>.html` file, JSON front matter with its exact route and source evidence, followed by validated rendered HTML. The optional selected media map rewrites only reviewed owned URLs for preview; source body provenance retains the original HTML checksum. `.hugo-import-report.json` lists source IDs, paths, per-file/body SHA-256 values and unresolved preview references. Repeated exports are byte-identical; a complete later bundle removes stale generated files. The adapter refuses to replace a directory containing files it did not generate or files edited since the prior report. This is a private candidate artifact; only MIG-08 promotes reviewed production content into the public repository.

Hugo must enable its [HTML content format](https://gohugo.io/content-management/formats/) with `security.allowContent = ['text/html']` and render `.Content` without Markdown conversion. MIG-04 must use the exact source-head front matter for title, canonical and social fields. MIG-03 supplies only required optimized ordinary-Git image files at selected exact public paths; the adapter copies no image bytes.

## Production evidence sidecars and preview gates

The private WXR manifest can additionally bind `wxrSha256` to the exact input bytes. `utilityItems` and `deferredItems` are maps keyed by `wp:<ID>`, each with the exact WXR `kind`, `canonicalUrl`, `reason` and opaque `reference`. Utility reasons are `navigation-config`, `ad-config`, `newsletter-form` and `template-config`; a published post/page/portfolio can be withheld only as `backend-dependent`. A changed ID/kind/URL fails. `externalAttachmentIds` maps missing WXR attachment IDs observed in hash-bound rendered HTML to opaque references; they remain explicit MIG-03 blockers, not fabricated assets.

An optional per-item `literalRenderedText` list permits ambiguous bracket text only when each token occurs in both the hash-bound WXR body and its matching frozen rendered HTML. It must not be used for active plugin shortcodes. `deferredPostMeta` maps each unresolved key to `{ "effect": "seo-social|url|layout|media|embed|backend|admin-cache-unverified|unknown", "reference": "opaque-id" }`; the private report lists each source ID/key/effect. These are conservative unresolved classifications, not claims of non-rendering. SEO, URL, layout, media and behavior fields require later mapping before promotion.

Attachment **HTML pages** are distinct from uploaded media files. Freeze reviewed read-only captures with `python -m scripts.import_content.attachments WXR capture-index.json snapshots/ attachment-pages.json`, writing the output outside Git. It checks WXR identity, HTTP 200 HTML with unchanged final URL, snapshot checksum, live article title/body, self canonical, captions, image references and both body and full-page fragments. No image bytes are downloaded by this command.

Use the private evidence when materializing Hugo:

```sh
python -m scripts.import_content.hugo /private/migration/import-01/content.json \
  /private/migration/hugo-content --build-time 2026-10-25T00:00:00-07:00 \
  --head-manifest /private/migration/source-head.json \
  --head-source-root /private/migration/source-head-html \
  --attachment-manifest /private/migration/attachment-pages.json \
  --attachment-source-root /private/migration/attachment-html \
  --private-report /private/migration/import-01/private-report.json \
  --media-map /private/migration/selected-media-map.json
```

The version 1.0.0 source-head sidecar has one record per `sourceId`/`canonicalUrl`, a source HTML `sourcePageSha256` and hashed `.html` `sourcePageReference`, and `fields` for `title`, `description`, `canonical`, `ogTitle`, `ogDescription`, `ogImage`, `twitterTitle`, `twitterDescription` and `twitterImage`. Missing source values are explicit `null`. The adapter re-extracts values from the referenced HTML and rejects changed checksums, duplicate/conflicting source fields or URL mappings, and gaps for selected content. The sidecar can retain three separately deferred backend page heads while materializing the 66 selected records. WXR title remains the article heading; `seoTitle` and social front matter use live source-head values.

If an authored WordPress page owns a Hugo section root (the current `/portfolio/` page), the adapter writes `<section>/_index.html` so the authored page's route and source head override Hugo's generated list page. Its WXR `sourceType` remains `page` in migration front matter. A real Hugo regression test covers this precedence.

The selected media map is `{ "schemaVersion": "1.0.0", "previewBase": "/project/", "mappings": [{ "sourceUrl": "https://...", "targetPath": "/wp-content/uploads/..." }] }`. Generate it privately from MIG-03's selected inventory, actual committed static files and the first adapter report with `python -m scripts.import_content.media migration/assets/manifest.json static/ first-report.json /private/selected-media-map.json --preview-base /project/`. This command verifies every selected file checksum and refuses conflicting paths; an upload URL alone never authorizes a target. The adapter rewrites selected owned `src`, `srcset`, poster, CSS `url()`, attachment image links/data attributes and head images beneath that preview base. External-provider URLs stay untouched. Every owned reference without an exact local target appears in `.hugo-import-report.json` as `unresolvedOwnedMedia`, distinguished as `unmapped-upload` or `owned-non-upload`. The report also records source/full-page attachment fragments and source-shell fragments that the final renderer must preserve or disposition. Original rendered body hashes remain in provenance, with separate hashes of preview-rewritten bodies.
