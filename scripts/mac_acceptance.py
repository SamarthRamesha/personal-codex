#!/usr/bin/env python3
"""Turn the native Mac self-check into one command with an unambiguous exit status.

The helper prints a single JSON report of synthetic checks. Reading that JSON by eye is how a
failure gets mistaken for a pass, so this summarises it into named PASS/FAIL lines and exits
non-zero unless every listed check actually passed.

It never grants permissions, changes TCC, signs anything, or touches the installed
permission-approved preview: it only reads a saved report or runs the candidate helper in
`desktop/automation/.build/`.

Usage:
    python3 scripts/mac_acceptance.py --run             # build the candidate first, then run it
    python3 scripts/mac_acceptance.py --run --capture    # also the capture/OCR checks
    python3 scripts/mac_acceptance.py --report report.json --save kept.json

Exit status: 0 verified, 1 not verified, 2 permission required, 3 stopped early, 4 the helper could
not be run at all (missing, timed out, or no readable report).
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "desktop/automation/.build/Personal Codex Automation.app/Contents/MacOS/personal-codex-automation"

VERIFIED = "verified"
NOT_VERIFIED = "not_verified"
PERMISSION = "permission_required"
STOPPED = "stopped"
UNREADABLE = "unreadable"
COULD_NOT_RUN = "could_not_run"
EXIT = {VERIFIED: 0, NOT_VERIFIED: 1, PERMISSION: 2, STOPPED: 3, UNREADABLE: 1, COULD_NOT_RUN: 4}


def summarize(report):
    """Map a helper report to a verdict. Only known fields are used and echoed."""
    if not isinstance(report, dict):
        return {"verdict": UNREADABLE, "total": 0, "passed": 0, "failures": [],
                "headline": "No readable native report was provided, so nothing is verified."}
    status = report.get("status") if isinstance(report.get("status"), str) else "unknown"
    checks = report.get("checks") if isinstance(report.get("checks"), list) else []
    named = [c for c in checks if isinstance(c, dict) and isinstance(c.get("name"), str)]
    failures = [{"name": c["name"], **({"detail": c["detail"]} if isinstance(c.get("detail"), str) else {})}
                for c in named if c.get("passed") is not True]
    total = len(named)
    base = {"status": status, "total": total, "passed": total - len(failures), "failures": failures}
    if status == COULD_NOT_RUN:
        reason = report.get("reason") if isinstance(report.get("reason"), str) else "The native helper could not be run."
        return {**base, "verdict": COULD_NOT_RUN, "headline": reason}
    if status == PERMISSION:
        return {**base, "verdict": PERMISSION,
                "headline": "Accessibility has not been granted to the helper, so no check ran. "
                            "Grant it yourself in System Settings, then run this again."}
    # The helper reports a stopped run as "failed" with the stage and error; treat both names alike so
    # a stopped run is never described as a mere failing check list.
    if status in (STOPPED, "failed"):
        stage = report.get("stage") if isinstance(report.get("stage"), str) else "an unnamed stage"
        error = report.get("error") if isinstance(report.get("error"), str) else "no error text"
        return {**base, "verdict": STOPPED, "headline": f"The check stopped at {stage}: {error}"}
    if failures:
        return {**base, "verdict": NOT_VERIFIED,
                "headline": f"{len(failures)} of {total} checks failed: "
                            + ", ".join(failure["name"] for failure in failures)}
    if status != "passed":
        return {**base, "verdict": NOT_VERIFIED,
                "headline": f"The report status is {status!r}, which is not a pass; nothing is verified."}
    if total == 0:
        return {**base, "verdict": NOT_VERIFIED,
                "headline": "The report says passed but lists no checks, so nothing is verified."}
    if report.get("actual_ui_exercised") is not True:
        return {**base, "verdict": NOT_VERIFIED,
                "headline": "The report does not state that a real UI was exercised, so its checks verify nothing."}
    # A passing run must say what it never touched, or the verdict reads as broader than it is.
    not_exercised = []
    if report.get("capture_requested") is not True:
        not_exercised.append("capture/OCR (re-run with --capture once Screen Recording is granted)")
    if report.get("browser_exercised") is not True:
        not_exercised.append("browser workflow (owner-run, runbook stage 7)")
    return {**base, "verdict": VERIFIED, "not_exercised": not_exercised,
            "headline": f"All {total} synthetic native checks passed on this Mac."}


def render(summary):
    lines = []
    for name in summary.get("failures", []):
        detail = f" - {name['detail']}" if "detail" in name else ""
        lines.append(f"FAIL {name['name']}{detail}")
    for entry in summary.pop("_checks", []):
        lines.append(f"PASS {entry}")
    lines.append("")
    lines.append(summary["headline"])
    for entry in summary.get("not_exercised", []):
        lines.append(f"NOT EXERCISED {entry}")
    lines.append("Synthetic fixture checks only; this is not acceptance of any real application.")
    return "\n".join(lines)


def run_helper(helper, capture):
    """Run the candidate helper; every failure to produce a report keeps its own exit status."""
    if not helper.is_file():
        return {"status": COULD_NOT_RUN, "reason": f"Candidate helper not found at {helper}. Run "
                "`python3 scripts/build_mac_automation.py --self-test` first."}
    command = [str(helper), "--ui-self-check"] + (["--capture"] if capture else [])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as error:
        return {"status": COULD_NOT_RUN, "reason": f"The candidate helper could not be run: {error}"}
    if completed.returncode != 0 and not completed.stdout.strip():
        return {"status": COULD_NOT_RUN, "reason": f"The helper exited {completed.returncode} without a report: "
                f"{completed.stderr.strip()[:400]}"}
    line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"status": COULD_NOT_RUN, "reason": f"The helper printed no readable report (exit {completed.returncode}): "
                f"{completed.stdout.strip()[:400] or completed.stderr.strip()[:400]}"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", action="store_true", help="run the candidate helper's UI self-check")
    source.add_argument("--report", type=Path, help="summarise a previously saved JSON report")
    parser.add_argument("--capture", action="store_true", help="also run the capture/OCR checks")
    parser.add_argument("--helper", type=Path, default=HELPER, help="candidate helper binary")
    parser.add_argument("--save", type=Path, help="keep the raw report for the handoff")
    args = parser.parse_args(argv)

    if args.report:
        try:
            report = json.loads(args.report.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"Cannot read {args.report}: {error}")
    else:
        report = run_helper(args.helper, args.capture)
    summary = summarize(report)
    # Never leave a saved report behind for a run that produced none, so a later --report cannot
    # turn a helper that never ran into evidence.
    if args.save and summary["verdict"] != COULD_NOT_RUN:
        args.save.write_text(json.dumps(report, indent=2, sort_keys=True))
    summary["_checks"] = [entry["name"] for entry in (report.get("checks") or [])
                          if isinstance(entry, dict) and entry.get("passed") is True
                          and isinstance(entry.get("name"), str)]
    print(render(summary))
    return EXIT[summary["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
