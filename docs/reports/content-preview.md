# Content preview status

This aggregate report describes the preview currently deployed to GitHub Pages, updated as of 2026-11-08. It contains no WXR records, comment text, personal comment metadata, source snapshots or private importer reports. The preview remains noindex, and WordPress remains the production site.

## Imported preview scope

- 45 posts, 8 pages and 12 portfolio entries are materialized as static Hugo content from hash-bound rendered-body and source-head evidence.
- All 45 blog posts are Markdown (`content/posts/*.md`) with route-preserving JSON front matter. Common article structure is Markdown; supported video, Gist and image/gallery content uses Hugo shortcodes; complex blocks remain inline HTML when needed to retain source behavior.
- 98 public attachment URLs are represented as HTML pages with their captured title, body, caption, image references, canonical and fragment evidence.
- The media inventory selects 420 uploaded source files across 422 observed public URL paths at 414,443,545 bytes. Two missing case-sensitive icon master paths are now covered by aliases whose optimized image bytes preserve the original decoded pixels. The aliases reuse existing optimized Git blobs.
- The selected media mapping now covers all 1,714 owned reference occurrences: 1,665 distinct URLs across 384 local target files. Fifteen third-party theme-demo image references are separately recorded as external and remain outside owned-media coverage.
- Nine source-head fields or explicit absences match the frozen source evidence for all 66 selected post/page/portfolio routes.

## Remaining review items

- Fifteen external Pixelwars theme-demo image references remain external. Their source/CDN URLs were unavailable during recovery, so these pages still need visual review against WordPress before production launch.
- Eighty-nine selected media files exceed 1 MB. Check their actual display sizes and quality, then reduce or provide responsive variants where measurements support it before production launch.
- Comments are intentionally omitted by owner decision. The importer removes captured comment threads, avatar markup and WordPress comment submission forms from the published bodies; it creates no comment UI or link back to comment functionality.
- Other WordPress submission forms are also removed from static bodies. A preview-only link points to the corresponding live page when a non-comment form needs a backend.
- The three WooCommerce routes `/cart/`, `/checkout/` and `/my-account/` remain backend-dependent and are not implemented by GitHub Pages.
- Attachment page body content and media are imported, but the original WordPress theme shell is not copied wholesale. Visual comparison against source screenshots and full feature behavior are still outstanding.
- Internal article links retain their original WordPress URLs during preview. They will use the preserved paths after an approved domain cutover; WordPress remains available now.

## Validation

CI checks lint, importer/contract tests, media-selection and recovery-evidence tests, migrated route counts and comment omission, then builds the Hugo preview. Passing CI and deployment prove the static bundle builds; they do not establish complete source coverage or pixel-level fidelity. A final WordPress export/delta, route and media reconciliation, image review, visual walkthrough and explicit cutover approval are still required.
