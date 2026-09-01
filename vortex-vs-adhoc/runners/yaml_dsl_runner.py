#!/usr/bin/env python3
"""
Reference YAML-DSL runner (methodology demo).

This is NOT the Vortex binary. It interprets the same policy YAML so you can
compare LOC / maintainability / output shape on any machine.

For the real product path:
  export VORTEX_BIN=/path/to/vortex
  ./examples/compare_all.sh
"""

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
    print("ERROR: PyYAML required — pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def load_policy(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not data or "rules" not in data:
        raise SystemExit(f"bad policy: {path}")
    return data


def scan(log_path: Path, policy: dict) -> dict:
    text = log_path.read_text(errors="replace").splitlines()
    defaults = policy.get("defaults") or {}
    default_ctx = int(defaults.get("context_lines", 1))
    case_sensitive = bool(defaults.get("case_sensitive", False))
    flags = 0 if case_sensitive else re.IGNORECASE

    results = []
    for rule in policy["rules"]:
        name = rule["name"]
        sev = rule.get("severity", "info")
        pat = rule["pattern"]
        thr = int(rule.get("count_threshold", 0))
        ctx = int(rule.get("context_lines", default_ctx))
        rx = re.compile(pat, flags)
        hits = []
        for i, line in enumerate(text):
            if rx.search(line):
                lo = max(0, i - ctx)
                hi = min(len(text), i + ctx + 1)
                hits.append(
                    {
                        "line": i + 1,
                        "text": line.rstrip("\n"),
                        "context": text[lo:hi],
                    }
                )
        count = len(hits)
        triggered = count > thr
        results.append(
            {
                "name": name,
                "severity": sev,
                "count": count,
                "threshold": thr,
                "triggered": triggered,
                "note": rule.get("note", ""),
                "hits": hits[:50],  # cap for report size
                "hits_truncated": max(0, count - 50),
            }
        )

    triggered = [r for r in results if r["triggered"]]
    return {
        "engine": "yaml_dsl_reference",
        "policy": policy.get("policy_name", path_name(policy)),
        "log": str(log_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rules_total": len(results),
        "rules_triggered": len(triggered),
        "results": results,
    }


def path_name(policy: dict) -> str:
    return str(policy.get("policy_name", "unnamed"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Reference YAML DSL log scanner")
    ap.add_argument("--policy", required=True, type=Path)
    ap.add_argument("--log", required=True, type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    policy = load_policy(args.policy)
    report = scan(args.log, policy)

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"# YAML-DSL report  policy={report['policy']}  log={report['log']}")
    print(f"# utc={report['timestamp']}  triggered={report['rules_triggered']}/{report['rules_total']}")
    print()
    for r in report["results"]:
        flag = "TRIGGERED" if r["triggered"] else "ok"
        print(
            f"[{r['severity']:7}] {r['name']:22} count={r['count']:5} "
            f"thr={r['threshold']}  {flag}"
        )
        if r["triggered"] and r["hits"]:
            h = r["hits"][0]
            print(f"           first @{h['line']}: {h['text'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
