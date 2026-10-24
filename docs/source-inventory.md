# Public source inventory

This is an unauthenticated acquisition baseline for MIG-01 and issue #1. It is **not a complete source inventory or a source freeze**. WordPress remains production; the owner WXR export, uploads archive, settings/theme/customizations and final delta are still required.

The machine-readable report is [`migration/inventory/public/observations.json`](../migration/inventory/public/observations.json). Its `schemaVersion` is `1.0.0`; `records` use the normalized contract identity `wp:<WordPress ID>`, but this acquisition report is deliberately separate from an import bundle. It stores public metadata, exact rendered-content UTF-8 hashes, per-page references, response statuses/body hashes and discovery reconciliation. It stores no article bodies, comments, private exports, credentials or authenticated responses.

## Verified public sources

The configured source is `https://www.pujolsluis.com/`. Requests are sequential with a 150 ms delay, an identifying browser-compatible User-Agent, a 30-second timeout and an 8 MiB response limit. Default Python urllib requests received HTTP 406; the identifying User-Agent succeeds. robots.txt permits this public discovery, disallows `/wp-admin/`, and advertises `/sitemap.xml` and `/news-sitemap.xml`.

- `/wp-json/` provides the REST index, site timezone `America/New_York` and an observed current GMT offset of -4. Historical dates must use WordPress GMT fields or the named timezone, not that single current offset.
- `/wp-json/wp/v2/posts?status=publish&context=view&per_page=100` reports 45 posts; all 45 records were captured.
- `/wp-json/wp/v2/pages?status=publish&context=view&per_page=100` reports 12 pages; all 12 records were captured.
- Categories report 21 terms; tags report 111 terms across two pages. All 132 taxonomy records and their route URLs were captured. Term counts are observations, not proof that every route responds or every archive page was crawled.
- `/sitemap.xml` indexes `/sitemap-1.xml` and `/image-sitemap-1.xml`. The report distinguishes direct page `<loc>` values from nested image namespace `<image:loc>` values. Image references are assets, never crawl-page denominators.
- `/feed/` is public RSS. Its item URLs/GUIDs are reconciled against the REST URLs; it is a limited feed, not a complete archive.
- `/wp-sitemap.xml` and `/sitemap_index.xml` returned 404. These failed probes remain recorded evidence.

The 2026-10-24 snapshot contains 57 REST records, 132 taxonomy routes, 70 successful HTML page observations, 2,361 resource reference URLs and 21 distinct embed URLs. All 57 REST permalinks were observed successfully. The image sitemap lists 445 image entries covering 155 distinct page URLs. Across sitemaps, **111 distinct page URLs are absent from the posts/pages REST sets**, including 12 `/portfolio/*` routes and attachment-like paths. These are retained as unresolved public routes; their content types, source IDs and behavior require further investigation and owner export reconciliation. No claim of all public content follows from the 57-record REST denominator.

Public REST `context=view` returned `content.rendered` and `content.protected`, without `content.raw`. This is useful fallback evidence for visible rendered HTML, but does not recover original editor blocks/shortcodes, complete plugin settings, theme settings or private source records. The importer must not invent original WXR content from rendered HTML.

## Rendered discovery and features

The final bounded capture prioritizes the homepage and all 57 REST permalinks, then taxonomy/sitemap routes, with a 70-page maximum. `reconciliation.uncrawledQueue` and `crawlLimitReached` explicitly identify the remaining crawl work. Capture is sequential and can span source changes; response hashes do not freeze or archive the source.

Per-page evidence includes canonical URL, internal/external links, asset URLs, embed URLs, and markup feature markers. The public types endpoint advertises WordPress/editor/plugin types; this report does not enumerate their records or assume that they represent public editorial content.

TheBlogger theme, Pixelwars and Jetpack asset markers occur on captured pages. Search, subscription/forms, comments, galleries, code and video markup occur. These are presence signals; playback, interaction, consent, form delivery, subscription processing and search behavior still need browser verification and replacement decisions. REST namespaces are plugin evidence, not a verified active plugin inventory.

