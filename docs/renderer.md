# Hugo renderer

MIG-04 provides a fixture-driven Hugo theme shell. It supports ordinary Hugo pages and posts, homepage stream/sidebar, category/tag taxonomies, portfolio archive/detail shells, page metadata, feed GUID/excerpt fields and preserved WordPress HTML. Goldmark's `unsafe` option is enabled because imported content can contain validated source HTML; the importer must reject unknown or unsafe constructs according to the MIG-01 contract before publishing. `preserved_html` is rendered as-is to retain HTML details that Markdown cannot represent.

The public source theme archive and its license/custom CSS have not been supplied in this worktree. The included responsive editorial theme is original scaffolding, not a claim that it matches TheBlogger visually. No production copy, theme font, image or other image binary is included. The fixture article and its example media path are synthetic and must not be treated as migrated material.

## Build modes

Install Hugo Extended (the build currently uses no Hugo Pipes resources, but Extended is the recommended pinned CI distribution):

```sh
brew install hugo
hugo version
```

Build the non-indexable Pages preview, using the repository subpath:

```sh
hugo --minify
```

Build production-root output for local review only:

```sh
hugo --minify --config hugo.toml,hugo.production.toml --destination dist-production
```

The production config sets `https://www.pujolsluis.com/`, which matches the observed canonical host. It does not configure a domain, create a `CNAME`, publish, or switch DNS. The default output is `dist/` and contains `robots.txt` with a site-wide disallow plus no sitemap. Production mode permits indexing and emits a sitemap. The preview is public, not access-controlled.

Run the sanitized renderer checks (they build both URL modes into temporary directories):

```sh
python3 -m unittest discover -s tests/rendering -v
```

They require a `hugo` executable on `PATH` and fail on build errors. Outputs, theme CSS, canonical links, crawl directives, preserved HTML, shortcode rendering, home/listing/portfolio shells, social image metadata, feed GUID/excerpt, and presence/absence of the sitemap are checked. The public HTML snapshots have no corresponding screenshot baseline in this worktree, and source theme assets are unavailable, so visual comparisons and production-theme fidelity remain unverified.

## Content adapter expectations

MIG-02 should provide standard Hugo Markdown with front matter for title, date, slug, author, categories, tags, description and image metadata. Where conversion would change semantic HTML, the adapter should populate `preserved_html` only after its validated import transform has preserved structure and attributes. It must not feed untrusted user input into Hugo's `safeHTML`. Original media paths are emitted as authored; use `relURL` for theme-owned UI URLs so links resolve under the Pages repository prefix. The import adapter and its schema are not present in this worktree yet.

The `youtube` shortcode accepts `id`, optional `title`, and optional `start`; it uses the privacy-enhanced YouTube host and a responsive, lazy-loaded iframe. The `gallery` shortcode wraps importer-provided figure markup and requires non-empty inner content; source ordering, image URLs, alt text and captions should be copied into that markup by the adapter. These shortcodes are examples pending comparison against frozen source HTML and provider settings. Exact media path validation belongs to MIG-03/MIG-05.

When imported front matter contains approved, sanitized comments, the single-page layout renders them in source order; it never renders the comment submission form. The inspected snapshot set contains visible comment threads on 4 of 70 page snapshots and none on 13 portfolio snapshots. Imported private email/IP data must never reach front matter or output. RSS preserves an imported `guid` and `excerpt` when present, falling back to the permalink and generated summary. The exact source feed route and XML compatibility still require MIG-05 inventory and validation.

## Current limits

This shell has no source screenshot baseline, no licensed theme assets, no confirmed font files, no imported records, and no complete feature inventory. It therefore establishes the generator, base-path behavior, templates and accessibility foundation only; it does not pass MIG-04's visual-equivalence acceptance gate. Comment submission, search service behavior, galleries with interactive controls, author archive requirements, feeds and route aliases require the frozen source contract and feature decisions. Keep production disabled until those are reconciled and staging has been reviewed.
