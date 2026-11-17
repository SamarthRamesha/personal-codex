"""Local, bounded text extraction for a single authorized document snapshot."""
from __future__ import annotations

import csv
from itertools import islice
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET
import zipfile

MAX_TEXT = 12_000
XML_LIMIT = 2_000_000
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
SUFFIXES = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md", ".markdown", *IMAGE_SUFFIXES}


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def nodes(parent, name):
    return (node for node in parent.iter() if local_name(node.tag) == name)


def xml(archive, path):
    info = archive.getinfo(path)
    if info.file_size > XML_LIMIT:
        raise ValueError("Office XML member exceeds the extraction limit")
    data = archive.read(info)
    if re.search(br"<\s*!\s*(?:doctype|entity)", data, re.I) or b"\x00" in data:
        raise ValueError("Unsupported XML declaration or encoding")
    return ET.fromstring(data)


def office(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) > 2000 or len(names) != len(set(names)):
            raise ValueError("Office archive has too many or duplicate entries")
        if path.suffix == ".docx":
            doc = xml(archive, "word/document.xml")
            paragraphs = ("".join(str(t.text or "") for t in nodes(p, "t")) for p in nodes(doc, "p"))
            return "\n".join(line for line in paragraphs if line)[:MAX_TEXT]
        if path.suffix == ".pptx":
            slides = sorted((name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                            key=lambda name: int(re.search(r"\d+", name).group()))
            return "\n\n".join(
                f"[{name}]\n" + "\n".join(node.text or "" for node in nodes(xml(archive, name), "t"))
                for name in slides[:12]
            )[:MAX_TEXT]
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(t.text or "" for t in nodes(si, "t")) for si in nodes(xml(archive, "xl/sharedStrings.xml"), "si")]
        rows = []
        sheets = sorted(name for name in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
        for name in sheets[:6]:
            rows.append(f"[{name}]")
            for row in islice(nodes(xml(archive, name), "row"), 30):
                cells = []
                for cell in islice(nodes(row, "c"), 20):
                    value = next(nodes(cell, "v"), None)
                    text = value.text or "" if value is not None else "".join(t.text or "" for t in nodes(cell, "t"))
                    if cell.get("t") == "s" and text:
                        position = int(text)
                        if not 0 <= position < len(shared):
                            raise ValueError("Invalid spreadsheet string reference")
                        text = shared[position]
                    cells.append(f"{cell.get('r', '')}={text[:250]}")
                rows.append(" | ".join(cells))
        return "\n".join(rows)[:MAX_TEXT]


def extract(path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pymupdf
        with pymupdf.open(str(path)) as pdf:
            if pdf.needs_pass:
                raise ValueError("Password-protected PDF requires an unlocked local copy")
            return "\n\n".join(f"[Page {index + 1}]\n{pdf[index].get_text(sort=True)[:MAX_TEXT]}"
                               for index in range(min(len(pdf), 12)))[:MAX_TEXT]
    if suffix in IMAGE_SUFFIXES:
        from PIL import Image
        with Image.open(path) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Image pixel budget exceeded")
        result = subprocess.run(["tesseract", str(path), "stdout", "-l", "eng", "--psm", "6"],
                                capture_output=True, timeout=20, check=True)
        return "[Local OCR]\n" + result.stdout.decode("utf-8", errors="replace")[:MAX_TEXT]
    if suffix in {".docx", ".pptx", ".xlsx"}:
        return office(path)
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as source:
            return "\n".join(" | ".join(item[:300] for item in row[:30])
                             for row in islice(csv.reader(source), 35))[:MAX_TEXT]
    if suffix in {".txt", ".md", ".markdown"}:
        with path.open(encoding="utf-8-sig") as source:
            return source.read(MAX_TEXT)
    raise ValueError("Unsupported attachment format")


if __name__ == "__main__":
    try:
        print(extract(Path(sys.argv[1])))
    except (OSError, ValueError, RuntimeError, ET.ParseError, zipfile.BadZipFile, KeyError, subprocess.SubprocessError):
        sys.exit("Local extraction failed. Check the file format, readability and available extractors.")
