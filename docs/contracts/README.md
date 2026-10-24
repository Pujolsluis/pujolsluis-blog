# Migration contracts v1

These contracts unblock fixture-driven MIG-02 through MIG-07. They do not establish source completeness or approve launch. MIG-01 remains open until private source inputs and a frozen, reconciled baseline exist.

## Files and consumers

| File | Purpose | Consumer |
| --- | --- | --- |
| `v1/content.schema.json` | Normalized content bundle with exact original body, rendered HTML, metadata and provenance | MIG-02, 04, 05, 06 |
| `v1/assets.schema.json` | Original media manifest with stable attachment ID, source URL, relative destination, SHA-256 and byte count | MIG-03, 04, 07 |
| `v1/routes.schema.json` | Path/query identity, fragments, content IDs and explicit alias targets | MIG-05, 07 |
| `../../fixtures/v1/` | Synthetic examples covering HTML, shortcode, gallery, code whitespace, video, Unicode and local anchors | All fixture development |
| `validate.py` | Draft 2020-12 plus cross-bundle validation | Import/integration/CI |

Every bundle has `schemaVersion: "1.0.0"` and one records array (`items`, `assets`, or `routes`). All properties are explicit; unexpected properties fail validation. A future incompatible contract gets a new major-version directory; consumers must reject unsupported versions. Contract changes require coordinated fixtures and tests. JSON array order is preserved; importer output order must be deterministic.

Content IDs retain a source namespace (`wp:101`); never replace WordPress IDs with array offsets. `path` is the original site-root-relative path, independent of the preview base. Keep canonical URLs intact; renderer handles the staging prefix separately. Dates must contain an explicit timezone offset or `Z`. HTML and original source are separate fields: do not pass an unresolved shortcode through as normalized HTML. Preserve a shortcode's exact original text and require a verified expansion or frozen rendered snapshot; unknown shortcode/block expansion fails import. `content.provenance` identifies synthetic, direct HTML or rendered snapshot evidence and hashes the rendered HTML UTF-8 bytes. Its reference is an opaque evidence identifier, never private raw data.

Normalized schemas support `publish`, `draft`, `future`, `private` and `pending` for private import/editorial processing and synthetic filtering tests. Public output must include only `publish` records whose publication time is at or before the fixed build time. Keep actual private/draft records, exports and intermediate private bundles outside this public repository. A fixture containing a synthetic draft is safe only because it is deliberately invented.

Asset paths are relative to the media bundle directory, contain no parent traversal, query or fragment, and are unique. Original bytes, checksum, MIME type and dimensions must be measured; no placeholder hash is accepted. `owned: false` documents a third-party resource and does not prove that it has been archived. A content `assetIds` reference must resolve. The sample SVG is created for this fixture, not copied from production.

Routes are unique by `(path, query)`. Query strings omit the leading `?` and retain the exact observed encoding/order. Fragment strings omit `#`. A content route must resolve to its content ID and canonical path; redirects/query aliases must name an existing route target. The manifest describes desired compatibility, not proof of an HTTP status: GitHub Pages lacks arbitrary server redirects/query routing, so MIG-05 records implementation and any accepted deviation. Never silently normalize encoded paths, query order, trailing slashes or fragments.

## Reproducible validation

Use Python 3.12 and pinned development dependencies from the repository root:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests/contracts -v
python -m unittest discover -s tests -v
python -m docs.contracts.validate fixtures/v1
ruff check .
```

Validation raises `ContractError` with the bundle and failing location, or a cross-record integrity description. CLI exits nonzero on invalid input. Schema validation alone cannot verify HTML fidelity, source completeness, media identity, safe HTML, behavior or domain cutover readiness. Synthetic fixtures are examples, never evidence about real source counts.

## Baseline and release evidence

Store raw WXR, private metadata, uploaded originals, theme settings and snapshots in an owner-controlled private location. Record collection time, tool/command, source URL/ID, input checksum, response status and evidence reference for each collection. Freeze source editing before final reconciliation; capture an initial baseline and final delta separately. Public evidence may contain published source IDs/URLs and aggregate counts but must omit credentials, drafts, emails and IP addresses.

The source inventory owner maintains public crawl evidence under `migration/inventory/public/`. Public crawl completeness is always `unverified` until reconciled with the frozen owner export and upload archive. Require set equality of stable IDs and routes across sources; report missing, unexpected and duplicate records with denominators. Measure every original media byte and check Pages limits before locking the final generator/hosting decision. Astro remains the candidate pending complete source/size evidence. Frozen visual baselines must cover every discovered route at desktop/tablet/mobile, with tool/browser/font versions, viewport and any justified nondeterministic masks recorded.

## Current evidence and blockers

- Synthetic fixtures and structural/integrity negative tests are available.
- Private WXR, full media archive, theme/settings/plugin inventory, frozen rendered snapshots and final delta are pending.
- Complete source counts, original media totals, production fidelity and accepted behavioral deviations are not established.
- No production DNS/custom-domain changes or release approval are included.