The 12 published pages include Contact, Cookie Policy, Shop, Cart, Checkout, My account, Portfolio, About Me and theme demonstration pages (Shortcodes, Typography, Page Full Width and Page with Sidebar). Page titles and route presence do not prove active commerce: these may be placeholders. No purchases, logins or form submissions were attempted. Backend feature parity remains an explicit unresolved cutover gate, and commerce/account routes require owner-reviewed compatibility decisions. No route is silently excluded as a demo.

Embed evidence includes YouTube, Canva, SlideShare, a same-site WordPress embed and XamGirl WordPress embeds. Public WordPress oEmbed `#?secret=` fragments are transport identifiers in already public embed URLs; they are preserved as source evidence and are not WordPress credentials. Providers, exact URLs and query settings remain intact. No third-party embed is fetched by the collector.

## Media feasibility remains unresolved

Source images predominantly use Jetpack `i0.wp.com`, `i1.wp.com` and `i2.wp.com` URLs. Every observed CDN reference and its transformation query is retained. `uploadOriginCandidate` maps only CDN paths explicitly containing the configured source host and `/wp-content/uploads/` back to that host. A candidate can be a resized filename and is not proof of an original attachment. Third-party images are not reclassified as owned merely because they use the same CDN.

The snapshot identifies 2,151 upload reference URLs mapping to 458 distinct origin candidates. Ten origins were measured for a partial known total of 4,459,043 bytes; 448 origins still have unknown byte counts. This total is not an estimate of the complete archive. HEAD measurements count distinct origin candidate URLs once, while retaining all reference variants. `unknownUploadOriginBytes` identifies unmeasured/unknown candidates; a measured sum of zero with unknown candidates means unknown, not an empty archive. HEAD Content-Length is an acquisition estimate, not a downloaded checksum or byte-for-byte verification. Full originals, CSS dependency traversal, JavaScript-loaded assets and the complete uploads archive remain pending. Therefore this report cannot establish the 1 GB Pages feasibility gate or authorize source-host shutdown.

## Reproduce and continue

Use Python 3.12 from the repository root:

```sh
python -m scripts.inventory.capture --output migration/inventory/public --max-pages 70
python -m scripts.inventory.measure migration/inventory/public/observations.json --limit 10
python -m unittest discover -s tests/inventory -v
python -m unittest discover -s tests -v
ruff check .
```

Capture defaults to **zero HEAD requests**, so metadata acquisition does not wait for media sizing. `--max-pages` bounds HTML requests; increase it for a later acquisition, retaining the old snapshot externally if needed. The measurement command resumes unattempted origins and atomically checkpoints after every URL. It deduplicates shared CDN origins. Failed HEAD attempts are marked as attempted and remain unknown; investigate them explicitly instead of silently retrying forever. Re-running capture replaces the report and resets measurement progress; run measurement after capture.

Tests cover pagination with authoritative totals, namespaced image sitemaps, relative/srcset/CSS resources, public-field allowlisting, CDN origin boundaries, deduplicated measurement and recovery after interruption. The root test discovery includes this suite. Existing SHA-pinned Actions are unchanged.

## MIG-01 acceptance evidence

| Acceptance requirement | Current evidence | Remaining input/gate |
| --- | --- | --- |
| Every published item accounted for | Public REST totals reconcile for 45 posts and 12 pages; sitemap/feed differences recorded | Owner WXR, all relevant public types and frozen final delta reconciliation |
| Owned media measured | Referenced direct/CDN origin candidates enumerated; resumable partial HEAD sizing | Complete uploads/original byte archive, SHA-256, dimensions, total hosting budget |
| No private export data committed | No export/authentication/comment collection; published metadata allowlist and body hashes | Apply the same private-data boundary to owner inputs/import intermediates |
| Versioned contracts and synthetic coverage | Owned by MIG-01 foundation PR #11 | Consume committed contracts; acquisition metadata is not a normalized content bundle |
| Frozen visual/backend fidelity | Feature and route evidence identifies work | Full snapshots/screenshots and interactive verification at required viewports |

No DNS, custom-domain configuration, production publication or feature retirement is part of this inventory.
