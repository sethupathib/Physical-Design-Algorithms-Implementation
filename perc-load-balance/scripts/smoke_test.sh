#!/usr/bin/env bash
# smoke_test.sh — offline CLAIM checks (no Calibre/LSF required)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p results

echo "== plan DRC example =="
python3 scripts/plan_calibre_job.py --job configs/job_drc_example.yaml \
  --out results/plan_drc.json | tee results/plan_drc.txt
grep -q 'status=FEASIBLE\|status=REDUCED' results/plan_drc.txt

echo "== plan PERC example =="
python3 scripts/plan_calibre_job.py --job configs/job_perc_example.yaml \
  --out results/plan_perc.json | tee results/plan_perc.txt

echo "== overask should BLOCK or REDUCE =="
set +e
python3 scripts/plan_calibre_job.py --job configs/job_overask_example.yaml \
  --out results/plan_overask.json | tee results/plan_overask.txt
rc=$?
set -e
# Either blocked (exit 2) or reduced — must not silently claim full want
python3 - <<'PY'
import json
from pathlib import Path
p=json.loads(Path("results/plan_overask.json").read_text())
want_s, want_t = 16, 8
assert p["status"] in ("BLOCKED","REDUCED"), p
if p["status"]=="FEASIBLE":
    raise SystemExit("overask must not be fully FEASIBLE at want size")
if p["status"]=="REDUCED":
    assert p["remote_slaves"]*p["turbo"] < want_s*want_t
print("overask_guard=PASS", p["status"])
PY

echo "== simulate dispatch =="
python3 scripts/simulate_dispatch.py --job configs/job_drc_example.yaml | tee results/sim_drc.txt
grep -q 'FULL VIEW' results/sim_drc.txt

echo "== emit launch bundle =="
python3 scripts/emit_launch_bundle.py --job configs/job_drc_example.yaml \
  --out-dir results/launch_drc
test -x results/launch_drc/run.sh
test -f results/launch_drc/NOTES.md

echo "== bacct fixture scoring =="
python3 scripts/parse_bacct_fixture.py | tee results/bacct_score.txt
grep -q 'verdict=GOOD' results/bacct_score.txt
grep -q 'verdict=POOR_PARALLEL_OR_OVERREQUESTED' results/bacct_score.txt

echo "smoke_result=PASS"
