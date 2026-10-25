# Editorial workflow for the Hugo preview

This guide describes the planned Git workflow for editing this repository. The repository currently has a Hugo renderer shell and synthetic fixtures; it does not contain the imported blog or a completed migration. The included theme is scaffolding and has not been verified against the production theme. WordPress remains production while migration review is underway.

## 1. Set up a local checkout

Install Git, Python 3, and Hugo. On macOS, Hugo can be installed with Homebrew:

```sh
brew install hugo
hugo version
git clone https://github.com/Pujolsluis/pujolsluis-blog.git
cd pujolsluis-blog
```

Keep private exports, credentials, unpublished source material containing personal data, and full-resolution masters outside the public checkout. Add only approved public content and the optimized media required by the route/media inventory.

## 2. Create or edit a post

Posts belong under `content/posts/`. Use Hugo YAML front matter with the fields the renderer and importer currently understand:

```markdown
---
title: "Example article title"
date: 2026-10-25T09:00:00-04:00
slug: example-article
description: "A short, accurate summary for the article."
author: "Luis Pujols"
categories:
  - Example category
tags:
  - example tag
featured_image: "/wp-content/uploads/2026/10/example.jpg"
featured_image_alt: "Describe the meaningful content of the image."
featured_image_caption: "Optional source caption."
draft: true
---

Write the article in Markdown. Keep headings in order, use descriptive link text,
and preserve source captions, alt text, dates, links, and embed placement.
```

The sample values are illustrative and do not describe an imported article. Set `draft: true` while editing; remove that field only when the article has been reviewed and is ready for a production build. The current single-page template renders `featured_image`, `featured_image_alt`, and `featured_image_caption`. Front matter for author, categories, tags, description, and date is supported; the complete imported-content schema is still pending MIG-01/MIG-02. Do not add `preserved_html` by hand. The importer may use that renderer field only for validated source HTML that cannot safely or faithfully be represented as Markdown.

The default permalink pattern is `/:year/:month/:day/:slug/`. Treat the slug as permanent once the route is approved. Route aliases and the frozen route manifest will be governed by MIG-05 when available.

## 3. Add an image without changing its public URL

Before adding a file, confirm its exact case-sensitive public URL in the approved media inventory. For a URL such as `/wp-content/uploads/2026/10/example.jpg`, place the optimized file at:

```text
static/wp-content/uploads/2026/10/example.jpg
```

Hugo copies files below `static/` to the same path in the generated site. Do not rename an inventoried file, change its extension, create an unapproved WordPress size variant, or add the source backup/master. If the image has not been approved or optimized, ask the migration owner to update the media inventory first.

For an inline image in a post, use a relative Markdown image path from that post's output URL so both the repository preview prefix and the future root URL resolve correctly. Posts currently use four URL segments below the site root, so an example is:

```markdown
![A concise, useful description](../../../../wp-content/uploads/2026/10/example.jpg)
```

The number of `../` segments depends on the post's final permalink depth. For a featured image, set the `featured_image` URL in front matter and confirm the generated HTML in both builds. The current shell does not yet provide a dedicated content image helper or manifest validator; until MIG-03/MIG-05 add those gates, inspect the built image URL and file case manually. Never assume that a successful crawl proves an old media path is unused.

## 4. Add video or gallery content

Use only the shortcodes currently implemented by the renderer:

```markdown
{{< youtube id="VIDEO_ID" title="A descriptive video title" start="30" >}}

{{< gallery label="Kitchen project photos" >}}
<figure>
  <img src="../../../../wp-content/uploads/2026/10/example.jpg" alt="Walnut cabinets beside a white stone island">
  <figcaption>Optional source caption.</figcaption>
</figure>
{{< /gallery >}}
```

The YouTube shortcode accepts a provider video `id`, optional `title`, and optional start time in seconds. The gallery shortcode wraps supplied figure markup; include each image's exact path, source order, meaningful alt text, and caption. These are renderer examples, not verified replacements for every WordPress player, gallery, or plugin setting. Do not embed a new third-party provider or copy arbitrary HTML into `preserved_html` without an approved fidelity/security decision. The full embed and feature inventory is still outstanding.

## 5. Preview locally

Use a local Hugo server for the draft, including drafts and future-dated entries:

```sh
hugo server --buildDrafts --buildFuture
```

Open the local address printed by Hugo. A normal preview build excludes drafts and future-dated pages:

```sh
hugo --minify
```

To run the renderer checks for repository-prefix and production-root output:

```sh
python3 -m unittest discover -s tests -v
```

The tests use synthetic content. They do not validate migrated pages, the production theme, image inventory, or source screenshots. The default build targets `https://pujolsluis.github.io/pujolsluis-blog/`; local output is configured with `noindex,nofollow`, `robots.txt` disallow, and no sitemap. A hosted preview, if deployed, is public and these crawler directives are not a privacy control. Do not put confidential content in a draft or assume `draft: true` protects a file already committed to this public repository.

## 6. Review changes through a pull request

Create a branch, commit the content and required approved media, and open a pull request against `master`:

```sh
git switch -c codex/editorial-example-article
git add content/posts/example-article.md static/wp-content/uploads/2026/10/example.jpg
git commit -m "Add example article"
git push -u origin codex/editorial-example-article
```

Replace the sample names with the approved post and media paths. Include the intended public route and media paths in the PR description. Review the diff for spelling, dates/time zones, heading structure, image paths/case, alt text, captions, links, and embeds. Run the local preview and renderer checks before requesting review.

In the current workflow, a PR runs Python lint/tests and builds the temporary landing-page artifact; it does not build Hugo or provide a hosted per-PR preview. A push to `master` deploys that temporary landing page. MIG-07 must replace this behavior with Hugo validation and the preview deployment before the blog shell can be checked at the public Pages URL. After that integration, use the Actions run and deployment status to confirm a reviewed change was published. The planned repository preview remains public and noindex; it is not private review storage.

## 7. Publish a future-dated article

Hugo omits a post marked `draft: true` and omits a post whose `date` is in the future during a normal build. The local server command above opts into seeing both. Set the intended publication timestamp and timezone in `date`; do not remove `draft: true` before editorial approval.

GitHub Pages does not run Hugo on a timer. The current repository workflow has no scheduled publishing job. A future-dated article will need a scheduled build or an explicit, reviewed publish action at or after its publication time. Until that automation is implemented and tested, schedule a maintainer to merge/rebuild the post at publication time. Do not use Hugo's `--buildFuture` flag in a public deployment job before an owner has approved the publishing policy, because it makes future posts visible early.

## 8. Roll back a content change

If a change is still in a pull request, close or revise that PR. If it has merged, use GitHub's **Revert** action on the specific merge commit, or make a new commit restoring the previous content and approved media. Open a PR for that rollback and let the validated deployment workflow publish it after merge. Do not force-push or reset the shared `master` branch.

If a bad staging deployment is already public, revert promptly, verify the new Pages deployment completed, then check the affected route and media paths at the repository preview URL. Until MIG-07 replaces the current workflow, that URL is the temporary landing page and does not reflect Hugo content. Keep WordPress serving production during the migration. This guide does not authorize changing the custom domain, DNS, production deployment mode, or disabling WordPress. Domain cutover and production rollback remain subject to the separate MIG-09 approval and rehearsal.

## Still pending

The content/media contracts, importer, complete feature decisions, PR checks and deployment workflow are not integrated here. The source theme assets, licensing, frozen screenshots, and production-content reconciliation are also missing. This guide enables local fixture-driven authoring and describes the intended reviewed workflow; it does not claim that migration or production theme fidelity is complete.
