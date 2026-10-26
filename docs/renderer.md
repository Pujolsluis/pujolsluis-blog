# Hugo renderer

MIG-04 provides a Hugo theme shell for the public preview. It supports Markdown posts, ordinary Hugo pages, homepage stream/sidebar, category/tag taxonomies, portfolio archive/detail shells, page metadata and feed GUID/excerpt fields. Imported posts use `.md` files: article text becomes Markdown, supported figures/galleries/YouTube/Gist embeds use shortcodes, and complex fidelity-critical blocks remain validated raw HTML inside the Markdown body. The Hugo security allowlist explicitly permits `text/html` alongside `text/markdown` for those blocks. This is an opt-in trusted import path, not permission to publish arbitrary HTML from untrusted submissions.

The public source theme archive and its license/custom CSS have not been supplied in this worktree. The included responsive editorial theme is original scaffolding, not a claim that it matches TheBlogger visually. The content preview source includes imported content and 420 selected upload files; merging to `master` deploys them to Pages. Synthetic renderer fixtures remain separately under `tests/rendering/fixtures` and must not be treated as migrated material.

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

MIG-02 provides a Hugo adapter with JSON front matter and Markdown post files. All imported blog posts live under `content/posts/*.md` and preserve their exact `url` and source metadata; new Markdown entries follow the [editorial guide](editorial/README.md). Page, portfolio and attachment route files retain their reviewed HTML where conversion could change their page semantics. The adapter maps only hash-verified media paths to local files; unresolved source URLs remain listed in the aggregate [preview status report](reports/content-preview.md). Theme-owned UI URLs use Hugo's `relURL` so navigation resolves under the Pages repository prefix.

The `youtube` shortcode accepts `id`, optional `title`, and optional `start`; it uses the privacy-enhanced YouTube host and a responsive, lazy-loaded iframe. The `gallery` shortcode wraps importer-provided figure markup and requires non-empty inner content; source ordering, image URLs, alt text and captions should be copied into that markup by the adapter. These shortcodes are examples pending comparison against frozen source HTML and provider settings. Exact media path validation belongs to MIG-03/MIG-05.

The importer-provided source-head fields are honored exactly: `seoTitle` controls the document title, `description` controls the description tag, `canonical` controls canonical/OG URL, and `ogTitle`, `ogDescription`, `ogImage`, `twitterTitle`, `twitterDescription`, and `twitterImage` control their matching social tags. If a key is explicitly null, its tag is omitted; only absent keys use renderer defaults. The importer is responsible for rewriting owned social image URLs with the selected media mapping/base path before rendering.

Comments and comment submission are intentionally not migrated. The importer removes captured comment threads, avatars and WordPress comment forms, and the rendered layout contains no comment UI. Other backend forms are removed from static bodies and bridged to their original live page in the preview. RSS preserves an imported `guid` and `excerpt` when present, falling back to the permalink and generated summary. Exact feed and archive compatibility remain under MIG-05 review.

## Current limits

The preview has no full-page source screenshot baseline, no licensed theme assets or confirmed source font files, and no complete feature inventory. It therefore establishes content and route behavior in the current Hugo shell but does not pass MIG-04's visual-equivalence gate. Search service behavior, interactive gallery controls, author archives, feeds and route aliases require remaining source reconciliation and feature decisions. Comments remain intentionally out of scope. Keep production disabled until remaining fidelity gates are reconciled and staging has been reviewed.
