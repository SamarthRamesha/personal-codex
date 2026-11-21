#!/usr/bin/env python3
"""Build the reviewed native automation helper from project Swift source; no downloads."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build(output=None):
    if sys.platform != "darwin":
        raise RuntimeError("The Mac automation helper requires macOS")
    root = ROOT / "desktop/automation"
    output = output or root / ".build/Personal Codex Automation.app"
    binary = output / "Contents/MacOS/personal-codex-automation"
    binary.parent.mkdir(parents=True, exist_ok=True)
    cache = root / ".build/module-cache"
    cache.mkdir(parents=True, exist_ok=True)
    files = sorted((root / "Sources").glob("*.swift")) + sorted((root / "Tests").glob("*.swift"))
    subprocess.run(["/usr/bin/xcrun", "swiftc", "-swift-version", "5", "-O", "-parse-as-library",
                    "-target", "arm64-apple-macos14.0" if subprocess.check_output(["/usr/bin/uname", "-m"], text=True).strip() == "arm64" else "x86_64-apple-macos14.0",
                    "-module-cache-path", str(cache), *map(str, files), "-o", str(binary)], check=True)
    (output / "Contents/Info.plist").write_bytes(plistlib.dumps({
        "CFBundleIdentifier": "local.personalcodex.automation", "CFBundleName": "Personal Codex Automation",
        "CFBundleDisplayName": "Personal Codex Automation", "CFBundleExecutable": binary.name,
        "CFBundlePackageType": "APPL", "CFBundleVersion": "1", "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "14.0", "LSUIElement": True,
        "NSScreenCaptureUsageDescription": "Capture only the window you selected, after your separate confirmation, for local preview and OCR.",
    }))
    from build_mac_automation_fixture import build as build_fixture
    build_fixture(output / "Contents/Resources/Fixtures/Personal Codex Automation Fixture.app")
    subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(output)], check=True, capture_output=True)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(output)], check=True, capture_output=True)
    return {"application": str(output), "binary": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
            "signature": "ad-hoc; not notarized", "permissions_granted": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path)
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    receipt = build(args.output)
    if args.self_test:
        subprocess.run([receipt["binary"], "--self-test"], check=True, timeout=15)
    print(json.dumps(receipt, indent=2))
