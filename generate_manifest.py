#!/usr/bin/env python3
"""
Run this script from the soups-network directory to auto-generate manifest.json
from all GraphML files in the data/ folder.

Usage: python3 generate_manifest.py
"""
import os, json

data_dir = 'data'
files = sorted([
    f for f in os.listdir(data_dir)
    if f.endswith('.graphml') and any(c.isdigit() for c in f)
])

with open(os.path.join(data_dir, 'manifest.json'), 'w') as fp:
    json.dump(files, fp, indent=2)

print(f"manifest.json updated with {len(files)} files:")
for f in files:
    print(f"  {f}")
