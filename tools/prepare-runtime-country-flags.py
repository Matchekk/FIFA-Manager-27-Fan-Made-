"""Recover existing 32px flags as reversible loose assets in an isolated runtime."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def unpack_refpack(data):
    if data[:2] != b"\x10\xfb":
        raise ValueError("Unsupported RefPack header")
    expected = int.from_bytes(data[2:5], "big")
    out = bytearray()
    pos = 5
    while True:
        code = data[pos]
        pos += 1
        stop = False
        if code >= 0xFC:
            literal, count, distance, stop = code & 3, 0, 0, True
        elif code >= 0xE0:
            literal, count, distance = ((code & 31) << 2) + 4, 0, 0
        elif code >= 0xC0:
            b, c, d = data[pos:pos + 3]
            pos += 3
            literal = code & 3
            count = ((code & 12) << 6) + d + 5
            distance = ((code & 16) << 12) + (b << 8) + c + 1
        elif code >= 0x80:
            b, c = data[pos:pos + 2]
            pos += 2
            literal = b >> 6
            count = (code & 63) + 4
            distance = ((b & 63) << 8) + c + 1
        else:
            b = data[pos]
            pos += 1
            literal = code & 3
            count = ((code & 28) >> 2) + 3
            distance = ((code & 96) << 3) + b + 1
        out.extend(data[pos:pos + literal])
        pos += literal
        if count:
            if distance > len(out):
                raise ValueError("Invalid backreference")
            for _ in range(count):
                out.append(out[-distance])
        if len(out) > expected:
            raise ValueError("RefPack output exceeds header")
        if stop:
            break
    if len(out) != expected or pos != len(data):
        raise ValueError("RefPack size mismatch or trailing bytes")
    return bytes(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    runtime = args.runtime.resolve()
    report = args.report.resolve()
    if runtime.parent != root / "runtime" or not report.is_relative_to(root / "reports/local"):
        raise ValueError("Only project runtime and local report targets are permitted")
    archive = runtime / "art_badges.big"
    prefix = "art/lib/countryflags/32x32/"
    pending = []
    preserved = []
    with archive.open("rb") as stream:
        header = stream.read(16)
        if header[:4] not in (b"BIGF", b"BIG4"):
            raise ValueError("Unsupported BIG header")
        count, end = struct.unpack(">II", header[8:])
        index = stream.read(end - 16)
        pos = 0
        for _ in range(count):
            offset, size = struct.unpack_from(">II", index, pos)
            pos += 8
            zero = index.index(0, pos)
            name = index[pos:zero].decode("ascii").replace("\\", "/")
            pos = zero + 1
            if not name.lower().startswith(prefix):
                continue
            destination = (runtime / name).resolve()
            if not destination.is_relative_to(runtime):
                raise ValueError(f"Refusing to escape: {destination}")
            if destination.exists():
                preserved.append({"path": name, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
                continue
            stream.seek(offset)
            packed = stream.read(size)
            payload = unpack_refpack(packed) if packed[:2] == b"\x10\xfb" else packed
            width, height = struct.unpack_from("<HH", payload, 12)
            depth = payload[16]
            if payload[2] != 2 or width != 32 or height != 32 or depth != 32 or len(payload) != 4114:
                raise ValueError(f"Unexpected flag TGA: {name}, {len(payload)}, {width}x{height}, {depth}")
            pending.append((destination, payload, {
                "path": name, "archive_offset": offset, "packed_bytes": size,
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                "distinct_pixel_values": len(set(struct.iter_unpack("4s", payload[18:])))
            }))
    if len(pending) + len(preserved) != 219:
        raise ValueError(f"Unexpected flag inventory: {len(pending)} + {len(preserved)}")
    if args.apply:
        for destination, payload, _ in pending:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as writer:
                writer.write(payload)
        for destination, payload, _ in pending:
            if destination.read_bytes() != payload:
                raise ValueError(f"Readback mismatch: {destination}")
    result = {
        "status": "APPLIED_RUNTIME_ONLY_VISUAL_RETEST_REQUIRED" if args.apply else "PREFLIGHT_PASS",
        "runtime": str(runtime), "archive": str(archive),
        "rationale": "Archive flags exist but country-selection UI displays white squares; test loose-file loading using unchanged decompressed source assets.",
        "root_cause_confirmed": False, "visual_fix_confirmed": False,
        "rollback": "Remove only newly created paths in this manifest after verifying their SHA256; archive and existing loose overrides are unchanged.",
        "files": [entry for _, _, entry in pending],
        "preserved_existing_files": preserved,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "files": len(pending), "report": str(report)}))


if __name__ == "__main__":
    main()
