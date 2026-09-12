"""Bounded PE inspection. No executable writes or inferred patch support."""
import struct
from pathlib import Path


def inspect_bytes(data: bytes) -> dict:
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("Not an MZ executable")
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if offset < 64 or offset + 24 > len(data) or data[offset:offset + 4] != b"PE\0\0":
        raise ValueError("Invalid PE header")
    machine, sections, stamp, _, _, size, flags = struct.unpack_from("<HHIIIHH", data, offset + 4)
    optional = offset + 24
    if size < 96 or optional + size + sections * 40 > len(data):
        raise ValueError("Truncated optional header or section table")
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic not in (0x10B, 0x20B) or not 1 <= sections <= 96:
        raise ValueError("Unsupported PE optional header/section count")
    if (magic == 0x10B and machine != 0x14C) or (magic == 0x20B and machine != 0x8664):
        raise ValueError("Unsupported/mismatched machine architecture")
    if magic == 0x20B and size < 112:
        raise ValueError("Truncated PE32+ optional header")
    image_size = struct.unpack_from("<I", data, optional + 56)[0]
    entry = struct.unpack_from("<I", data, optional + 16)[0]
    if not image_size or entry >= image_size:
        raise ValueError("Entry point outside image")
    for n in range(sections):
        start = optional + size + 40 * n
        raw_size, raw_start = struct.unpack_from("<II", data, start + 16)
        if raw_size and raw_start + raw_size > len(data):
            raise ValueError("Section exceeds file bounds")
    base_offset, base_format = (28, "<I") if magic == 0x10B else (24, "<Q")
    return {
        "architecture": "x86" if magic == 0x10B else "x64",
        "machine": hex(machine), "sections": sections, "timestamp_raw": stamp,
        "image_base": hex(struct.unpack_from(base_format, data, optional + base_offset)[0]),
        "entry_point_rva": hex(entry), "image_size": image_size,
        "large_address_aware": bool(flags & 0x20),
        "binary_patch_support": "UNVERIFIED_NO_WRITES_ALLOWED",
    }


def inspect(path: Path) -> dict:
    return inspect_bytes(path.read_bytes())
