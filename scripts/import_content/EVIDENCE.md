# MIG-02 implementation evidence

This is fixture and private-source audit evidence, not production publication acceptance. It depends on MIG-01 content 1.1.0 and route 1.0.0 contracts. No production WXR, drafts, private reports, comments' personal data, credentials or media bytes are committed.

Run with Python 3.12 and pinned `requirements-dev.txt`:

```sh
python -m unittest discover -s tests/import_content -v
python -m unittest discover -s tests -v
ruff check --no-cache .
```

The fixture suite checks exact rendered HTML, code whitespace, Unicode, GUID, author/taxonomy IDs, local/GMT offsets, excerpts, comments, featured assets, URL paths and fragment IDs. Snapshot hash mismatches, unresolved shortcodes/blocks, unexpected XML/meta/custom records, unsafe comments, duplicate paths/IDs and nonpublic publication attempts fail with source-ID diagnostics. Source duplicate anchors are preserved in HTML and reported privately while route fragments list browser target names once. Tests also cover hash-bound literal brackets, explicit utility/backend deferrals, source-head values/absences/checksums, attachment HTML routes and selected owned media rewriting. Repeat imports are byte-identical. A final full-export delta removes records absent from the replacement export and the Hugo adapter removes stale generated files while protecting owner edits. The private report hashes both `content.json` and `routes.json`; the Hugo report hashes each output file and original/rewritten body.

A read-only audit of the owner's WXR 1.2 export found 550 source items: 45 published posts, 12 published pages, 12 published portfolios, 448 attachments, 11 drafts and 22 published utility/custom records. All 69 public content URLs have hash-bound live source-head records; 66 can be frozen as candidate static content. Three WooCommerce shortcode pages (`/cart/`, `/checkout/`, `/my-account/`) remain explicitly backend-dependent. The 22 utility records are individually classified by source ID, exact URL and type (15 navigation items, four ad configurations, two newsletter forms, one template configuration). The private report also lists 15 image class IDs absent from WXR attachment records, four pages with duplicate source anchors, and all metadata keys whose effects remain unresolved. None of those private values or raw snapshots are committed.

The 98 attachment-like URLs common to the public sitemap and owner WXR are all public HTML attachment pages in the observed capture: HTTP 200, unchanged final URL and self canonical. Their full page HTML snapshots remain private. The attachment freezer binds each page to WXR ID/URL and source checksum, then extracts live body/title/caption/image references and body/full-page fragment sets. A private Hugo materialization produced 66 content files plus 98 attachment HTML files. It reported 1,714 owned media references without a selected local target (1,676 distinct URLs), so the preview cannot claim media parity until MIG-03 supplies verified optimized files and an exact URL map.

Hugo v0.168.0 built the 164 private candidate records with a temporary copy of the MIG-04 renderer after adding `security.allowContent = ['text/html']` to that copy. The current renderer configuration rejects `.html` content without this setting; its head partial also recomputes `<title>` rather than using the exact `seoTitle` source field. MIG-04 must land both changes. MIG-03 must supply selected optimized images as ordinary Git files at exact public URL paths. MIG-05 consumes generated v1 content routes, attachment page route evidence and source-shell fragment gaps, then adds archive, feed, alias and query-route dispositions. MIG-08 performs final source/media/route/head and visual reconciliation before production content is committed.
