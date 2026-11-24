"""Frontend filenames and imports must survive macOS's case-insensitive filesystem.

The hosted native job checks this repository out on macOS and runs ``tsc -b`` / ``cargo test``. Two
files whose names differ only in case are the same file there: TypeScript reports TS1149/TS1261 and
then misses exports, which is how the native job failed on 24 November (``RoundEvidence.tsx`` vs
``roundEvidence.ts``). These checks run in the Linux backend job, so the problem is caught before a
Mac checkout ever sees it.

The scan is deliberately about *stems*, not exact names: ``TaskReport.tsx`` and ``taskReport.ts``
can both exist in a Git tree, but a case-insensitive directory cannot hold both, and TypeScript
treats them as one module.
"""
import re
import unittest
from collections import defaultdict
from pathlib import Path

DESKTOP = Path(__file__).resolve().parents[1] / "desktop"
SRC = DESKTOP / "src"
SCAN_DIRS = (("src", SRC), ("src-tauri", DESKTOP / "src-tauri"))
SKIPPED_PARTS = {"target", "node_modules", ".git", "gen"}
IMPORT_RE = re.compile(r"""(?:from|import)\s*\(?\s*['"](\.{1,2}/[^'"]+)['"]""")
SUFFIXES = ("", ".ts", ".tsx", ".css", ".json", ".d.ts")


def scanned_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*")
            if path.is_file() and not SKIPPED_PARTS & set(path.relative_to(root).parts)]


class FrontendFilenameCaseTests(unittest.TestCase):
    def test_the_source_directories_are_present_and_were_really_scanned(self):
        # A silently empty scan would make the checks below pass for the wrong reason.
        self.assertTrue((SRC / "App.tsx").is_file())
        self.assertGreaterEqual(len([path for path in scanned_files(SRC) if path.suffix == ".tsx"]), 10)

    def test_no_two_source_files_share_a_stem_case_insensitively(self):
        problems = []
        for label, root in SCAN_DIRS:
            groups = defaultdict(list)
            for path in scanned_files(root):
                groups[path.stem.lower()].append((path.stem, path.relative_to(root).as_posix()))
            for entries in sorted(groups.values()):
                # The same stem with different extensions (icon.png / icon.icns) is fine; two stems that
                # differ only in case are what a case-insensitive checkout and tsc cannot hold apart.
                if len({stem for stem, _ in entries}) > 1:
                    problems.append(f"{label}: {sorted(name for _, name in entries)} differ only in name casing")
        self.assertEqual(problems, [],
                         "on macOS each pair is one file and the native build fails with TS1149/TS1261 "
                         "before it can find their exports:\n" + "\n".join(problems))

    def test_every_relative_import_resolves_to_one_real_file(self):
        problems = []
        for path in sorted(scanned_files(SRC)):
            if path.suffix not in {".ts", ".tsx"}:
                continue
            for specifier in IMPORT_RE.findall(path.read_text(encoding="utf-8")):
                # Vite raw imports carry a query (`?raw`); the file part is what has to exist.
                specifier = specifier.split("?", 1)[0]
                base = Path(str((path.parent / specifier).resolve()))
                candidates = [base] if base.suffix else [Path(str(base) + suffix) for suffix in SUFFIXES]
                if not any(candidate.is_file() for candidate in candidates):
                    problems.append(f"{path.relative_to(SRC).as_posix()} imports {specifier}, which does not resolve")
                    continue
                resolved = next(candidate for candidate in candidates if candidate.is_file())
                if resolved.name not in {entry.name for entry in resolved.parent.iterdir()}:
                    problems.append(f"{path.relative_to(SRC).as_posix()} imports {specifier} "
                                    f"but {resolved.name} is not its exact name")
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
