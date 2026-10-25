# Media inventory and lossless optimization

`migration/assets/manifest.json` is the generated, path-by-path record for MIG-03. It records every regular file under the supplied uploads tree, its SHA-256 and size, each WXR content reference, attachment record and parent ID when available, and an explicit include/exclude reason plus compatibility disposition. The private backup remains the source of truth; do not copy the uploads tree wholesale.

Regenerate the inventory from a read-only backup, then add the private rendered-page snapshots supplied for the live-site audit:

```sh
python3 scripts/import_media/inventory.py \
  --wxr ~/Desktop/pujolsluis-wordpress-backup/pujolsluisblog.WordPress.2026-10-24.xml \
  --uploads ~/Desktop/pujolsluis-wordpress-backup/uploads \
  --theme ~/Desktop/pujolsluis-wordpress-backup/themes/theblogger \
  --homepage-html /private/tmp/pujolsluis-homepage.html \
  --output migration/assets/manifest.json
python3 scripts/import_media/augment_rendered.py \
  --manifest migration/assets/manifest.json \
  --snapshots /private/tmp/pujolsluis-source-pages-20261025 \
    /private/tmp/pujolsluis-source-portfolios-20261025 \
  --attachment-audit /private/tmp/pr12-attachment-route-audit.json
python3 scripts/import_media/augment_live_bodies.py \
  --manifest migration/assets/manifest.json \
  --bodies-json /private/tmp/pujolsluis-live-rendered-manifest.json \
  --uploads ~/Desktop/pujolsluis-wordpress-backup/uploads \
  --routes-json migration/assets/live-body-routes.json
```

The WXR audit finds 240 distinct image URL paths in published post, page and portfolio bodies; 225 have source bytes and 15 are missing. The rendered HTML audit adds image-card `src`/`srcset`, lazy image attributes, and actual Open Graph/Twitter image URLs from the homepage and captured published pages/portfolio routes. A separate hash-bound audit of five live rendered post bodies found 71 distinct owned upload paths, including 16 present in the backup but absent from the raw WXR bodies. All 16 are selected at their exact paths; the remaining 55 were already selected through other evidence. The manifest records 305 rendered-page paths and selects 420 source files for 422 exact public paths (aliases included). It inventories all 2,402 backup files but selects only confirmed live content assets. Exact source/output byte totals and SHA-256 values are in the manifest. The source URLs include WordPress multisite prefixes such as `/sites/12/`; these prefixes are retained in each public output path even though the backup has flattened those files into its local `uploads/` tree. The manifest links exact WXR attachment records and also marks inferred generated-size-to-base-attachment relationships.

The WXR has 39 image paths in `_essb_cached_image` fields alone. They are candidates, not proof of use. The rendered-page audit confirmed all 39 paths in actual Open Graph/Twitter output and includes them. A further 98 self-canonical attachment URLs are HTML pages. Their primary displayed image, actual image srcset and head image references are parsed from private source captures and included only when those exact upload paths exist in the backup. See per-path roles and evidence in the manifest.

Every other upload is explicitly classified. A filename with a WordPress `-WIDTHxHEIGHT` suffix and no published-content reference is recorded as an unused generated size; other unreferenced images are orphans for this migration; non-image uploads are listed but left to their owning feature migration. Old excluded URLs receive no redirects or aliases unless a later approved route inventory requires one. The manifest records 51 video-provider URLs from published records. Video embeds remain external; this tool never downloads video bytes.

## Recovery status

The 15 missing body references are recorded as pre-existing broken source paths: exact, backup-relative and observed `i0.wp.com` CDN requests returned HTTP 404 with non-image responses. Two additional missing image masters are referenced by attachment pages. The manifest groups these paths by WXR source item and lists attachment/sibling evidence. A same-parent sibling attachment is not treated as a visual substitute; no replacement was verified. All 17 exact paths remain hard blockers for complete URL coverage and must not be silently dropped or replaced.

| WXR source | Missing public paths | Available related attachment evidence |
| --- | --- | --- |
| Page 1998, Typography | `sites/12/2016/08/01-300x199.jpg` | Attachment 9 (`2016/08/01.jpg`) is available under the same attachment's base path. The specific derivative was not found and visual/crop equivalence is unverified. |
| Page 1999, About Me | `sites/20/2016/08/about-1024x683.jpg` | Attachment 1968 (`2016/08/about.jpg`) is available; the requested derivative was not found and visual/crop equivalence is unverified. |
| Portfolio 333, Planet Unknown | `sites/12/2017/02/01.jpg`, `02.jpg`, `03.jpg` | Same-parent attachment 1994 (`unknown.jpg`) is available, but it is a different named image and is not a substitute. |
| Portfolio 354, Blank Space | `sites/12/2017/02/blank2.jpg`, `blank3.jpg`, `blank4.jpg` | Same-parent attachment 1988 (`blank1.jpg`) is available, but it is a different portfolio image and is not a substitute. |
| Portfolio 342, L'Envers des Contes | `sites/12/2017/02/kennes2.jpg`, `kennes3.jpg`, `kennes4.jpg` | Same-parent attachment 1993 (`kennes1.jpg`) is available, but it is a different portfolio image and is not a substitute. |
| Portfolio 359, Stages | `sites/12/2017/02/stages2.jpg`, `stages3.jpg`, `stages4.jpg`, `stages5.jpg` | Same-parent attachment 1976 (`stages1.jpg`) is available, but it is a different portfolio image and is not a substitute. |
| Attachment 31, `cropped-Pujolsluis-icon.png` | `2018/06/cropped-Pujolsluis-icon.png` | WXR master is 512×512 and absent from uploads. A 300×300 same-attachment derivative exists, but the live page's HTML references the missing master with CDN resize queries, never the derivative URL itself; it is not substituted. |
| Attachment 34, `cropped-Pujolsluis-icon-1.png` | `2018/06/cropped-Pujolsluis-icon-1.png` | WXR master is 240×208 and absent from uploads. Only a 150×150 derivative exists, which is not a matching displayed source; it is not substituted. |

