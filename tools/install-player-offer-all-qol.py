"""Build and install the FM27 offer-to-all-clubs UI extension in an isolated runtime."""
import argparse
import copy
import hashlib
import json
import shutil
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


KEY = "IDS_FM27_OFFER_ALL_CLUBS"
BUTTON_TEXT = "Spieler allen Vereinen anbieten"
TRANSLATION = (
    f"{KEY}|Offer Player to All Clubs|Proposer le joueur à tous les clubs|"
    "Spieler allen Vereinen anbieten|Offri il giocatore a tutti i club|"
    "Ofrecer jugador a todos los clubes|Zaoferuj zawodnika wszystkim klubom"
)
SCREEN = "screens/13TransfersOfferToClub.xml"
DARK_SCREEN = "dark/screens/13TransfersOfferToClub.xml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack_refpack(data: bytes) -> bytes:
    if data[:2] != b"\x10\xfb":
        return data
    expected = int.from_bytes(data[2:5], "big")
    out, pos = bytearray(), 5
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
            literal, count = code & 3, ((code & 12) << 6) + d + 5
            distance = ((code & 16) << 12) + (b << 8) + c + 1
        elif code >= 0x80:
            b, c = data[pos:pos + 2]
            pos += 2
            literal, count = b >> 6, (code & 63) + 4
            distance = ((b & 63) << 8) + c + 1
        else:
            b = data[pos]
            pos += 1
            literal, count = code & 3, ((code & 28) >> 2) + 3
            distance = ((code & 96) << 3) + b + 1
        out.extend(data[pos:pos + literal])
        pos += literal
        for _ in range(count):
            if distance > len(out):
                raise ValueError("Invalid RefPack backreference")
            out.append(out[-distance])
        if stop:
            break
    if len(out) != expected or pos != len(data):
        raise ValueError("RefPack size mismatch")
    return bytes(out)


def read_big_entries(archive: Path, wanted: set[str]) -> dict[str, bytes]:
    result = {}
    with archive.open("rb") as stream:
        header = stream.read(16)
        if header[:4] not in (b"BIGF", b"BIG4"):
            raise ValueError("Unsupported BIG archive")
        count, index_end = struct.unpack(">II", header[8:])
        index = stream.read(index_end - 16)
        pos = 0
        entries = []
        for _ in range(count):
            offset, size = struct.unpack_from(">II", index, pos)
            pos += 8
            zero = index.index(0, pos)
            name = index[pos:zero].decode("ascii").replace("\\", "/").lower()
            pos = zero + 1
            if name in wanted:
                entries.append((name, offset, size))
        for name, offset, size in entries:
            stream.seek(offset)
            result[name] = unpack_refpack(stream.read(size))
    if set(result) != wanted:
        raise ValueError(f"Missing screen entries: {sorted(wanted - set(result))}")
    return result


def transform_screen(payload: bytes) -> bytes:
    root = ET.fromstring(payload.decode("utf-8-sig"))
    parent = root.find(".//Trfm")
    if parent is None:
        raise ValueError("Screen transform container missing")
    accept = next((node for node in parent if node.get("Uid") == "BtAccept"), None)
    details = next((node for node in parent if node.get("Uid") == "BtPlayerDetails"), None)
    if accept is None or details is None:
        raise ValueError("Required controls missing")
    replacement = copy.deepcopy(accept)
    replacement.set("Uid", "BtPlayerDetails")
    replacement.attrib.pop("Visible", None)
    replacement.find("Appearance").set("Rect", "703,795,503,32")
    replacement.find("ColText").set("String", BUTTON_TEXT)
    parent.remove(details)
    parent.insert(list(parent).index(accept) + 1, replacement)
    ET.indent(root, space="\t")
    return ET.tostring(root, encoding="utf-8") + b"\n"


def validate_screen(payload: bytes, dark: bool) -> None:
    root = ET.fromstring(payload)
    nodes = [node for node in root.iter("Obj") if node.get("Uid") == "BtPlayerDetails"]
    if len(nodes) != 1:
        raise ValueError("Offer-all control must be unique")
    node = nodes[0]
    if node.get("Visible") == "false" or node.find("Appearance").get("Rect") != "703,795,503,32":
        raise ValueError("Offer-all control visibility or placement invalid")
    if node.find("ColText").get("String") != BUTTON_TEXT:
        raise ValueError("Offer-all label invalid")
    resources = [element.get("Resrc", "") for element in node.iter()]
    expected_prefix = "dark\\" if dark else "art\\"
    if not any(value.startswith(expected_prefix) for value in resources):
        raise ValueError("Offer-all theme resources invalid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument(
        "--plugin", type=Path,
        default=Path("data/qol/player-offer-all/plugins/FM27.PlayerOfferAll.asi")
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    runtime, report = args.runtime.resolve(), args.report.resolve()
    plugin = (root / args.plugin).resolve() if not args.plugin.is_absolute() else args.plugin.resolve()
    if runtime.parent != (root / "runtime").resolve():
        raise ValueError("Only direct project runtime children are permitted")
    if not report.is_relative_to((root / "reports/local").resolve()):
        raise ValueError("Report must stay in reports/local")
    if not plugin.is_relative_to(root) or not plugin.is_file():
        raise ValueError("Built project plugin missing")

    wanted = {SCREEN.lower(), DARK_SCREEN.lower()}
    entries = read_big_entries(runtime / "data/screens.big", wanted)
    package = root / "data/qol/player-offer-all"
    generated = {}
    for name in (SCREEN, DARK_SCREEN):
        payload = transform_screen(entries[name.lower()])
        validate_screen(payload, name.startswith("dark/"))
        target = package / Path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        generated[name] = target

    translations = runtime / "fmdata/Translations.csv"
    existing_lines = translations.read_text(encoding="utf-8-sig").splitlines()
    matching = [line for line in existing_lines if line.startswith(KEY + "|")]
    if matching and matching != [TRANSLATION]:
        raise ValueError("Conflicting existing translation key")

    installed = []
    if args.apply:
        legacy_map = runtime / "plugins/FM27.PlayerOfferAll.clubs.csv"
        if legacy_map.exists():
            legacy_map.unlink()
        for name, source in generated.items():
            destination = runtime / Path(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            installed.append(destination)
        plugin_target = runtime / "plugins/FM27.PlayerOfferAll.asi"
        shutil.copy2(plugin, plugin_target)
        installed.append(plugin_target)
        if matching:
            raw_lines = translations.read_bytes().splitlines(keepends=True)
            translations.write_bytes(b"".join(
                line for line in raw_lines
                if not line.decode("utf-8-sig").startswith(KEY + "|")
            ))

    result = {
        "status": "APPLIED_RESTART_REQUIRED" if args.apply else "PREFLIGHT_PASS",
        "runtime": str(runtime),
        "manager_sha256_expected": "8ebe1291fbcc1291bfee182995a165194156a0b4b8e0d6c80994cadb087a857c",
        "manager_sha256_actual": sha256(runtime / "Manager.exe"),
        "archive_sha256": sha256(runtime / "data/screens.big"),
        "plugin_sha256": sha256(plugin),
        "generated": {name: sha256(path) for name, path in generated.items()},
        "installed": {str(path.relative_to(runtime)): sha256(path) for path in installed},
        "button_text": BUTTON_TEXT,
        "rollback": "Delete the two loose screen XML files and plugins/FM27.PlayerOfferAll.asi.",
    }
    if result["manager_sha256_actual"] != result["manager_sha256_expected"]:
        raise ValueError("Unsupported Manager.exe build")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "report": str(report)}))


if __name__ == "__main__":
    main()
