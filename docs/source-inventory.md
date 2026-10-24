# Public source inventory

This is an unauthenticated acquisition baseline for MIG-01 and issue #1. It is **not a complete source inventory or a source freeze**. WordPress remains production. An owner WXR, uploads directory and theme directory were subsequently supplied and reconciled below; production editing freeze, complete settings/customizations, full rendered baselines and final delta remain required.

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

The snapshot identifies 2,151 upload reference URLs mapping to 458 distinct origin candidates. Ten origins were measured for a partial known total of 4,459,043 bytes; 448 origins still have unknown byte counts. This total is not an estimate of the complete archive. HEAD measurements count distinct origin candidate URLs once, while retaining all reference variants. `unknownUploadOriginBytes` identifies unmeasured/unknown candidates; a measured sum of zero with unknown candidates means unknown, not an empty archive. HEAD Content-Length is an acquisition estimate, not a downloaded checksum or byte-for-byte verification. This initial public capture predates the supplied owner archive. Its partial HEAD sizing remains separate from the complete backup hashing below; CSS dependency traversal and JavaScript-loaded assets remain unresolved. Therefore this report cannot establish the 1 GB Pages feasibility gate or authorize source-host shutdown.

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
| Every published item accounted for | Owner WXR post/page IDs match all 57 REST IDs; 12 published portfolios and 98 attachment routes explain sitemap extras | Explicit handling of plugin/config records, complete feature/settings evidence and frozen final delta |
| Owned media measured | All 2,402 backup upload files hashed privately; exact aggregate footprints and case-loss recovery below | Complete source/media URL reconciliation, per-item asset mapping and approved hosting decision |
| No private export data committed | No export/authentication/comment collection; published metadata allowlist and body hashes | Apply the same private-data boundary to owner inputs/import intermediates |
| Versioned contracts and synthetic coverage | Owned by MIG-01 foundation PR #11 | Consume committed contracts; acquisition metadata is not a normalized content bundle |
| Frozen visual/backend fidelity | Feature and route evidence identifies work | Full snapshots/screenshots and interactive verification at required viewports |

No DNS, custom-domain configuration, production publication or feature retirement is part of this inventory.


## Owner backup acquisition and reconciliation

The later owner backup contains one top-level WXR export (2,165,608 bytes), `uploads/` and `themes/`. The acquisition command reads these inputs and never changes them. The versioned sanitized report is [`owner-backup-summary.json`](../migration/inventory/owner-backup-summary.json). The full per-file SHA-256/path manifest and recovered media stay in a private directory outside Git, with directory mode 0700 and manifest mode 0600. No XML, draft content, comments/email/IP/password data, or licensed theme source enters this repository.

WXR has **550 items**: 45 published posts, 7 draft posts, 12 published pages, 4 draft pages, 12 published portfolios, 448 inherited attachments, 15 published navigation-menu definitions, 3 ad definitions, 1 ad-placement definition, 1 Elementor library record and 2 subscription-form definitions. Configuration records are explicit work items, not silently discarded editorial content. Draft counts are aggregate only; no private IDs, titles or bodies appear in the report.

All 45 published post IDs and 12 published page IDs equal the public REST sets, with zero missing or additional IDs. The public sitemap's 111 non-REST URLs are now classified: 12 published portfolio URLs, 98 attachment URLs and the homepage. This resolves route identity classification, not fidelity or final source completeness. The WXR export plus upload copy is not evidence that production editing has frozen, nor does it contain complete database options, theme/plugin behavior or all externally hosted data.

All 446 available attachment metadata payloads parsed successfully with a data-only PHP serialization reader that cannot instantiate PHP objects. Metadata identifies primary attachment files, explicit original images, generated size variants and image-edit backups. No symlinks were traversed. Original/private-parent attachment candidates are an archival planning set, **not a publication allowlist**.

| Upload classification | Present files | Known bytes | Exact-path misses |
| --- | ---: | ---: | ---: |
| Entire uploads backup | 2,402 | 1,076,148,970 | Not applicable |
| Attachment main/original-image candidates | 459 | 673,948,321 | 2 |
| Image-edit backup variants | 19 | 17,160,808 | 0 |
| Metadata size derivatives | 1,889 | 384,303,215 | 2 |
| Observed public references | 494 | 684,445,082 | 2 |
| Originals + edit backups + observed public references (union) | 525 | 697,725,468 | 2 |
| All attachment metadata + observed references (union) | 2,370 | **1,075,541,365** | 4 |
| Metadata derivatives not observed in the bounded public capture | 1,845 | 377,815,897 | 2 |
| Remaining unclassified/unreferenced backup files | 32 | 607,605 | 0 |

