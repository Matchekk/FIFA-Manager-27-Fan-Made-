"""Package only our source/toolkit, never installed game assets or upstream code."""
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fm27.common import sha256

root = Path(__file__).resolve().parents[1]
target = root / "dist" / "FM27CommunityToolkit-0.1.0.zip"
files = [root / "README.md", root / "HANDOFF.md", root / "requirements-data.txt", root / "reports/VALIDATION_SUMMARY.md"]
for folder in ("src/fm27", "src/native", "tools", "config", "docs", "tests"):
    files.extend(p for p in (root / folder).rglob("*") if p.is_file()
                 and p.suffix in {".py", ".ps1", ".md", ".json", ".cpp", ".h"} and "__pycache__" not in p.parts
                 and p.name != "package-toolkit.py")
files = sorted(set(files))
manifest = {"kind": "SOURCE_DIAGNOSTIC_TOOLKIT_NOT_GAME_PATCH", "version": "0.1.0",
            "files": [{"path": p.relative_to(root).as_posix(), "sha256": sha256(p)} for p in files]}
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for file in files:
        archive.write(file, file.relative_to(root).as_posix())
    archive.writestr("package-manifest.json", json.dumps(manifest, indent=2))
print(json.dumps({"package": str(target), "sha256": sha256(target), "files": len(files)}))
