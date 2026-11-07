#!/usr/bin/env python3
"""Run the scoped, outbound-only Mac inference worker (no persistent service installed)."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.mac_worker import main
if __name__=='__main__':raise SystemExit(main())
