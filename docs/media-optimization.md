# Media inventory, optimization and recovery evidence

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

The inventory originally identified 15 missing body paths and two missing attachment-page image masters. Both icon masters now have hash-verified case-variant outputs in `migration/assets/recovery-evidence.json`; their live source hashes match the backup files, and their optimized outputs preserve decoded pixels. The Typography image path `sites/12/2016/08/01-300x199.jpg` is now covered by three locally generated variants from the verified owner upload `2016/08/01.jpg`. The theme demo WXR records the 300×199 derivative and its use on that page. The original derivative bytes are absent, so the new files are reconstructed outputs rather than byte-identical recoveries. Fourteen other theme-demo paths remain external fidelity gaps.

| WXR source | Missing public paths | Available related attachment evidence |
| --- | --- | --- |
| Page 1999, About Me | `sites/20/2016/08/about-1024x683.jpg` | Attachment 1968 (`2016/08/about.jpg`) is available; the requested derivative was not found and visual/crop equivalence is unverified. |
| Portfolio 333, Planet Unknown | `sites/12/2017/02/01.jpg`, `02.jpg`, `03.jpg` | Same-parent attachment 1994 (`unknown.jpg`) is available, but it is a different named image and is not a substitute. |
| Portfolio 354, Blank Space | `sites/12/2017/02/blank2.jpg`, `blank3.jpg`, `blank4.jpg` | Same-parent attachment 1988 (`blank1.jpg`) is available, but it is a different portfolio image and is not a substitute. |
| Portfolio 342, L'Envers des Contes | `sites/12/2017/02/kennes2.jpg`, `kennes3.jpg`, `kennes4.jpg` | Same-parent attachment 1993 (`kennes1.jpg`) is available, but it is a different portfolio image and is not a substitute. |
| Portfolio 359, Stages | `sites/12/2017/02/stages2.jpg`, `stages3.jpg`, `stages4.jpg`, `stages5.jpg` | Same-parent attachment 1976 (`stages1.jpg`) is available, but it is a different portfolio image and is not a substitute. |
| Attachment 31, `cropped-Pujolsluis-icon.png` | `2018/06/cropped-Pujolsluis-icon.png` | WXR master is 512×512 and absent from uploads. A 300×300 same-attachment derivative exists, but the live page's HTML references the missing master with CDN resize queries, never the derivative URL itself; it is not substituted. |
| Attachment 34, `cropped-Pujolsluis-icon-1.png` | `2018/06/cropped-Pujolsluis-icon-1.png` | WXR master is 240×208 and absent from uploads. Only a 150×150 derivative exists, which is not a matching displayed source; it is not substituted. |

The manifest still contains exactly 240 `published_body_path_mappings`, with 225 included and 15 marked blocked in the source inventory, 305 rendered-page paths, 98 attachment-route paths (96 included, two recovered by the sidecar), and 71 hash-bound live-rendered-body paths. One of the 15 blocked body paths is covered by the derived variants above; the other 14 remain explicit third-party dependencies. The live-body evidence names posts `wp:279`, `wp:274`, `wp:1194`, `wp:1343`, and `wp:1450`, with exact routes and body HTML hashes in the manifest. Across 2,402 backup files, 420 source files (453,897,778 bytes) map to 422 public paths. Counting source bytes once per public path gives 455,880,308 bytes; lossless selected outputs total 414,443,545 bytes, saving 41,436,763 bytes across the mappings. The three Typography variants add 286,725 bytes, bringing the static image output total to 425 files and 414,730,270 bytes. The other 1,982 files are excluded as 1,855 unused generated sizes, 90 unreferenced uploads and 37 non-image uploads; their source bytes are totaled by reason in the manifest. Of the 422 manifest paths, 89 remain over the 1 MB target. Per-role byte totals are in `role_totals`; they overlap when one image serves more than one route or role.

The two lowercase icon master paths now have hash-verified recoveries. The backup files `cropped-Pujolsluis-Icon.png` (attachment 41, 512×512, SHA-256 `f9b1e129…`) and `cropped-Pujolsluis-Icon-1.png` (attachment 44, 240×208, SHA-256 `a31502ba…`) match the live requested bytes exactly; their repository aliases are losslessly optimized counterparts whose decoded pixel streams match the sources. The sidecar records both source and output hashes.

## Optimization contract

Run the optimizer only after regenerating the manifest and verifying that source hashes still match:

```sh
python3 scripts/import_media/optimize.py \
  --manifest migration/assets/manifest.json \
  --backup-uploads ~/Desktop/pujolsluis-wordpress-backup/uploads \
  --static-root static
```

It selects only `required-content-candidate` files. JPEGs use `jpegtran -copy all -optimize`, which keeps the original DCT image coefficients and metadata while improving Huffman coding. The source and output are decoded to PNG and their pixel streams are compared. Progressive JPEG output is disabled because the system decoder showed small rendered-pixel differences for that conversion. PNG IDAT data is recompressed with zlib level 9 only if the result is smaller; all non-IDAT chunks, including transparency and metadata, are retained, and decoded pixel streams are compared. GIFs are copied byte-for-byte because no safe GIF optimizer is part of the available toolchain. The output path keeps every exact referenced URL, case and extension. Source/output hashes, dimensions, sizes, optimization method and pixel-equivalence result are added to the manifest. Re-running the optimizer from the same source tree is deterministic.

The 420 selected MIG-03 source assets remain losslessly optimized; the original full-size `01.jpg` master is unchanged. The three Typography derivatives are separate JPEG files generated from the verified 1920×1273 owner upload at quality 80: 300×199 for the body and Open Graph image, 640×424 for the Twitter image, and 710×471 for the full-width body image. They add 286,725 bytes after a lossless `jpegtran -copy all -optimize` pass. The files were visually reviewed at their output dimensions. Exact original derivative bytes and encoder settings were unavailable, so the generated variants are not claimed to be byte- or pixel-identical to WordPress CDN outputs. The wider site still lacks frozen screenshot comparison at agreed viewports. Other files above the 1 MB target remain flagged for display-size and quality review. The repository uses ordinary Git blobs; full-resolution masters and the original backup stay outside it. Snapshot HTML remains outside Git; its hash and page URL/file map are recorded in the manifest.

Theme-package references are evidence separate from upload references. The backup includes TheBlogger sources, but the package also contains admin and demo assets, and the backup does not establish which conditional theme features were rendered on public pages. CSS-only references to conditional loader/gallery/player artwork are recorded as evidence in the manifest and are not copied as upload images. MIG-04 must decide which theme behaviors it reproduces and include only the theme files it actually references.

Run the suite with:

```sh
python3 -m unittest discover -s tests/import_media -v
```

Check the recorded outputs with:

```sh
python3 scripts/import_media/check.py --manifest migration/assets/manifest.json --static-root static
```

The checker validates selected output hashes, sizes and signatures, and now also validates the generated variants' hashes and JPEG dimensions. It compares every published-body, rendered-page, attachment-route and hash-bound live-body mapping against the canonical `assets[].output_paths` records, and fails if any owned upload in a hash-bound live body is neither selected nor explicitly blocked. It warns on outputs above the 1 MB role target. The 14 classified external theme-demo paths appear as warnings and remain MIG-08 fidelity blockers until reviewed or resolved; a successful checker exit does not mark the full archive fidelity gate complete. All 225 available WXR body paths, 96 available attachment-route image paths, both verified icon aliases and all 71 live-rendered-body paths are covered.
