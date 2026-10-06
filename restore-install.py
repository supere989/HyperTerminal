#!/usr/bin/env python3
"""Restore files from a HyperTerminal installer backup."""
import json
from pathlib import Path
import shutil
import sys
backup = Path(sys.argv[1]).resolve()
home = Path.home().resolve()
for entry in json.loads((backup/'manifest.json').read_text()):
    rel = Path(entry['path'])
    if rel.is_absolute() or '..' in rel.parts:
        raise SystemExit('Invalid backup path')
    target = home/rel
    if entry['existed']:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup/rel, target)
    elif target.exists():
        target.unlink()
print('HyperTerminal file installation restored. Reload systemd and desktop session.')
