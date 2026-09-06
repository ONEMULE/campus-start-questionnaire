#!/usr/bin/env python3
"""Verify release files against MANIFEST.sha256; ignores runtime files not in the manifest."""
import hashlib,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=root/'MANIFEST.sha256'
if not manifest.is_file():raise SystemExit('MANIFEST.sha256 not found')
errors=[];count=0
for line in manifest.read_text('utf-8').splitlines():
 if not line.strip():continue
 expected,relative=line.split('  ',1)
 path=root/relative
 if '..' in Path(relative).parts or Path(relative).is_absolute():errors.append('Unsafe path: '+relative);continue
 if not path.is_file():errors.append('Missing: '+relative);continue
 if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:errors.append('Changed: '+relative)
 count+=1
if errors:
 print('\n'.join(errors));raise SystemExit(1)
print(f'Verified {count} release files. This proves local file consistency, not publisher identity or deployment security.')