The manifest contains exactly 240 `published_body_path_mappings`, with 225 included and 15 blocked, 305 rendered-page paths, 98 attachment-route paths (96 included, two blocked), and 71 hash-bound live-rendered-body paths. The latter evidence names posts `wp:279`, `wp:274`, `wp:1194`, `wp:1343`, and `wp:1450`, with exact routes and body HTML hashes in the manifest. It records source role, attachment relationship, exact public path, and source/output hashes and sizes for every selected mapping. Across 2,402 backup files, 420 source files (453,897,778 bytes) map to 422 public paths. Counting source bytes once per public path gives 455,880,308 bytes; lossless outputs total 414,443,545 bytes, saving 41,436,763 bytes across the mappings. The other 1,982 files are excluded as 1,855 unused generated sizes, 90 unreferenced uploads and 37 non-image uploads; their source bytes are totaled by reason in the manifest. Of the 422 mapped paths, 89 remain over the 1 MB target, including the prior 78 flagged paths and 11 newly selected outputs. Per-role byte totals are in `role_totals`; they overlap when one image serves more than one route or role.

The two missing lowercase icon masters remain blocked. The backup has case-variant attachments `cropped-Pujolsluis-Icon.png` (attachment 41, 512×512, SHA-256 `f9b1e129…`) and `cropped-Pujolsluis-Icon-1.png` (attachment 44, 240×208, SHA-256 `a31502ba…`), corresponding to distinct WXR attachments from missing IDs 31 and 34. Matching dimensions and case-only filename differences do not establish byte identity or visual lineage; no hash-bound recovered blob exists for either requested lowercase master. Their exact candidate metadata is retained in the manifest, and neither candidate is substituted.

## Optimization contract

Run the optimizer only after regenerating the manifest and verifying that source hashes still match:

```sh
python3 scripts/import_media/optimize.py \
  --manifest migration/assets/manifest.json \
  --backup-uploads ~/Desktop/pujolsluis-wordpress-backup/uploads \
  --static-root static
```

It selects only `required-content-candidate` files. JPEGs use `jpegtran -copy all -optimize`, which keeps the original DCT image coefficients and metadata while improving Huffman coding. The source and output are decoded to PNG and their pixel streams are compared. Progressive JPEG output is disabled because the system decoder showed small rendered-pixel differences for that conversion. PNG IDAT data is recompressed with zlib level 9 only if the result is smaller; all non-IDAT chunks, including transparency and metadata, are retained, and decoded pixel streams are compared. GIFs are copied byte-for-byte because no safe GIF optimizer is part of the available toolchain. The output path keeps every exact referenced URL, case and extension. Source/output hashes, dimensions, sizes, optimization method and pixel-equivalence result are added to the manifest. Re-running the optimizer from the same source tree is deterministic.

No source image is resized or lossy-re-encoded. Private rendered HTML snapshots are available, but no visual screenshots or measured display sizes were supplied; native source dimensions are therefore the conservative ceiling. I spot-checked the icon PNG and one JPEG source/output pair. The manifest records that limited review and notes that per-image rendered-pixel and target-viewport review was not performed. Files above the 1 MB per-image target remain flagged for later display-size and visual review; they are not silently omitted or degraded. The repository uses ordinary Git blobs; full-resolution masters and the original backup stay outside it. Snapshot HTML remains outside Git; its hash and page URL/file map are recorded in the manifest.

Theme-package references are evidence separate from upload references. The backup includes TheBlogger sources, but the package also contains admin and demo assets, and the backup does not establish which conditional theme features were rendered on public pages. CSS-only references to conditional loader/gallery/player artwork are recorded as evidence in the manifest and are not copied as upload images. MIG-04 must decide which theme behaviors it reproduces and include only the theme files it actually references.

Run the suite with:

```sh
python3 -m unittest discover -s tests/import_media -v
```

Check the recorded outputs with:

```sh
python3 scripts/import_media/check.py --manifest migration/assets/manifest.json --static-root static
```

The checker validates all selected output hashes, sizes and signatures, then compares every published-body, rendered-page, attachment-route and hash-bound live-body mapping against the canonical `assets[].output_paths` records. It also fails if any owned upload in a hash-bound live body is neither selected nor explicitly blocked. The optimizer refreshes those projections from the selected asset records after writing outputs. It warns on outputs above the 1 MB role target. Its nonzero result is expected because 15 pre-existing broken WXR paths and two missing attachment-page image masters remain hard blockers; all 225 available WXR body paths, 96 available attachment-route image paths and 71 live-rendered-body paths are mapped and included.
