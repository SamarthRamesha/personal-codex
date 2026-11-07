#!/usr/bin/env python3
"""Restore a verified Personal Codex snapshot to a NEW path; refuses overwrite."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.maintenance import restore_new
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('snapshot',type=Path)
parser.add_argument('new_database',type=Path)
if __name__=='__main__':
    args=parser.parse_args()
    print(json.dumps(restore_new(args.snapshot,args.new_database)))
