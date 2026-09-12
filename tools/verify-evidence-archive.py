"""Read back legacy path archives or schema2 content-addressed evidence archives."""
import argparse
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from fm27.common import sha256, write_json

parser = argparse.ArgumentParser()
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
archive = args.archive.resolve()
if args.output.exists():
    raise ValueError('Verification output must be new')
manifest_path = archive / 'EVIDENCE.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
objects = manifest['files_sha256']
if not objects or manifest.get('schema', 1) not in {1, 2}:
    raise ValueError('Empty or unsupported archive')
if manifest.get('schema') == 2:
    if manifest.get('storage') != 'SHA256_OBJECTS':
        raise ValueError('Unsupported schema2 storage')
    sources = manifest['source_files_sha256']
    paths = manifest['source_to_archive_paths']
    if set(sources) != set(paths) or set(paths.values()) != set(objects):
        raise ValueError('Incomplete source-to-object mapping')
    for name, digest in sources.items():
        source = Path(name)
        if source.is_absolute() or '..' in source.parts:
            raise ValueError('Original source path escapes its project')
        if paths[name] != 'objects/' + digest + '.bin' or objects[paths[name]] != digest:
            raise ValueError('Source/object hash binding differs')
else:
    sources = objects
for name, digest in objects.items():
    path = (archive / name).resolve()
    if (not path.is_relative_to(archive) or not re.fullmatch('[0-9a-f]{64}', digest)
            or sha256(path) != digest):
        raise ValueError('Archive object changed: ' + name)
write_json(args.output, dict(status='PASS', schema=manifest.get('schema', 1),
    archive=str(archive), manifest_sha256=sha256(manifest_path),
    original_inputs=len(sources), stored_files=len(objects), all_object_bytes_reread=True,
    source_mapping_complete=True, verifier_sha256=sha256(Path(__file__))))
print(json.dumps(dict(status='PASS',original_inputs=len(sources),stored_files=len(objects))))
