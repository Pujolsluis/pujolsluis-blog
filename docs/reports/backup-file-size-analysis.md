# Backup file sizes and quality-preserving compression candidates

Full read-only inventory of `~/Desktop/pujolsluis-wordpress-backup`, including uploads, themes and top-level XML. All binary media and experimental compressed files remain outside Git. No source file was modified. Raw XML contents and EXIF/GPS values are excluded.

Measured quality-preserving opportunities are strongest in the tested PNG screenshots (36–41% smaller), followed by the tested large JPEG photographs (5–7% smaller). All 39 GIFs together save 4.63%. Exact decoded pixels and the stated metadata/animation checks passed; no source image has been replaced. JPEG/PNG figures are samples, not a forecast for the whole archive.

The backup contains **4,531 files, 1,152,227,647 bytes (1,098.85 MiB)**. The globally largest 30 files are all uploads and total **202,461,232 bytes (193.08 MiB)**. The JSON companion contains exact hashes, image probes, all type totals and the largest duplicate groups: [`backup-file-size-analysis.json`](../../migration/inventory/backup-file-size-analysis.json).

## Largest 30 files

“Original” means an attachment main file or explicit `original_image` in owner WXR metadata. “Observed” means referenced in the public crawl/WXR body. No top-30 file is classified as a generated WordPress size derivative. The largest GIF has no attachment-metadata classification, so its filename is not assumed disposable.

| Rank | Backup-relative path | Exact bytes | MiB | Dimensions | Frames / duration | Metadata evidence |
| ---: | --- | ---: | ---: | --- | --- | --- |
| 1 | `uploads/2019/01/timelinecontrol.gif` | 10,411,474 | 9.9292 | 600×1232 | 154 / 15.4s | observed |
| 2 | `uploads/2018/07/linkedinclient.gif` | 10,172,350 | 9.7011 | 800×1401 | 197 / 19.7s | original, observed |
| 3 | `uploads/2018/07/googleclient.gif` | 7,514,491 | 7.1664 | 600×1038 | 200 / 20s | original, observed |
| 4 | `uploads/2019/11/IMG_1682.jpg` | 7,392,393 | 7.0499 | 5184×3456 | 1 / static | original, observed, EXIF |
| 5 | `uploads/2019/11/IMG_1639-1.jpg` | 7,085,399 | 6.7572 | 5184×3456 | 1 / static | original, observed, EXIF |
| 6 | `uploads/2019/11/IMG_1639.jpg` | 7,085,399 | 6.7572 | 5184×3456 | 1 / static | original, observed, EXIF |
| 7 | `uploads/2019/11/IMG_1697.jpg` | 7,014,731 | 6.6898 | 5184×3456 | 1 / static | original, observed, EXIF |
| 8 | `uploads/2019/11/IMG_1677.jpg` | 6,759,873 | 6.4467 | 5184×3456 | 1 / static | original, observed, EXIF |
| 9 | `uploads/2019/11/IMG_1707-1.jpg` | 6,701,665 | 6.3912 | 5184×3456 | 1 / static | original, observed, EXIF |
| 10 | `uploads/2019/11/IMG_1707.jpg` | 6,701,665 | 6.3912 | 5184×3456 | 1 / static | original, observed, EXIF |
| 11 | `uploads/2019/11/IMG_1770.jpg` | 6,678,427 | 6.3690 | 5184×3456 | 1 / static | original, observed, EXIF |
| 12 | `uploads/2019/11/IMG_1648.jpg` | 6,568,901 | 6.2646 | 5184×3456 | 1 / static | original, observed, EXIF |
| 13 | `uploads/2019/11/IMG_1698-1.jpg` | 6,510,078 | 6.2085 | 5184×3456 | 1 / static | original, observed, EXIF |
| 14 | `uploads/2019/11/IMG_1698.jpg` | 6,510,078 | 6.2085 | 5184×3456 | 1 / static | original, observed, EXIF |
| 15 | `uploads/2021/02/Screen-Shot-2021-02-08-at-2.49.05-PM.png` | 6,435,497 | 6.1374 | 3352×1836 | 1 / static | original, observed, EXIF, ICC |
| 16 | `uploads/2019/11/IMG_1786.jpg` | 6,422,090 | 6.1246 | 5184×3456 | 1 / static | original, observed, EXIF |
| 17 | `uploads/2019/11/IMG_1649.jpg` | 6,384,163 | 6.0884 | 5184×3456 | 1 / static | original, observed, EXIF |
| 18 | `uploads/2019/11/IMG_1666-1.jpg` | 6,372,434 | 6.0772 | 5184×3456 | 1 / static | original, observed, EXIF |
| 19 | `uploads/2019/11/IMG_1666.jpg` | 6,372,434 | 6.0772 | 5184×3456 | 1 / static | original, observed, EXIF |
| 20 | `uploads/2019/11/IMG_1667.jpg` | 6,334,777 | 6.0413 | 5184×3456 | 1 / static | original, observed, EXIF |
| 21 | `uploads/2019/11/IMG_1669.jpg` | 6,212,356 | 5.9246 | 5184×3456 | 1 / static | original, observed, EXIF |
| 22 | `uploads/2019/11/IMG_1624.jpg` | 6,181,889 | 5.8955 | 5184×3456 | 1 / static | original, observed, EXIF |
| 23 | `uploads/2019/11/IMG_1735.jpg` | 6,180,563 | 5.8942 | 5184×3456 | 1 / static | original, observed, EXIF |
| 24 | `uploads/2019/11/IMG_1668.jpg` | 6,171,739 | 5.8858 | 5184×3456 | 1 / static | original, observed, EXIF |
| 25 | `uploads/2019/11/IMG_1537.jpg` | 6,111,076 | 5.8280 | 5184×3456 | 1 / static | original, observed, EXIF |
| 26 | `uploads/2019/11/IMG_1600.jpg` | 6,055,927 | 5.7754 | 5184×3456 | 1 / static | original, observed, EXIF |
| 27 | `uploads/2019/11/IMG_1574.jpg` | 6,053,165 | 5.7727 | 5184×3456 | 1 / static | original, observed, EXIF |
| 28 | `uploads/2021/02/Screen-Shot-2021-02-08-at-12.30.07-AM.png` | 6,025,965 | 5.7468 | 3360×1850 | 1 / static | original, observed, EXIF, ICC |
| 29 | `uploads/2019/11/IMG_1676.jpg` | 6,022,882 | 5.7439 | 5184×3456 | 1 / static | original, observed, EXIF |
| 30 | `uploads/2019/11/IMG_1660.jpg` | 6,017,351 | 5.7386 | 5184×3456 | 1 / static | original, observed, EXIF |

