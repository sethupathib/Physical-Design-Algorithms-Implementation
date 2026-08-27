#!/usr/bin/env python3
"""
Ad-hoc Python equivalent of policy/design_health.yaml.

Still procedural: patterns + thresholds duplicated as code constants.
More readable than Bash, but still not a shared policy language —
FE/methodology leads cannot edit this safely without a Python owner.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Rule:
    name: str
    severity: str
    pattern: str
    threshold: int
    note: str


# --- hand-maintained rule table (change here, hope docs match) ---
RULES = [
    Rule(
        "setup_violation",
        "error",
        r"VIOLATED.*\bsetup\b|Setup\s+slack\s+-\d",
        0,
        "Timing setup fails (any count is actionable).",
    ),
    Rule(
        "hold_violation",
        "error",
        r"VIOLATED.*\bhold\b|Hold\s+slack\s+-\d",
        0,
        "Timing hold fails.",
    ),
    Rule(
        "max_transition",
        "warning",
        r"max_transition|MaxTran|MAXTRAN",
        10,
        "Flag only if more than 10 MaxTran hits (noise floor).",
    ),
    Rule(
        "drc_error",
        "error",
        r"\bDRC\b.*(error|violation|fail)|ERROR:\s*DRC",
        0,
        "Hard DRC errors.",
    ),
    Rule(
        "antenna",
        "warning",
        r"\bANTENNA\b|antenna\s+violation",
        5,
        "Antenna noise below 5 is ignored.",
    ),
    Rule(
        "congestion_hotspot",
        "warning",
        r"Congestion\s*>\s*0\.(8|9)|Overflow\s*>\s*[5-9]\d",
        0,
        "Routing congestion / overflow hotspots.",
    ),
    Rule(
        "fatal_or_abort",
        "fatal",
        r"\bFATAL\b|\bABORT\b|stack\s+trace|INTERNAL\s+ERROR",
        0,
        "Tool death / internal errors — stop and escalate.",
    ),
]


def scan(log_path: Path) -> dict:
    lines = log_path.read_text(errors="replace").splitlines()
    results = []
    for rule in RULES:
        rx = re.compile(rule.pattern, re.IGNORECASE)
        idxs = [i for i, ln in enumerate(lines) if rx.search(ln)]
        count = len(idxs)
        triggered = count > rule.threshold
        first = None
        if idxs:
            i = idxs[0]
            first = {"line": i + 1, "text": lines[i][:200]}
        results.append(
            {
                "name": rule.name,
                "severity": rule.severity,
                "count": count,
                "threshold": rule.threshold,
                "triggered": triggered,
                "note": rule.note,
                "first": first,
            }
        )
    return {
        "engine": "python_adhoc_procedural",
        "log": str(log_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()
    report = scan(args.log)
    print(f"# python ad-hoc report  log={report['log']}  ts={report['timestamp']}")
    print(f"# engine={report['engine']}")
    print()
    for r in report["results"]:
        flag = "TRIGGERED" if r["triggered"] else "ok"
        print(
            f"[{r['severity']:7}] {r['name']:22} count={r['count']:5} "
            f"thr={r['threshold']}  {flag}"
        )
        if r["triggered"] and r["first"]:
            print(f"           first @{r['first']['line']}: {r['first']['text'][:100]}")
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
