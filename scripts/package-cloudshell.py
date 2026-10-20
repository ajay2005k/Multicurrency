#!/usr/bin/env python3
"""Assemble tested, prebuilt deployment files. Run package-cloudshell.sh first."""
from pathlib import Path
import hashlib
import json
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
out = root / '.deploy' / 'sentinel-cloudshell'
out.mkdir(parents=True, exist_ok=True)
for source, target in [
    ('deployment/deploy.py', 'deploy.py'),
    ('deployment/README.md', 'README.md'),
    ('infra/hosting.yaml', 'hosting.yaml'),
    ('docs/FACULTY_DEMO.md', 'FACULTY_DEMO.md'),
]:
    shutil.copy2(root / source, out / target)
shutil.copytree(root / 'frontend/dist', out / 'web', dirs_exist_ok=True)
if (out / 'vendor').exists():
    shutil.rmtree(out / 'vendor')
with ZipFile(out / 'backend.zip', 'w', ZIP_DEFLATED) as archive:
    for file in sorted((root / '.build/lambda').rglob('*')):
        if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
            archive.write(file, file.relative_to(root / '.build/lambda').as_posix())
    archive.write(root / 'backend/app.py', 'app.py')
files = [p for p in out.rglob('*') if p.is_file() and p.name != 'manifest.json']
manifest = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
path = root / '.deploy' / 'sentinel-cloudshell.zip'
with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
    for file in sorted(out.rglob('*')):
        if file.is_file() and '__pycache__' not in file.parts:
            archive.write(file, 'sentinel-cloudshell/' + file.relative_to(out).as_posix())
print(f'Built {path} ({path.stat().st_size / 1024**2:.1f} MiB)')
