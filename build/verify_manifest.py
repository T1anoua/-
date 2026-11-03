"""Verify the shipped SHA-256 list; extra runtime files are deliberately ignored."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'manifest.sha256.json').read_text(encoding='utf-8'))
failures = []
for relative, expected in manifest.items():
    path = (root / relative).resolve()
    if root not in path.parents:
        failures.append(relative + ': invalid path')
    elif not path.is_file():
        failures.append(relative + ': missing')
    elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        failures.append(relative + ': changed')
if failures:
    print('\n'.join(failures))
    sys.exit(1)
print('PASS: {} release files match their SHA-256 values.'.format(len(manifest)))