Rows overlap; use the union rows instead of summing categories. The two/ four exact-path misses are case-collision evidence discussed below, not an assumption that matching case-insensitive bytes are interchangeable. Present byte sums precede URL-correct reconstruction and additional renderer/theme assets.

The limited observed-reference union fits 1 GB, but it excludes many metadata derivatives and does not establish that those historical public URLs may be omitted. Preserving the complete attachment metadata/reference union already requires 1,075,541,365 known bytes, above both 1,000,000,000 bytes and 1 GiB before site HTML, fonts and source-case repairs. The exact final deployment footprint remains unverified pending complete mapping and a hosting/routing decision. Nothing has been deleted, compressed or moved out of scope to fit Pages.

Uploads contain 529,484,277 bytes of PNG, 486,086,393 bytes of JPG, 49,096,927 bytes of GIF and 10,742,401 bytes of JPEG, plus CSS/fonts and small auxiliary files. The largest file is 10,411,474 bytes; no file reaches 50 MiB or 100 MiB. Per-file Git size is therefore not the present blocker; total preserved deployment bytes are.

The backup has 2,151 distinct SHA-256 values and 119,980,396 bytes of repeated content. Identical bytes do **not** automatically permit deduplicating URLs on plain Pages: every historical media URL still needs to serve the correct bytes. Rewriting current HTML to one shared URL would leave old direct links unresolved. No deduplication occurred; a future storage/routing design must preserve the original URL-to-bytes contract explicitly.

The theme directory identifies **TheBlogger 2.3.3, ThemeForest License**, plus 15 bundled WordPress default themes. This confirms available source identity only; active theme selection, owner customizations, database options and redistribution rights for deployed theme assets still need verification. No commercial theme implementation or bundled plugin archive is copied into Git. The backup contains no original uploads ZIP/TAR; five ZIP files are theme-bundled plugin packages and are unrelated to upload recovery.

### Exact-case media loss and private recovery

[`missing-upload-case-evidence.json`](../migration/inventory/public/missing-upload-case-evidence.json) records eight successful public GET observations with exact URL, status, byte count and SHA-256. The four exact-case metadata misses are:

- `2018/06/cropped-Pujolsluis-icon.png`
- `2018/06/cropped-Pujolsluis-icon-1.png`
- `2018/06/cropped-Pujolsluis-icon-150x150.png`
- `2018/06/cropped-Pujolsluis-Icon-1-150x150.png`

WXR has separate original attachment identities for `icon` versus `Icon` names (31/41 and 34/44). Upper- and lower-case source URLs return different bytes. The case-insensitive backup has four path entries holding the opposite-case URL's content; even an exact-looking filename cannot be trusted without its source hash. Case-only path normalization would silently replace media.

All eight live URL variants were captured into **private SHA-256-addressed blobs**, with an exact, case-sensitive source URL-to-hash mapping. Three live blobs totaling **16,569 bytes** were absent anywhere in the backup; a fourth mismatched candidate's bytes existed under another filename. All eight URLs and all eight distinct live hashes are now preserved privately. The backup remains unchanged. Future acquisition should use content-addressed storage or a case-sensitive filesystem and retain exact source URLs separately, preventing another macOS case collision. Reconstruction into public routes remains a later asset-mapping task; these GET observations do not declare the entire uploads archive source-verified.

### Reproduce owner acquisition

Choose a new private output directory outside every Git checkout; existing output directories are rejected to preserve prior acquisition evidence:

```sh
python -m scripts.inventory.backup \
  --backup /path/to/pujolsluis-wordpress-backup \
  --public-inventory migration/inventory/public/observations.json \
  --private-output /private/tmp/pujolsluis-mig-01-new-acquisition \
  --report migration/inventory/owner-backup-summary.json
python -m unittest discover -s tests/inventory -v
```

The script discovers exactly one top-level XML, rejects DTD/entity declarations, checks uploads paths, skips file/directory symlinks, hashes every regular upload file and keeps sensitive per-file detail outside Git. Tests cover UTF-8 PHP byte lengths, rejection of PHP objects/trailing data, URL-decoded traversal, symlink boundaries, private-data allowlisting, private file permissions and unchanged source bytes. The separately recorded eight public GET snapshots are frozen source-case evidence; broad crawling is not repeated as part of owner acquisition.
