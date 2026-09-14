"""Install the global player-knowledge level 10 patch in an isolated FM27 runtime."""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path


EXPECTED_MANAGER_SHA256 = "8ebe1291fbcc1291bfee182995a165194156a0b4b8e0d6c80994cadb087a857c"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument(
        "--plugin", type=Path,
        default=Path("data/qol/full-player-knowledge/plugins/FM27.FullPlayerKnowledge.asi"),
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    runtime = args.runtime.resolve()
    report = args.report.resolve()
    plugin = (root / args.plugin).resolve() if not args.plugin.is_absolute() else args.plugin.resolve()
    if runtime.parent != (root / "runtime").resolve():
        raise ValueError("Only direct project runtime children are permitted")
    if not report.is_relative_to((root / "reports/local").resolve()):
        raise ValueError("Report must stay in reports/local")
    if not plugin.is_relative_to(root) or not plugin.is_file():
        raise ValueError("Built project plugin missing")

    manager = runtime / "Manager.exe"
    manager_hash = sha256(manager)
    if manager_hash != EXPECTED_MANAGER_SHA256:
        raise ValueError("Unsupported Manager.exe build")
    payload = plugin.read_bytes()
    pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
    if struct.unpack_from("<H", payload, pe_offset + 4)[0] != 0x14C:
        raise ValueError("FM27 player-knowledge plugin must be x86")

    installed = None
    if args.apply:
        installed = runtime / "plugins/FM27.FullPlayerKnowledge.asi"
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(plugin, installed)
        if sha256(installed) != sha256(plugin):
            raise RuntimeError("Installed plugin hash mismatch")

    result = {
        "status": "APPLIED_RESTART_REQUIRED" if args.apply else "PREFLIGHT_PASS",
        "runtime": str(runtime),
        "manager_sha256": manager_hash,
        "plugin_sha256": sha256(plugin),
        "installed": str(installed.relative_to(runtime)) if installed else None,
        "knowledge_level": 10,
        "getter_rva": "0xAB9BA0",
        "scope": "central player-knowledge getter used by all player-information views",
        "rollback": "Delete plugins/FM27.FullPlayerKnowledge.asi and restart the game.",
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "report": str(report)}))


if __name__ == "__main__":
    main()
