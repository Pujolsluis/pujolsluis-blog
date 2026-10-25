# MIG-02 implementation evidence

This is fixture and private-source audit evidence, not production publication acceptance. It depends on MIG-01 content 1.1.0 and route 1.0.0 contracts. No production WXR, drafts, private reports, comments' personal data, credentials or media bytes are committed.

Run with Python 3.12 and pinned `requirements-dev.txt`:

```sh
python -m unittest discover -s tests/import_content -v
python -m unittest discover -s tests -v
ruff check --no-cache .
```

The importer fixture suite has 38 passing tests. A complete synthetic WXR reconciles five source records into two published content records, one delegated attachment, one draft exclusion and one password exclusion. Exact rendered HTML, code whitespace, Unicode, GUID, author/taxonomy IDs, local/GMT offsets, excerpts, comments, featured assets, URL paths and fragment IDs are checked. Snapshot hash mismatches, unresolved shortcodes/blocks, unexpected XML/meta/custom records, unsafe comments, duplicate anchors/paths/IDs and nonpublic publication attempts fail with source-ID diagnostics. Repeat imports are byte-identical. A final full-export delta removes records absent from the replacement export and the Hugo adapter removes stale generated files while protecting owner edits. The private report hashes both `content.json` and `routes.json`; the Hugo report hashes each output file and body.

A read-only audit of the owner backup's WXR 1.2 export found 550 source items: 45 published posts, 12 published pages, 12 published portfolios, 448 attachments, 11 drafts, and 22 other published utility/custom records. The importer failed closed on all 91 published records: the 69 content records need rendering evidence and/or metadata review, and the 22 other published structures need compatibility decisions. Its failure report contains per-record IDs and source URLs privately; no partial content bundle was produced. Portfolio category IDs are supported, but portfolio rendering, media and route parity require later gates. The backup export is named `pujolsluisblog.WordPress.2026-10-24.xml` in the owner-controlled Desktop backup directory.

Hugo output is implemented as `.html` content files with JSON front matter and exact `url` values, but no Hugo binary or MIG-04 Hugo site is present in this branch, so a full Hugo build remains an integration gate. MIG-04 must permit HTML content and use the unchanged rendered body. MIG-03 must supply required optimized images as ordinary Git files at their exact public URL paths. MIG-05 consumes the generated v1 content routes and adds archive, feed, alias and query-route dispositions. MIG-08 performs final source/media/route and visual reconciliation before production content is committed.
