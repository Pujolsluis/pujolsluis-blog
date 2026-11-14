# Content preview status

This report describes the repository's reviewed Hugo content selection. GitHub Pages reflects the cleanup after the associated pull request is merged and deployed. WordPress remains the production site, and the preview remains noindex.

## Imported preview scope

- All 45 authored blog posts remain Markdown under `content/posts/`. The selection retains two pages and 22 non-demo attachment routes; no theme demo portfolio routes are published.
- The [hash-bound exclusion ledger](../../migration/theme-demo-exclusions.json) identifies 19 published demo content records (six pages, twelve portfolio entries and the portfolio section index), 76 demo attachment wrappers, and 18 selected demo-only media files.
- The 18 removed media outputs totaled 6,225,861 bytes. Two logo images referenced by both theme pages and authored posts remain. All media paths linked from the 45 posts remain in the selected static assets.
- The selected output set now contains 404 media paths totaling 408,217,684 bytes. The earlier aggregate reference report (1,714 owned reference occurrences across 384 local targets) predates these exclusions and is historical; rerun retained-route reconciliation before launch.
- The 45 posts retain their original routes, Markdown conversion, links, code, image/gallery shortcodes, video and Gist embeds, source metadata and SEO evidence.

## Remaining review items

- Fifteen external Pixelwars theme-demo image references belonged to the excluded demo routes and are no longer part of the published preview.
- Review retained image display dimensions and quality, then create responsive variants only where they improve loading without reducing visible quality.
- Comments are intentionally omitted by owner decision. The importer removes captured comment threads, avatar markup and WordPress comment submission forms; it creates no comment UI or comment links.
- Other WordPress submission forms are removed from static bodies. A preview-only link points to the corresponding live page when a retained page needs a backend.
- The three WooCommerce routes `/cart/`, `/checkout/` and `/my-account/` remain backend-dependent and are not implemented by GitHub Pages.
- The retained attachment page bodies use the captured media content without copying the original WordPress theme shell. Visual comparison against source screenshots and full feature behavior are still outstanding.
- Internal article links retain their original WordPress URLs during preview. They will use the preserved paths after an approved domain cutover; WordPress remains available now.

## Validation

CI checks lint, importer/contract tests, media-selection and recovery-evidence tests, migrated route counts, exclusion policy and comment omission, then builds the Hugo preview. Passing CI and deployment prove the static bundle builds; they do not establish complete source coverage or pixel-level fidelity. Rebind the exclusion ledger to the final WXR export, reconcile retained routes/media, review image quality, complete the visual walkthrough and approve the production cutover before switching the domain.