The three leading GIFs loop indefinitely and retain 154, 197 and 200 frames respectively. Their 100 ms frame durations produce 15.4, 19.7 and 20 seconds per loop. Most leading JPEGs are 5,184×3,456 photographs with EXIF; the two leading PNG screenshots are RGBA and contain both ICC and EXIF metadata. Width/height alone does not establish displayed orientation; EXIF orientation must survive optimization.

## Where the bytes are

| Area | Files | Exact bytes | MiB |
| --- | ---: | ---: | ---: |
| top-level | 2 | 2,171,756 | 2.07 |
| uploads | 2,402 | 1,076,148,970 | 1,026.30 |
| themes | 2,127 | 73,906,921 | 70.48 |

The full backup is not the deployed site: theme PHP, bundled plugin ZIPs, raw WXR and source tooling are not automatically public assets. Uploads alone are 1,076,148,970 bytes. The earlier metadata/reference audit identifies 1,075,541,365 known bytes required by complete attachment metadata plus observed references, before case repairs and site assets. Optimizing a measured subset does not prove the final Pages footprint fits.

| Extension across full backup | Files | Exact bytes | MiB |
| --- | ---: | ---: | ---: |
| `.png` | 1,461 | 536,065,580 | 511.23 |
| `.jpg` | 844 | 495,066,898 | 472.13 |
| `.gif` | 42 | 49,135,190 | 46.86 |
| `.woff2` | 384 | 17,118,684 | 16.33 |
| `.xml` | 18 | 11,657,825 | 11.12 |
| `.jpeg` | 187 | 10,742,401 | 10.24 |
| `.zip` | 5 | 9,164,733 | 8.74 |
| `.woff` | 96 | 5,611,424 | 5.35 |
| `.css` | 141 | 3,230,628 | 3.08 |
| `.webp` | 46 | 3,097,819 | 2.95 |
| `.php` | 659 | 2,958,351 | 2.82 |
| `.json` | 67 | 2,583,187 | 2.46 |
| `.ttf` | 11 | 2,071,340 | 1.98 |
| `.js` | 184 | 710,138 | 0.68 |
| `.po` | 20 | 574,575 | 0.55 |
| `.mp4` | 1 | 468,755 | 0.45 |
| `.svg` | 9 | 378,808 | 0.36 |
| `.txt` | 55 | 323,581 | 0.31 |
| `.scss` | 145 | 301,088 | 0.29 |
| `.html` | 71 | 200,529 | 0.19 |
| `.mo` | 20 | 188,469 | 0.18 |
| `.eot` | 5 | 141,316 | 0.13 |
| `.pot` | 4 | 134,006 | 0.13 |
| `.dat` | 17 | 88,197 | 0.08 |
| `.wie` | 17 | 69,715 | 0.07 |
| `.map` | 7 | 51,169 | 0.05 |
| `.otf` | 2 | 36,424 | 0.03 |
| `(none)` | 8 | 30,100 | 0.03 |
| `.md` | 4 | 26,359 | 0.03 |
| `.log` | 1 | 358 | 0.00 |

