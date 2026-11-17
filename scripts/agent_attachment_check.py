#!/usr/bin/env python3
"""Exercise the local attachment pipeline against generated documents and images."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import attachments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(mode=0o700)
    data = root / "private"
    data.mkdir(mode=0o700)
    fixtures = root / "fixtures"
    fixtures.mkdir()
    expected = {}
    for extension in ("txt", "md", "csv"):
        file = fixtures / ("sample." + extension)
        file.write_text("marker,value\nALPHA LOCAL,42\n", encoding="utf-8")
        expected[file] = "ALPHA LOCAL"
    members = {
        "docx": ("word/document.xml", "<document><p><t>ALPHA LOCAL</t></p></document>"),
        "pptx": ("ppt/slides/slide1.xml", "<slide><t>ALPHA LOCAL</t></slide>"),
        "xlsx": ("xl/worksheets/sheet1.xml", '<worksheet><row><c r="A1" t="inlineStr"><is><t>ALPHA LOCAL</t></is></c></row></worksheet>'),
    }
    for extension, (member, content) in members.items():
        file = fixtures / ("sample." + extension)
        with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member, content)
        expected[file] = "ALPHA LOCAL"
    import pymupdf
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((80, 80), "ALPHA LOCAL")
        file = fixtures / "sample.pdf"
        doc.save(file)
        expected[file] = "[Page 1]"
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (680, 140), color="white")
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 48)
    ImageDraw.Draw(image).text((38, 36), "ALPHA LOCAL", font=font, fill="black")
    for extension in ("png", "jpeg", "webp"):
        file = fixtures / ("sample." + extension)
        image.save(file)
        expected[file] = "ALPHA LOCAL"

    def selection(path):
        info = path.stat()
        return {"project_id": "disposable", "path": str(path), "device": info.st_dev, "inode": info.st_ino}

    checks = []
    for file, marker in expected.items():
        name, mechanism, excerpt = attachments.import_selected(selection(file), data)
        assert name == file.name and marker in excerpt
        checks.append({"file": name, "mechanism": mechanism, "passed": True})
    malformed = fixtures / "bad.docx"
    with zipfile.ZipFile(malformed, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "<!DOCTYPE x [<!ENTITY ex 'invalid'>]><x>&ex;</x>")
    inputs = [selection(malformed), {**selection(file), "inode": 1}]
    for test, payload in zip(("untrusted XML entity", "changed file selection"), inputs):
        try:
            attachments.import_selected(payload, data)
        except ValueError:
            checks.append({"negative_case": test, "passed": True})
        else:
            raise AssertionError("Unsafe attachment unexpectedly accepted")
    (root / "evidence.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
