# Content preview status

This aggregate report describes the content preview represented in this repository as of 2026-10-25. Merging to `master` and completing the Pages deployment makes these routes available at the public preview URL. The report contains no WXR records, comment text, personal comment metadata, source snapshots or private importer reports. The preview remains noindex, and WordPress remains the production site.

## Imported preview scope

- 45 posts, 8 pages and 13 portfolio entries are materialized as static Hugo content from hash-bound rendered-body and source-head evidence.
- 98 public attachment URLs are represented as HTML pages with their captured title, body, caption, image references, canonical and fragment evidence.
- The media inventory commits 420 selected upload files at 414,443,545 bytes for 422 public URL paths. Shared bytes may cover more than one URL.
- The verified selector maps 1,701 of 1,714 owned reference occurrences: 1,663 distinct URLs across 382 local target files. All selected file hashes are checked before URL rewrites.
- Nine source-head fields or explicit absences match the frozen source evidence for all 66 selected post/page/portfolio routes.

## Remaining review items

- Thirteen owned references still lack local targets: twelve references to two case-sensitive attachment masters absent from the backup, and one WordPress oEmbed endpoint. Lookalike files with different identities were not substituted and no replacement embed page is fabricated.
- Fifteen external theme-demo image references remain external; they were not copied into the repository.
- Eighty-nine selected media files exceed 1 MB. Check their actual display sizes and quality, then reduce or provide responsive variants where measurements support it before production launch.
- Comments are intentionally omitted by owner decision. The importer removes captured comment threads, avatar markup and WordPress comment submission forms from the published bodies; it creates no comment UI or link back to comment functionality.
- Other WordPress submission forms are also removed from static bodies. A preview-only link points to the corresponding live page when a non-comment form needs a backend.
- The three WooCommerce routes `/cart/`, `/checkout/` and `/my-account/` remain backend-dependent and are not implemented by GitHub Pages.
- Attachment page body content and media are imported, but the original WordPress theme shell is not copied wholesale. Visual comparison against source screenshots and full feature behavior are still outstanding.
- Internal article links retain their original WordPress URLs during preview. They will use the preserved paths after an approved domain cutover; WordPress remains available now.

## Validation

CI checks lint, importer/contract tests, media-selection tests, migrated route counts and comment omission, then builds the Hugo preview. Passing CI and deployment prove the static bundle builds; they do not establish complete source coverage or pixel-level fidelity. A final WordPress export/delta, route and media reconciliation, image review, visual walkthrough and explicit cutover approval are still required.
