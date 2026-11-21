#!/usr/bin/env python3
"""Build a disposable synthetic UI target; never reads personal application data."""
from pathlib import Path
import json
import plistlib
import subprocess
ROOT = Path(__file__).resolve().parents[1]


def build(output=None):
    root = ROOT / "desktop/automation"
    app = output or root / ".build/Personal Codex Automation Fixture.app"
    binary = app / "Contents/MacOS/automation-fixture"
    binary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/xcrun", "swiftc", "-swift-version", "5", "-parse-as-library", "-O",
                "-module-cache-path", str(root / ".build/module-cache"), str(root / "Fixtures/Fixture.swift"), "-o", str(binary)], check=True)
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "local.personalcodex.automation.fixture",
    "CFBundleName": "Personal Codex Automation Fixture", "CFBundleExecutable": binary.name,
    "CFBundlePackageType": "APPL", "CFBundleVersion": "1", "LSMinimumSystemVersion": "14.0"}))
    subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(app)], check=True, capture_output=True)
    return {"application": str(app), "binary": str(binary), "data": "synthetic only", "launched": False}


if __name__ == "__main__":
    print(json.dumps(build()))