## Exact duplicates

There are **257 duplicate SHA-256 groups** and **123,126,423 bytes (117.42 MiB)** beyond one copy per payload across the full backup. Uploads account for 119,980,396 repeated bytes. These identify storage/delivery candidates, not safe deletions: every original public URL still needs the correct response bytes, and distinct attachment IDs/captions/references must remain intact.

| Repeated bytes | Copies | Paths with identical bytes |
| ---: | ---: | --- |
| 7,085,399 | 2 | `uploads/2019/11/IMG_1639-1.jpg` · `uploads/2019/11/IMG_1639.jpg` |
| 6,701,665 | 2 | `uploads/2019/11/IMG_1707-1.jpg` · `uploads/2019/11/IMG_1707.jpg` |
| 6,510,078 | 2 | `uploads/2019/11/IMG_1698-1.jpg` · `uploads/2019/11/IMG_1698.jpg` |
| 6,372,434 | 2 | `uploads/2019/11/IMG_1666-1.jpg` · `uploads/2019/11/IMG_1666.jpg` |
| 5,910,817 | 2 | `uploads/2019/11/IMG_1689-1.jpg` · `uploads/2019/11/IMG_1689.jpg` |
| 5,419,506 | 2 | `uploads/2019/11/IMG_1688-1.jpg` · `uploads/2019/11/IMG_1688.jpg` |
| 5,414,747 | 2 | `uploads/2019/11/IMG_1716-1.jpg` · `uploads/2019/11/IMG_1716.jpg` |
| 5,313,385 | 2 | `uploads/2019/11/IMG_1651-1.jpg` · `uploads/2019/11/IMG_1651.jpg` |
| 4,901,932 | 2 | `uploads/2019/11/Screen-Shot-2019-11-03-at-2.07.13-PM-1.png` · `uploads/2019/11/Screen-Shot-2019-11-03-at-2.07.13-PM.png` |
| 3,890,898 | 3 | `uploads/2021/02/IMG_9734-1.png` · `uploads/2021/02/IMG_9734-2.png` · `uploads/2021/02/IMG_9734.png` |

Storage that supports content-addressed payloads plus exact URL mapping can share duplicate bytes. Merely deleting the `-1` image or changing current HTML does not preserve old direct links on plain Pages. No deduplication was performed.

## Measured quality-preserving candidates

Only experimental outputs verified against their own source are counted as safe samples. “Lossless” below means identical decoded pixels and preserved relevant metadata/animation behavior; the optimized file bytes and SHA-256 necessarily differ. The unchanged owner backup remains the original-byte archive.

### Animated GIF: verified full corpus

All **39 upload GIFs (49,096,927 bytes)** passed frame-by-frame composed RGBA pixel, frame-duration, loop and non-graphic-control extension checks after optimization. Verified combined savings: **2,275,423 bytes (4.63%)**. Three files needed `-Okeep-empty` after the initial optimization changed empty-frame handling; unverified/default output was not accepted.

| Public upload | Before | Verified after | Saved |
| --- | ---: | ---: | ---: |
| `2019/01/timelinecontrol.gif` | 10,411,474 | 9,693,075 | 718,399 (6.90%) |
| `2018/07/linkedinclient.gif` | 10,172,350 | 9,458,812 | 713,538 (7.01%) |
| `2018/07/googleclient.gif` | 7,514,491 | 7,196,621 | 317,870 (4.23%) |

### PNG: pixel/metadata-preserving samples

IDAT-only DEFLATE recompression preserves the decompressed PNG scanline bytes and every non-IDAT chunk byte-for-byte, including ICC/gamma/EXIF and other ancillary metadata. This avoids palette reduction, resizing or color conversion. Fully verified sample outputs:

| Public upload | Before | Verified after | Saved |
| --- | ---: | ---: | ---: |
| `2019/03/Screen-Shot-2019-03-05-at-12.46.54-AM.png` | 3,202,788 | 1,847,507 | 1,355,281 (42.32%) |
| `2019/11/Screen-Shot-2019-11-03-at-2.07.13-PM.png` | 4,901,932 | 4,049,749 | 852,183 (17.38%) |
| `2019/11/Screen-Shot-2019-11-03-at-2.13.25-PM.png` | 4,554,990 | 3,629,497 | 925,493 (20.32%) |

