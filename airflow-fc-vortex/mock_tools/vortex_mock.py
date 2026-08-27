#!/usr/bin/env python3
"""mock vortex search_by_rule — YAML policy against a log. NOT the Vortex binary."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def load_policy(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    # tiny fallback: only supports our simple policy shape via json if provided
    raise SystemExit("PyYAML required: pip install pyyaml")


def run_rules(log_text: str, policy: dict) -> list[dict]:
    results = []
    for rule in policy.get("rules", []):
        pat = re.compile(rule["pattern"], re.IGNORECASE)
        hits = [i + 1 for i, line in enumerate(log_text.splitlines()) if pat.search(line)]
        count = len(hits)
        thr = int(rule.get("count_threshold", 0))
        triggered = count > thr
        results.append(
            {
                "name": rule["name"],
                "severity": rule.get("severity", "info"),
                "count": count,
                "count_threshold": thr,
                "triggered": triggered,
                "hit_lines": hits[:20],
                "note": rule.get("note", ""),
            }
        )
    return results


def overall(results: list[dict]) -> str:
    order = {"fatal": 3, "error": 2, "warning": 1, "info": 0}
    sev = 0
    for r in results:
        if r["triggered"]:
            sev = max(sev, order.get(r["severity"], 0))
    return {0: "clean", 1: "warning", 2: "error", 3: "fatal"}[sev]


def main() -> int:
    ap = argparse.ArgumentParser(description="Mock Vortex search_by_rule")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--json-out", default="")
    ap.add_argument("--fail-on", default="fatal", help="clean|warning|error|fatal")
    args = ap.parse_args()

    policy = load_policy(Path(args.policy))
    log_text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    results = run_rules(log_text, policy)
    level = overall(results)
    report = {
        "tool": "vortex_mock",
        "policy": str(Path(args.policy).resolve()),
        "log": str(Path(args.log).resolve()),
        "utc": datetime.now(timezone.utc).isoformat(),
        "overall": level,
        "triggered": [r["name"] for r in results if r["triggered"]],
        "results": results,
    }
    print(json.dumps(report, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    rank = {"clean": 0, "warning": 1, "error": 2, "fatal": 3}
    if rank[level] >= rank.get(args.fail_on, 3):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
