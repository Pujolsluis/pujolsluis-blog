# pujolsluis.com — WordPress to GitHub Pages

This repository will preserve and operate [Luis Pujols’s blog](https://www.pujolsluis.com/) as a static GitHub Pages site. The goal is to migrate every published post, page, link, image, video and relevant blog feature with 100% verified fidelity, keep publishing through Git/GitHub, and switch the existing domain only when the replacement is ready and approved.

**Current status:** planning and CI bootstrap only. No posts or media have been imported and fidelity has not yet been verified. The temporary Pages landing page explicitly identifies itself as a migration preview. WordPress remains the production site. No DNS or production custom-domain change is part of this initialization.

## Architecture and constraints

- Proposed target: a statically generated blog, with Astro as the initial candidate, preserved article HTML where Markdown would lose fidelity, structured metadata, and original media. MIG-01/04 validate and lock this choice after inventory.
- Authoring: edit content and upload media through GitHub or local Git, preview in a PR, then merge to `master`. GitHub Actions lint, test, build and deploy validated output. Future-dated posts require a scheduled build or explicit publish action; GitHub Pages itself runs no WordPress/PHP/database.
- Preview: `https://pujolsluis.github.io/pujolsluis-blog/` (verify deployment availability). Support this repository prefix and the later production root independently. Preview is public, `noindex, nofollow`, disallowed in robots.txt, and has no sitemap or production CNAME. These settings are not access control.
- Preserve the observed canonical host `https://www.pujolsluis.com/`; the apex currently redirects there. The public homepage inspected on 2026-10-24 references TheBlogger, Pixelwars shortcodes, Jetpack, media players and other plugin assets. Asset presence is evidence to investigate, not proof that every plugin feature is active. `/wp-sitemap.xml` returned 404; discover other inventory sources.
- A WXR export contains content and attachment records, **not media bytes or complete site configuration**. Obtain full uploads, settings/theme/custom CSS and rendered source snapshots separately. Keep raw exports, private drafts, comment email/IP data and credentials outside this public repository. `private-export/` is ignored as an extra precaution.
- GitHub Pages has a **hard 1 GB limit on published site output** and separately **recommends keeping the source repository below 1 GB**; these are different constraints. Measure both repository and built output, with headroom. Keep owned original masters byte-for-byte in Git LFS when appropriate for repository size and recovery, but do not copy every WordPress-generated size into deployed output by default. Generate/package only responsive renditions needed by observed content and actual layouts. If measured output cannot fit with agreed headroom, pause the Pages architecture decision and get owner agreement for owned external asset hosting or another platform. Never silently omit, transcode originals, or hotlink to WordPress to claim fidelity.
- Media inventory must reconcile original masters, attachment records, rendered crawl/source snapshots, and every observed legacy media URL including size-suffixed WordPress variants and CDN aliases. Record source URL, references, destination/compatibility action, hash and dimensions. A crawl that did not observe a URL is not evidence that a WordPress variant is unused: choose an explicit compatibility policy for unobserved historical variants (preserve aliases/redirect mapping where supported, retain files where required, or record an accepted limitation). Test known legacy URLs and references after build.
- Use Astro's processed image assets for generated responsive renditions; public-directory assets bypass that processing. Choose a deliberately bounded width set only after measuring the blog-column, gallery and hero breakpoints against source dimensions; do not hard-code widths before the rendered-layout inventory provides evidence. Report generated variant counts and bytes, and check both in CI against the agreed budget. Remember that a browser generally downloads one suitable `srcset` candidate per image view, while every generated candidate still adds to published output size. Preserve source fidelity and available metadata, alt text, captions and attribution. Render standard `img`/`picture` markup with a usable fallback `src`, generated `srcset` and layout-appropriate `sizes`, intrinsic width/height (or equivalent aspect ratio), and lazy loading for below-fold images. Identify likely LCP/hero images from page layouts and prioritize their loading; do not lazy-load the likely LCP image. Preserve links to original masters where required by content.
- Production SEO includes canonical URLs, descriptive alt text, image dimensions and social preview metadata, plus an image sitemap (or an explicitly documented reason and equivalent discovery method). Staging remains excluded from indexing. CI must check broken media references and legacy mappings, built output size against the 1 GB hard cap and a lower project budget with headroom, image markup/rendition coverage, and SEO metadata. Performance gates should use repeatable browser measurements and realistic page-weight/loading budgets grounded in the inventory; do not promise a Lighthouse score without measured evidence.
- Third-party video embeds retain provider identity and settings; verify playback, but provider uptime remains external. WordPress-dependent search, comments, forms, subscriptions, query routes and HTTP redirects need explicit compatibility decisions. GitHub Pages cannot reproduce arbitrary server behavior. Any accepted deviation must be recorded; it prevents a claim of literal 100% equivalence for that behavior.

## Fidelity release contract

“100%” is a release gate, not an assertion about an unbuilt site. Freeze the source and reconcile WXR, media archive, crawl, feeds/API and available sitemaps. Every record gets a stable source ID and per-item evidence; samples alone cannot establish completeness.

1. **Content:** every published post/page retains text, headings, ordered structures, code whitespace, Unicode, dates/time zones, authors, categories/tags, captions, alt text, anchors and embed placement. Unknown blocks/shortcodes fail import. Keep drafts private and excluded from public output.
2. **Assets:** preserve owned originals byte-for-byte, verify SHA-256/size/type/dimensions and map every observed image URL and every image, srcset, poster, CSS image, download, audio and video reference. Record policy and verification for unobserved legacy size variants; a crawl alone cannot establish that they are unused. Generate only layout/content-required Astro-processed responsive renditions, preserve alt/caption/metadata, and remove unintended dependency on WordPress hosting before cancellation.
3. **URLs and discovery:** preserve original paths, fragments, archives, pagination, feeds/GUIDs, outbound URLs, attachments, media compatibility URLs and metadata. Test both preview subpath and production root. Inventory query aliases, trailing-slash and encoded URL variants. Include canonical/social metadata and image sitemap checks in production SEO validation. Record pre-existing broken external links separately.
4. **Appearance and behavior:** compare every public page at desktop/tablet/mobile viewports with matching browser/fonts. Allow no unexplained differences; document any nondeterministic masks and manually verify those regions. Exercise navigation, galleries, search, players and discovered backend features.
5. **Launch:** zero missing records/assets/routes, no unexplained diffs or unaccepted behavioral differences, passing CI including output-size, broken-media, SEO and measured performance-budget checks, owner editorial walkthrough, final delta import reconciliation, rollback rehearsal and explicit cutover approval. Attach reports with counts, denominators and measured repository/output sizes.

## Independently executable issue plan

Each task has a checked-in issue specification under [docs/issues](docs/issues/), with inputs, owned paths, verification commands and completion criteria. The commands named in those issues are deliverables to implement, not existing migration tooling.

| Task | GitHub issue | Prerequisites |
| --- | --- | --- |
| MIG-01: Capture source inventory and freeze migration contracts | [#1](https://github.com/Pujolsluis/pujolsluis-blog/issues/1) | Ready |
| MIG-02: Implement deterministic WordPress content import | [#2](https://github.com/Pujolsluis/pujolsluis-blog/issues/2) | MIG-01 |
| MIG-03: Archive original media and implement asset mapping | [#3](https://github.com/Pujolsluis/pujolsluis-blog/issues/3) | MIG-01 |
| MIG-04: Build static blog renderer matching the existing theme | [#4](https://github.com/Pujolsluis/pujolsluis-blog/issues/4) | MIG-01 |
| MIG-05: Preserve routes, metadata, feeds and blog discovery | [#5](https://github.com/Pujolsluis/pujolsluis-blog/issues/5) | MIG-01 |
| MIG-06: Define Git-based editorial operation and feature replacements | [#6](https://github.com/Pujolsluis/pujolsluis-blog/issues/6) | MIG-01 |
| MIG-07: Extend CI/CD with full migration fidelity gates | [#7](https://github.com/Pujolsluis/pujolsluis-blog/issues/7) | MIG-01 |
| MIG-08: Integrate full archive and prove fidelity in Pages staging | [#8](https://github.com/Pujolsluis/pujolsluis-blog/issues/8) | MIG-02, MIG-03, MIG-04, MIG-05, MIG-06, MIG-07 |
| MIG-09: Rehearse and execute reversible domain cutover | [#9](https://github.com/Pujolsluis/pujolsluis-blog/issues/9) | MIG-08 |
| MIG-10: Protect master and document ongoing maintenance | [#10](https://github.com/Pujolsluis/pujolsluis-blog/issues/10) | MIG-07 |


### Parallel execution

- **Wave 1:** MIG-01 establishes versioned JSON contracts for normalized content, asset mappings and routes, plus sanitized fixtures and frozen baseline conventions.
- **Wave 2:** MIG-02, 03, 04, 05, 06 and 07 run in parallel against those fixtures. Production import is not a prerequisite for fixture development. MIG-04 owns generator dependencies/package scripts; MIG-07 owns workflows; coordinate changes through those owners.
- **Wave 3:** MIG-08 integrates and verifies the complete archive. MIG-10 configures maintenance and protection in parallel once CI is stable.
- **Wave 4:** MIG-09 performs the approved cutover after acceptance, then post-launch verification and retention of WordPress for rollback.

Assign one subagent per ready issue, each in its own worktree/branch (`codex/mig-NN`). The coordinator merges contract work first, reviews each PR and evidence, resolves integration conflicts, then runs the complete fidelity gate. Do not have agents concurrently edit a shared checkout. Tasks with unmet prerequisites are not ready; “independent” means scoped fixture-driven execution within each dependency wave.

## CI/CD included now

[CI and Pages](.github/workflows/pages.yml) runs on PRs targeting `master`, pushes to `master`, and manual dispatch. It installs pinned Ruff, lints Python, runs unittest safety checks, builds the temporary preview and uploads a Pages artifact. Actions use the latest stable releases verified on 2026-10-24, pinned to full commit SHAs. Both jobs use Ubuntu 24.04 to avoid runner-label migration notices. The workflow packages `artifact.tar` directly and uploads it with the current `upload-artifact` release, avoiding an older transitive dependency in the Pages upload wrapper. Deployment depends on successful checks and is restricted to `master`; PRs never deploy. The deploy job alone receives `pages: write` and `id-token: write` and uses the `github-pages` environment.

These bootstrap tests check that the preview cannot claim the production domain or expose unexpected files. They do **not** establish migration fidelity. MIG-07 adds importer, route, media, browser and visual regression suites before migration acceptance.

Run locally with Python 3.12:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build.py
.venv/bin/python -m http.server 8000 --directory dist
```

Set repository Pages publishing source to **GitHub Actions**. `master` is the intended default branch. MIG-10 adds required checks/branch protections according to account capabilities. The current build is dependency-light scaffolding; MIG-04 replaces it with the actual renderer, and MIG-07 updates CI in coordination.

## Domain cutover and recovery

Keep WordPress serving production while staging is reviewed. Capture DNS, hosting backups and the current deployment revision; verify domain ownership without switching web traffic. After approval, briefly freeze edits, import the final delta and rerun the complete gate. Deploy the production-root configuration with canonical URLs and sitemap, configure the Pages custom domain and web DNS, and verify apex/www redirects and HTTPS. Preserve unrelated MX/TXT records.

Check every legacy route and critical interaction after launch. On missing content, broken HTTPS or critical functionality, restore prior web DNS and the previous artifact; retain the source host and backups for at least 14 days and until explicit acceptance of shutdown. DNS rollback is subject to caching, so rehearse it before launch.

## Inputs still required

WordPress export/admin access or owner-provided exports; original media archive; theme/customizations and license information; feature inventory and any external-service accounts; DNS access at cutover. Public crawling alone cannot prove all content was discovered. No source content counts or total media sizes are claimed yet.

## References

- [WordPress export contents and exclusions](https://developer.wordpress.org/cli/commands/export/)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
- [GitHub Pages custom Actions workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
