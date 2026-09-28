#!/usr/bin/env python3
"""Simulate why a Calibre DRC/PERC LSF launch pending/fails.

Shows the two silent killers explicitly:
  - slot ceiling (hosts × turbo + master vs max_slots_per_user)
  - license ceiling (base + MT tokens)

CPU/mem-only requests that ignore these look "fine" until the job never starts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from plan_calibre_job import plan_job  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--farm", type=Path, default=ROOT / "configs" / "farm.yaml")
    p.add_argument("--job", type=Path, required=True)
    p.add_argument(
        "--naive",
        action="store_true",
        help="Print naive CPU-only view (what engineers often check) vs full plan",
    )
    args = p.parse_args()

    farm = yaml.safe_load(args.farm.read_text())
    job = yaml.safe_load(args.job.read_text()).get("job")
    slaves = int(job["want_remote_slaves"])
    turbo = int(job["want_turbo"])
    master = int(farm.get("defaults", {}).get("master_slots", 1))
    compute = slaves * turbo

    print("=== NAIVE VIEW (CPU/mem only — incomplete) ===")
    print(f"want_remote_slaves={slaves}")
    print(f"want_turbo={turbo}")
    print(f"naive_cores={compute} (slaves×turbo)")
    print(f"mem_gb_per_slave={job.get('mem_gb_per_slave')}")
    print("naive_verdict=LOOKS_OK_IF_CLUSTER_HAS_CORES")
    print()

    plan = plan_job(farm, job)
    print("=== FULL VIEW (slots + licenses + semantics) ===")
    print(json.dumps(plan.to_dict(), indent=2))
    print()
    if plan.status == "BLOCKED":
        print("dispatch_simulation=WILL_NOT_RUN")
        print(
            "hint=LSF may accept the bsub then never schedule children, "
            "or Calibre aborts when MT tokens are exhausted."
        )
        return 2
    if plan.status == "REDUCED":
        print("dispatch_simulation=RUNS_ONLY_IF_REDUCED_PLAN_APPLIED")
        return 0
    print("dispatch_simulation=RUNNABLE_UNDER_CAPS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
