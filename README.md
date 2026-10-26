# pujolsluis.com — WordPress to GitHub Pages

This repository will preserve and operate [Luis Pujols’s blog](https://www.pujolsluis.com/) as a static GitHub Pages site. The goal is to migrate every published post, page, link, image, video and relevant blog feature with 100% verified fidelity, keep publishing through Git/GitHub, and switch the existing domain only when the replacement is ready and approved.

**Current status:** a Hugo content preview is deployed at [GitHub Pages](https://pujolsluis.github.io/pujolsluis-blog/). It contains 66 selected static records (45 posts, 8 pages and 13 portfolio entries), 98 attachment pages and the reviewed media inventory. The preview is public and noindex; WordPress remains production and its domain/DNS have not changed. Comments are intentionally omitted. Fidelity is still under review: missing source assets, an oEmbed endpoint, three backend-dependent commerce pages, large images and visual comparison remain open. See the [content preview report](docs/reports/content-preview.md); no 100% fidelity or production-readiness claim is being made.

## Architecture and constraints

- Chosen target: Hugo static output on GitHub Pages. Hugo owns Markdown/front matter authoring and rendering; the WordPress importer must provide a Hugo adapter. Preserve rendered HTML/shortcode output wherever Markdown conversion would lose source details. MIG-01 freezes the contracts; MIG-04 implements Hugo.
- Authoring: edit content and upload media through GitHub or local Git, preview in a PR, then merge to `master`. GitHub Actions lint, test, build and deploy validated output. Future-dated posts require a scheduled build or explicit publish action; GitHub Pages itself runs no WordPress/PHP/database.
- Preview: `https://pujolsluis.github.io/pujolsluis-blog/` (verify deployment availability). Support this repository prefix and the later production root independently. Preview is public, `noindex, nofollow`, disallowed in robots.txt, and has no sitemap or production CNAME. These settings are not access control.
- Preserve the observed canonical host `https://www.pujolsluis.com/`; the apex currently redirects there. The public homepage inspected on 2026-10-24 references TheBlogger, Pixelwars shortcodes, Jetpack, media players and other plugin assets. Asset presence is evidence to investigate, not proof that every plugin feature is active. `/wp-sitemap.xml` returned 404; discover other inventory sources.
- A WXR export contains content and attachment records, **not media bytes or complete site configuration**. Obtain full uploads, settings/theme/custom CSS and rendered source snapshots separately. Keep raw exports, private drafts, comment email/IP data and credentials outside this public repository. `private-export/` is ignored as an extra precaution.
- GitHub Pages has a hard 1 GB published-site limit, and its source repository has a recommended 1 GB size. Keep the WordPress backup and full-resolution masters outside this public repo. The current inventory commits 420 selected upload files at 414,443,545 bytes for 422 public URL paths, as ordinary Git files. Eighty-nine selected files remain over 1 MB and need display-size/performance review before launch. Preserve required public paths and verify dimensions, quality and references; the open optimization and missing-reference details are in the [content preview report](docs/reports/content-preview.md). Do not add unneeded size variants or substitute unverified similarly named files.
- Preserve exact public media paths for required images and verify them from a source URL manifest. Crawl absence is not proof that an old path is unused. Classify every discovered upload and WordPress-generated size variant as required or intentionally excluded, and record the reason and compatibility disposition for each exclusion.
- Third-party video embeds retain provider identity and settings; verify playback, but provider uptime remains external. Comments are intentionally omitted. WordPress-dependent search, forms, subscriptions, query routes and HTTP redirects need explicit compatibility decisions. GitHub Pages cannot reproduce arbitrary server behavior. Any accepted deviation must be recorded; it prevents a claim of literal 100% equivalence for that behavior.

## Fidelity release contract

“100%” is a release gate, not an assertion about an unbuilt site. Freeze the source and reconcile WXR, media archive, crawl, feeds/API and available sitemaps. Every record gets a stable source ID and per-item evidence; samples alone cannot establish completeness.

1. **Content:** every published post/page retains text, headings, ordered structures, code whitespace, Unicode, dates/time zones, authors, categories/tags, captions, alt text, anchors and embed placement. Unknown blocks/shortcodes fail import. Keep drafts private and excluded from public output.
2. **Assets:** keep owned source masters byte-for-byte in the private backup; for each required optimized repository image, verify source/output SHA-256, size, type, dimensions and references. Map every image, srcset, poster, CSS image, download, audio and video reference. Remove unintended dependency on WordPress hosting before cancellation.
3. **URLs and discovery:** preserve original paths, fragments, archives, pagination, feeds/GUIDs, attachments, outbound URLs and metadata. Check exact URL paths including case on every build from a committed manifest; crawl absence never licenses deleting an old route. Test both preview subpath and production root. Inventory query aliases, trailing-slash and encoded URL variants. Record pre-existing broken external links separately. Keep canonical/social metadata and image sitemap entries consistent.
4. **Appearance and behavior:** compare every public page at desktop/tablet/mobile viewports with matching browser/fonts. Allow no unexplained differences; document any nondeterministic masks and manually verify those regions. Review optimized images at their actual rendered sizes for visible artifacts, correct crop/orientation, transparency, captions and alt text. Exercise navigation, galleries, search, players and discovered backend features.
5. **Launch:** zero missing records/assets/routes, no unexplained diffs or unaccepted behavioral differences, passing CI, owner editorial walkthrough, final delta import reconciliation, rollback rehearsal and explicit cutover approval. Attach reports with counts and denominators.

## Independently executable issue plan

Each task has a checked-in issue specification under [docs/issues](docs/issues/), with inputs, owned paths, verification commands and completion criteria. The commands named in those issues are deliverables to implement, not existing migration tooling.

| Task | GitHub issue | Prerequisites |
| --- | --- | --- |
| MIG-01: Capture source inventory and freeze migration contracts | [#1](https://github.com/Pujolsluis/pujolsluis-blog/issues/1) | Ready |
| MIG-02: Implement deterministic WordPress content import | [#2](https://github.com/Pujolsluis/pujolsluis-blog/issues/2) | MIG-01 |
| MIG-03: Select, optimize and map required media | [#3](https://github.com/Pujolsluis/pujolsluis-blog/issues/3) | MIG-01 |
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

Use issue-scoped tasks for parallel work, each in its own worktree/branch (`codex/mig-NN`). Review each PR and its evidence, resolve integration conflicts, then run the complete fidelity gate. Tasks with unmet prerequisites are not ready; “independent” means scoped fixture-driven execution within each dependency wave.

## Hugo renderer

MIG-04 adds the Hugo theme shell and synthetic renderer fixtures. See [docs/renderer.md](docs/renderer.md) for installation, preview/production-root builds, content adapter expectations and current visual-fidelity blockers. The default `hugo --minify` build is a public, non-indexable preview below `/pujolsluis-blog/`; it has no sitemap or production `CNAME`. Production-root output is for local review and requires separate approval before any domain or deployment change.

## CI/CD included now

[CI and Pages](.github/workflows/pages.yml) runs on PRs targeting `master`, pushes to `master`, and manual dispatch. It installs pinned Ruff, lints Python, runs unittest safety checks, builds the temporary preview and uploads a Pages artifact. Actions use the latest stable releases verified on 2026-10-24, pinned to full commit SHAs. Both jobs use Ubuntu 24.04 to avoid runner-label migration notices. The workflow packages `artifact.tar` directly and uploads it with the current `upload-artifact` release, avoiding an older transitive dependency in the Pages upload wrapper. Deployment depends on successful checks and is restricted to `master`; PRs never deploy. The deploy job alone receives `pages: write` and `id-token: write` and uses the `github-pages` environment.

CI now runs importer, media, content privacy/count, and migrated Hugo route checks in addition to lint and a minified build. It still does **not** establish visual parity with every source screenshot or replace the remaining feature and final-delta gates. Hugo builds and Pagefind (if selected after feature inventory) remain static; production acceptance still requires exact route/metadata/feed reconciliation and measured published-output size.

Run locally with Python 3.12 and Hugo:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
brew install hugo
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v
hugo --minify
.venv/bin/python -m http.server 8000 --directory dist
```

Set repository Pages publishing source to **GitHub Actions**. `master` is the intended default branch. MIG-10 adds required checks/branch protections according to account capabilities. MIG-07 updates CI to build Hugo in coordination with this renderer.

## Domain cutover and recovery

Keep WordPress serving production while staging is reviewed. Capture DNS, hosting backups and the current deployment revision; verify domain ownership without switching web traffic. After approval, briefly freeze edits, import the final delta and rerun the complete gate. Deploy the production-root configuration with canonical URLs and sitemap, configure the Pages custom domain and web DNS, and verify apex/www redirects and HTTPS. Preserve unrelated MX/TXT records.

Check every legacy route and critical interaction after launch. On missing content, broken HTTPS or critical functionality, restore prior web DNS and the previous artifact; retain the source host and backups for at least 14 days and until explicit acceptance of shutdown. DNS rollback is subject to caching, so rehearse it before launch.

## Inputs still required

The owner-provided backup is available locally at `~/Desktop/pujolsluis-wordpress-backup` and contains the WXR export, uploads and themes; keep it outside this public repository. A hash-bound initial export and source-page captures supplied the current preview, but source completeness remains unverified until a final export/delta and the full route, media and feature inventories reconcile. The backup's earlier 1.15 GB disk footprint is not the Pages output size; the selected media outputs currently total 414,443,545 bytes. Any missing settings/customizations, media rights, compatibility behaviors and visual differences remain tracked before launch. DNS access is needed only at cutover. Public crawling alone cannot prove all content was discovered.

Commerce and other backend-dependent capabilities remain owner decisions pending the feature inventory. Record each observed feature and its disposition; no functionality may be omitted silently.

## References

- [WordPress export contents and exclusions](https://developer.wordpress.org/cli/commands/export/)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
- [GitHub Pages custom Actions workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub repository file limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits) and [Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
- [Adding files to a GitHub repository](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
- [Hugo GitHub Pages deployment](https://gohugo.io/host-and-deploy/deploy-to-github-pages/), [URL aliases](https://gohugo.io/content-management/urls/#aliases) and [image processing](https://gohugo.io/content-management/image-processing/)
- [Montemagno: rebuilding a blog as a static site with Hugo and GitHub Pages](https://montemagno.com/rebuilding-my-blog-as-a-static-site-with-github-copilot-cli/) — useful patterns include Markdown/front matter, exact media paths, Hugo aliases, custom feed compatibility, shortcode-based embeds, per-build URL manifests and CI. That article migrated Ghost, whose export/editor and URL/feed behavior differ from this site’s WordPress/WXR source; its Ghost-specific facts are not assumptions about this migration. Hugo aliases on Pages generate static HTML/meta-refresh pages with canonical links; they are not HTTP 301 responses.
