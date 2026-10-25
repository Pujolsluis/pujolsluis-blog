#!/usr/bin/env python3
"""Apply deterministic, lossless image optimizations to manifest-selected assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GPS_TAG = 0x8825
TIFF_TYPE_WIDTH = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("invalid PNG signature")
    chunks: list[tuple[bytes, bytes]] = []
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + size
        if end > len(data):
            raise ValueError(f"truncated PNG {kind!r} chunk")
        payload = data[offset + 8 : offset + 8 + size]
        expected_crc = struct.unpack(">I", data[offset + 8 + size : end])[0]
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError(f"bad CRC in PNG {kind.decode('ascii', errors='replace')} chunk")
        chunks.append((kind, payload))
        offset = end
        if kind == b"IEND":
            if offset != len(data):
                raise ValueError("data found after PNG IEND")
            return chunks
    raise ValueError("PNG has no IEND chunk")


def png_scan_stream_hash(data: bytes) -> str:
    chunks = png_chunks(data)
    ihdr = next(payload for kind, payload in chunks if kind == b"IHDR")
    raster = zlib.decompress(b"".join(payload for kind, payload in chunks if kind == b"IDAT"))
    visual_metadata = b"".join(kind + payload for kind, payload in chunks if kind in {b"PLTE", b"tRNS", b"iCCP", b"sRGB", b"gAMA", b"cHRM"})
    return hashlib.sha256(ihdr + visual_metadata + raster).hexdigest()


def strip_tiff_gps(tiff: bytearray) -> bool:
    """Erase the EXIF GPS IFD and all its values while preserving other TIFF tags."""
    if len(tiff) < 8 or tiff[:2] not in (b"II", b"MM"):
        return False
    endian = "little" if tiff[:2] == b"II" else "big"
    if int.from_bytes(tiff[2:4], endian) != 42:
        return False
    first_ifd = int.from_bytes(tiff[4:8], endian)
    if first_ifd + 2 > len(tiff):
        return False
    count = int.from_bytes(tiff[first_ifd:first_ifd + 2], endian)
    for index in range(count):
        entry = first_ifd + 2 + index * 12
        if entry + 12 > len(tiff):
            return False
        tag = int.from_bytes(tiff[entry:entry + 2], endian)
        if tag != GPS_TAG:
            continue
        gps_offset = int.from_bytes(tiff[entry + 8:entry + 12], endian)
        if gps_offset + 2 > len(tiff):
            return False
        gps_count = int.from_bytes(tiff[gps_offset:gps_offset + 2], endian)
        if gps_offset + 2 + gps_count * 12 + 4 > len(tiff):
            return False
        # Clear every GPS value stored out-of-line before erasing the directory.
        for gps_index in range(gps_count):
            gps_entry = gps_offset + 2 + gps_index * 12
            data_type = int.from_bytes(tiff[gps_entry + 2:gps_entry + 4], endian)
            value_count = int.from_bytes(tiff[gps_entry + 4:gps_entry + 8], endian)
            value_bytes = TIFF_TYPE_WIDTH.get(data_type, 0) * value_count
            value_offset = int.from_bytes(tiff[gps_entry + 8:gps_entry + 12], endian)
            if value_bytes > 4 and value_offset + value_bytes <= len(tiff):
                tiff[value_offset:value_offset + value_bytes] = b"\x00" * value_bytes
        directory_end = gps_offset + 2 + gps_count * 12 + 4
        tiff[gps_offset:directory_end] = b"\x00" * (directory_end - gps_offset)
        tiff[entry + 8:entry + 12] = b"\x00" * 4
        return True
    return False


def strip_jpeg_gps(path: Path) -> bool:
    """Remove standard GPS IFD values from JPEG EXIF without discarding other metadata."""
    data = bytearray(path.read_bytes())
    if not data.startswith(b"\xff\xd8"):
        raise ValueError(f"invalid JPEG signature: {path}")
    offset = 2
    changed = False
    while offset < len(data):
        if data[offset] != 0xFF:
            break
        marker_start = offset
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD9, 0xDA}:
            break
        if marker in {0x01, *range(0xD0, 0xD8)}:
            continue
        if offset + 2 > len(data):
            break
        segment_length = int.from_bytes(data[offset:offset + 2], "big")
        segment_start = offset + 2
        segment_end = offset + segment_length
        if segment_length < 2 or segment_end > len(data):
            raise ValueError(f"invalid JPEG segment length: {path}")
        payload = data[segment_start:segment_end]
        if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            tiff = bytearray(payload[6:])
            if strip_tiff_gps(tiff):
                data[segment_start + 6:segment_end] = tiff
                changed = True
        offset = segment_end
    if changed:
        path.write_bytes(data)
    return changed


def jpeg_contains_gps(path: Path) -> bool:
    """Read-only test for a standard GPS IFD in a JPEG EXIF segment."""
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8"):
        raise ValueError(f"invalid JPEG signature: {path}")
    offset = 2
    while offset < len(data) and data[offset] == 0xFF:
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD9, 0xDA}:
            break
        if marker in {0x01, *range(0xD0, 0xD8)}:
            continue
        if offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset:offset + 2], "big")
        start, end = offset + 2, offset + length
        if length < 2 or end > len(data):
            raise ValueError(f"invalid JPEG segment length: {path}")
        payload = data[start:end]
        if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            if strip_tiff_gps(bytearray(payload[6:])):
                return True
        offset = end
    return False


def png_lossless_optimize(source: Path, destination: Path) -> dict[str, str]:
    original = source.read_bytes()
    chunks = png_chunks(original)
    idat = b"".join(payload for kind, payload in chunks if kind == b"IDAT")
    decoded = zlib.decompress(idat)
    compressed = zlib.compress(decoded, level=9)
    # Preserve every ancillary chunk and keep the original IDAT stream if the
    # recompressed stream does not reduce bytes.
    if len(compressed) >= len(idat):
        destination.write_bytes(original)
        return {"pixel_stream_sha256": hashlib.sha256(decoded).hexdigest(), "method": "original-png-kept"}

    output = bytearray(PNG_SIGNATURE)
    inserted = False
    for kind, payload in chunks:
        if kind == b"IDAT":
            if not inserted:
                payload = compressed
                inserted = True
            else:
                continue
        output.extend(struct.pack(">I", len(payload)))
        output.extend(kind)
        output.extend(payload)
        output.extend(struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))
    destination.write_bytes(output)
    optimized = png_chunks(bytes(output))
    optimized_pixels = zlib.decompress(b"".join(data for kind, data in optimized if kind == b"IDAT"))
    if optimized_pixels != decoded:
        raise ValueError(f"PNG pixel stream changed for {source}")
    return {"pixel_stream_sha256": hashlib.sha256(decoded).hexdigest(), "method": "png-zlib-level-9"}


def optimize(source: Path, destination: Path, jpegtran: str) -> dict[str, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    ext = source.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        subprocess.run(
            [jpegtran, "-copy", "all", "-optimize", "-outfile", str(destination), str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
        gps_removed = strip_jpeg_gps(destination)
        if destination.stat().st_size >= source.stat().st_size:
            shutil.copyfile(source, destination)
            gps_removed = strip_jpeg_gps(destination)
            return {"method": "source-copy-optimizer-not-smaller", "pixel_equivalence": "source pixels unchanged", "gps_metadata_removed": gps_removed}
        with tempfile.TemporaryDirectory(prefix="media-pixels-") as temporary:
            source_png = Path(temporary) / "source.png"
            output_png = Path(temporary) / "output.png"
            subprocess.run(["sips", "-s", "format", "png", str(source), "--out", str(source_png)], check=True, capture_output=True, text=True)
            subprocess.run(["sips", "-s", "format", "png", str(destination), "--out", str(output_png)], check=True, capture_output=True, text=True)
            source_pixels = png_scan_stream_hash(source_png.read_bytes())
            output_pixels = png_scan_stream_hash(output_png.read_bytes())
            if source_pixels != output_pixels:
                shutil.copyfile(source, destination)
                gps_removed = strip_jpeg_gps(destination)
                return {
                    "method": "source-copy-jpeg-pixel-check-mismatch",
                    "pixel_equivalence": "source pixels unchanged; transformed JPEG rejected",
                    "gps_metadata_removed": gps_removed,
                }
        return {"method": "jpegtran-lossless-huffman-copy-all", "pixel_equivalence": "decoded PNG pixel stream matched", "gps_metadata_removed": gps_removed}
    if ext == ".png":
        return png_lossless_optimize(source, destination)
    if ext == ".gif":
        shutil.copyfile(source, destination)
        if file_hash(source) != file_hash(destination):
            raise ValueError(f"GIF bytes changed for {source}")
        return {"method": "unchanged-gif-no-safe-optimizer-available", "pixel_equivalence": "byte-identical source copy"}
    raise ValueError(f"unsupported selected image extension: {ext}")


def dimensions(path: Path) -> tuple[int, int]:
    result = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)], check=True, capture_output=True, text=True)
    values = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.strip().split(":", 1)
            if key in {"pixelWidth", "pixelHeight"}:
                values[key] = int(value.strip())
    return values["pixelWidth"], values["pixelHeight"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--backup-uploads", type=Path, required=True)
    parser.add_argument("--static-root", type=Path, required=True, help="repository static/ directory")
    parser.add_argument("--jpegtran", default="jpegtran")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    rows = [a for a in manifest["assets"] if a["disposition"] == "required-content-candidate"]
    if manifest["missing_references"]:
        print(f"WARNING: {len(manifest['missing_references'])} published references have no backup source; output remains incomplete.")
    if not shutil.which(args.jpegtran):
        parser.error(f"jpegtran executable not found: {args.jpegtran}")
    for asset in rows:
        source = args.backup_uploads / asset["source_path"]
        if file_hash(source) != asset["source_sha256"]:
            raise SystemExit(f"source hash changed since inventory: {asset['source_path']}")
        output_paths = []
        existing_outputs = {output["path"]: output for output in asset.get("output_paths", [])}
        metadata_policy_current = not asset["extension"] in {".jpg", ".jpeg"} or asset.get("metadata_policy_version") == "jpeg-gps-v1"
        reusable = None
        result = asset.get("optimization")
        for url_path in asset["referenced_url_paths"]:
            output_relative = Path("wp-content/uploads") / url_path
            destination = args.static_root / output_relative
            public_path = output_relative.as_posix()
            prior = existing_outputs.get(public_path)
            if metadata_policy_current and prior and destination.is_file() and file_hash(destination) == prior.get("sha256") and destination.stat().st_size == prior.get("bytes"):
                if reusable is None:
                    reusable = destination
                output_paths.append(public_path)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if reusable is None:
                result = optimize(source, destination, args.jpegtran)
                reusable = destination
            else:
                shutil.copyfile(reusable, destination)
            output_paths.append(public_path)
        if result is None or not output_paths:
            result = asset.get("optimization", {"method": "reused-verified-prior-output", "pixel_equivalence": "prior output hash/size verified"})
        source_size = source.stat().st_size
        output_size = sum((args.static_root / path).stat().st_size for path in output_paths)
        source_dimensions = dimensions(source)
        for output_path in output_paths:
            output_dimensions = dimensions(args.static_root / output_path)
            if source_dimensions != output_dimensions:
                raise SystemExit(f"dimensions changed for {asset['source_path']}: {source_dimensions} -> {output_dimensions}")
        if output_size > source_size * len(output_paths):
            raise SystemExit(f"optimizer increased file size: {asset['source_path']} ({source_size} -> {output_size})")
        asset.update(
            {
                "output_paths": [
                    {"path": path, "sha256": file_hash(args.static_root / path), "bytes": (args.static_root / path).stat().st_size}
                    for path in output_paths
                ],
                "output_bytes": output_size,
                "dimensions": {"width": source_dimensions[0], "height": source_dimensions[1]},
                "role_byte_budget_bytes": 1_000_000,
                "byte_budget_status": "within-1MB-target" if all(path["bytes"] <= 1_000_000 for path in asset_output_info(args.static_root, output_paths)) else "above-1MB-needs-display-sized-review",
                "optimization": result,
                "metadata_policy_version": "jpeg-gps-v1" if asset["extension"] in {".jpg", ".jpeg"} else "keep-format-metadata-v1",
                "pixel_equivalence": "verified pixel-identical for JPEG/PNG; GIF copied byte-for-byte",
                "visual_review": "not reviewed per asset: rendered HTML is available, but no rendered-pixel captures or measured display viewports are supplied; original dimensions and lossless-only settings were retained",
            }
        )
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    total_in = sum(row["source_bytes"] * len(row["output_paths"]) for row in rows)
    total_out = sum(row["output_bytes"] for row in rows)
    manifest["optimization_toolchain"] = {
        "jpegtran": subprocess.run([args.jpegtran, "-version"], check=True, capture_output=True, text=True).stdout.strip(),
        "sips": subprocess.run(["sips", "--version"], check=True, capture_output=True, text=True).stdout.strip(),
        "strategy": "lossless-only; no resizing, lossy re-encoding, or alternate formats without measured display sizes and visual review",
        "jpeg_metadata": "Remove standard EXIF GPS IFD values while preserving all other JPEG metadata, including embedded copyright/licensing fields; confirm pixel equivalence after metadata edit.",
    }
    jpeg_assets = [asset for asset in rows if asset["extension"] in {".jpg", ".jpeg"}]
    remaining_gps = [asset["source_path"] for asset in jpeg_assets for output in asset["output_paths"][:1] if jpeg_contains_gps(args.static_root / output["path"])]
    if remaining_gps:
        raise SystemExit(f"GPS metadata remains in optimized JPEG outputs: {remaining_gps[:10]}")
    manifest["metadata_audit"] = {
        "jpeg_source_files_checked": len(jpeg_assets),
        "jpeg_files_with_gps_removed": sum(bool(asset.get("optimization", {}).get("gps_metadata_removed")) for asset in jpeg_assets),
        "jpeg_outputs_with_gps_remaining": len(remaining_gps),
        "policy": "standard EXIF GPS IFD removed; other metadata retained",
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"images": len(rows), "source_bytes": total_in, "output_bytes": total_out, "saved_bytes": total_in - total_out}, sort_keys=True))
    return 0


def asset_output_info(static_root: Path, paths: list[str]) -> list[dict[str, int]]:
    return [{"bytes": (static_root / path).stat().st_size} for path in paths]


if __name__ == "__main__":
    raise SystemExit(main())