The four largest PNGs were additionally verified:

| Public upload | Before | Verified after | Saved |
| --- | ---: | ---: | ---: |
| `2021/02/Screen-Shot-2021-02-08-at-2.49.05-PM.png` | 6,435,497 | 4,100,370 | 2,335,127 (36.29%) |
| `2021/02/Screen-Shot-2021-02-08-at-12.30.07-AM.png` | 6,025,965 | 3,585,630 | 2,440,335 (40.50%) |
| `2021/02/Screen-Shot-2021-02-08-at-12.00.01-AM.png` | 5,782,517 | 3,490,393 | 2,292,124 (39.64%) |
| `2021/02/Screen-Shot-2021-02-07-at-11.58.59-PM.png` | 5,729,362 | 3,361,655 | 2,367,707 (41.33%) |

These four samples save **9,435,293 bytes (39.36%)**, with the same dimensions, file format, decoded image bytes and ancillary metadata. No unmeasured corpus savings are extrapolated.

### JPEG: entropy optimization without re-quantization

Ten distinct large JPEG samples total **67,517,720 → 63,403,968 bytes**, saving **4,113,752 bytes (6.09%)**. Both baseline Huffman and progressive entropy encodings were tested with `jpegtran -copy all`; the smaller verified result was retained privately. Decoded pixel bytes and EXIF/ICC/comment/DPI/Adobe metadata markers were compared before accepting each sample. Quantization and resolution were not reduced.

| Public upload | Before | Verified after | Saved |
| --- | ---: | ---: | ---: |
| `2019/11/IMG_1682.jpg` | 7,392,393 | 6,940,873 | 451,520 (6.11%) |
| `2019/11/IMG_1639-1.jpg` | 7,085,399 | 6,599,894 | 485,505 (6.85%) |
| `2019/11/IMG_1697.jpg` | 7,014,731 | 6,562,632 | 452,099 (6.44%) |
| `2019/11/IMG_1677.jpg` | 6,759,873 | 6,407,871 | 352,002 (5.21%) |
| `2019/11/IMG_1707-1.jpg` | 6,701,665 | 6,280,115 | 421,550 (6.29%) |

Exact SHA-256 duplicates such as `IMG_1639.jpg` share the same input payload as their tested `-1` counterpart. The JSON links those top-file rows to the verified trial using input hash identity. This does not authorize deleting either URL.

### Archive-only text compression

The private owner WXR roundtrips exactly through gzip level 9: **2,165,608 → 203,410 bytes (90.61% saved)**. Theme text files roundtrip exactly as individual gzip payloads: **20,347,006 → 3,257,427 bytes (84.0% saved)** across 1,220 files. These are backup/archive storage candidates only. Do not substitute `.gz` files for importer XML or theme PHP/CSS/JS; restore original bytes before use. They do not reduce the deployed image footprint.

## Lossy options and metadata boundaries

JPEG re-encoding at a lower quality, image resizing, palette reduction and conversion of animated GIF to video are perceptual/behavioral changes. They may save much more, but no pixel-identical or “no quality loss” claim is made for them. A delivery derivative would require explicit visual review of fine text/gradients/photographs, animation timing and transparency, while retaining the original archive and original URL contract. No such conversion was applied.

EXIF orientation, ICC color profiles, gamma, transparency, animation durations/looping and source comments can affect appearance or behavior. Blind metadata stripping or generic image “optimize” presets are not equivalent to the measured preservation checks. EXIF/GPS values themselves are not included in this report.

## Reproduce the read-only size inventory

Use Python with Pillow (the bundled runtime uses Pillow 12.3.0), an existing private manifest from the owner-backup audit, and a report path outside the supplied backup:

```sh
python -m scripts.inventory.file_sizes \
  --backup /path/to/pujolsluis-wordpress-backup \
  --private-manifest /path/to/private-manifest.json \
  --report migration/inventory/backup-file-size-analysis.json
```

The recorded image probe used Pillow 12.3.0. Full GIF measurements and bounded 10-JPEG/4-PNG trials were supplied by the separate compression-analysis task; source/experimental binaries remain private. Full JPEG/PNG corpus scans are still in progress and are not counted as completed here.

The scanner hashes regular files without following symlinks, ranks the full backup before selecting 30 files, and reads image metadata without encoding or modifying a source image. Compression experiments remain private and are a separate evidence artifact; no compressed binaries, source media or licensed theme files are committed.
