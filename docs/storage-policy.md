# Binary source storage and build artifacts

All binary files belong in **Git LFS**, regardless of size. Ordinary Git stores their small pointer files; build artifacts contain the actual asset bytes. UTF-8 text without binary controls, including textual SVG, remains normal Git. `.gitattributes` covers common image/font/audio/video/document/archive/executable formats, including uppercase extensions. The content gate also detects binary data with unknown extensions; add a specific LFS attribute for a new format before adding it. No raw private export/theme backup belongs in this public repository.

## Add binary assets safely

Install Git LFS through its [official installation instructions](https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage) before adding any binary. `git lfs version` was unavailable on the local authoring host during this checkpoint; no filters/hooks were configured to a temporary executable. Git LFS is installed on the hosted Actions runner and `actions/checkout` downloads LFS files with `lfs: true`.

```sh
git lfs version                 # Stop if the executable is unavailable.
git lfs install --local         # Configure the installed, durable executable.
# For an uncovered format/path only:
git lfs track 'path/to/new-format.ext'
git add .gitattributes path/to/asset.png
python -m scripts.check_lfs     # Check index pointers AND materialized file bytes.
git lfs ls-files
```

The storage checker examines Git's **index blobs**, not just the smudged working files. Raw binary blobs, binary-format files without pointers, malformed pointers and missing LFS attributes fail. Valid pointers require `filter=lfs diff=lfs merge=lfs -text`. Their working files must exist as regular files and match the pointer's SHA-256 and size; unresolved pointers and mismatched downloads fail with an installation/pull instruction. `--no-materialized` is available for a storage-only diagnostic and is not sufficient for building/deploying.

```sh
python -m scripts.check_lfs --history
python -m unittest discover -s tests/storage -v
python -m scripts.check_lfs --artifact dist
```

`--history` also rejects binary blobs deleted later in the same reachable history. It requires a full fetch; CI uses `fetch-depth: 0`. It does not rewrite history. If a binary is accidentally pushed, report the exact object/path/affected refs and obtain explicit approval before any history migration or force-push. A new pointer commit alone does not remove an earlier binary blob from history. No migration is needed for the audited checkpoints below.

## CI and output limits

The existing full-SHA checkout pin is retained with `lfs: true`. CI runs `git lfs fsck --objects`, checks index/history/materialization, then tests/builds. Before packaging, both the renderer preview and deployed placeholder artifacts are scanned for unresolved pointers and symlinks. Output bytes are counted against a conservative **1,000,000,000-byte ceiling**. The renderer itself also rejects pointer input/output, including an invalid manifest that mistakenly hashes the pointer text. Its normal output may contain binary media/font bytes; the prohibition concerns ordinary Git storage, not the materialized website artifact.

GitHub's [LFS documentation](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage) explicitly states that LFS cannot be used with GitHub Pages sites. The [checkout action](https://github.com/actions/checkout#usage) separately supports downloading LFS files. This project's custom Actions strategy materializes build inputs before packaging ordinary output bytes; that is a build strategy requiring validation, **not a documented exception or support guarantee** for direct Pages/LFS hosting. Pages will never be asked to serve pointer files. The existing placeholder remains the deployed artifact until source/media/hosting acceptance and human merge approval.

LFS source storage does not increase the [Pages published-site limit of 1 GB](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits). LFS object-size, storage and bandwidth allowances are separate. A large original-media archive still needs an approved hosting plan; it must not be silently omitted, downsampled or hotlinked to fit. The actual first hosted LFS-object download must be validated when an approved binary is introduced; this policy does not add a demo binary or claim that such a remote download has already occurred.

## Initial branch/history audit

On 2026-10-24, after fetching all current refs, **108 distinct reachable Git blobs** across local/origin master and every open migration branch were inspected by complete content: **zero binary blobs** at tips or in reachable history. Exact remote checkpoints:

| Ref / PR | Audited head | Binary blobs at tip / history |
| --- | --- | --- |
| master | `268d1c64db9e9b7742685bd542fad93663b7b37f` | 0 / 0 |
| MIG-01 #11 | `5a6c288f103d68ffeb3b2e5c906636dc2b15183b` | 0 / 0 |
| Public inventory #12 | `74fcf1d500d407feca209f1b5618f601b7d9207f` | 0 / 0 |
| Renderer #13 | `dab827ca886d81de5c43642efbb64f14dffc7796` | 0 / 0 |
| Importer #14 | `e5c7fcd273a58cbe3b13866e330e620674ca29ae` | 0 / 0 |

The fixture `example.svg` is text. Font bytes reside in ignored npm dependencies and generated output; only package versions/license texts are tracked. Storage tests generate synthetic binary bytes and pointer/index states solely in temporary repositories; no binary test fixture is committed. The final policy commit adds text files only and must pass the same gate after staging and in CI. No default/shared history was rewritten, and no force-push was performed.
