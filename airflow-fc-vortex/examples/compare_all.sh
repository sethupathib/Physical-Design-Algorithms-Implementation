#!/usr/bin/env bash
# Compare ad-hoc Bash pipeline vs Airflow-style local runner (hacks).
# No Airflow install required.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/results"
mkdir -p "$OUT"
chmod +x "$ROOT/adhoc/bash_fc_vortex_pipeline.sh" "$ROOT/mock_tools"/*.py "$ROOT/scripts"/*.py 2>/dev/null || true

loc() { grep -cvE '^\s*(#|$)' "$1" 2>/dev/null || echo 0; }

LOC_ADHOC=$(loc "$ROOT/adhoc/bash_fc_vortex_pipeline.sh")
LOC_RUNNER=$(loc "$ROOT/scripts/local_runner.py")
LOC_DAG=$(loc "$ROOT/dags/fc_vortex_chain.py")
LOC_POLICY=$(loc "$ROOT/config/design_health.yaml")
LOC_WF=$(loc "$ROOT/config/workflows.json")
LOC_HACKS=$(loc "$ROOT/HACKS.md")

{
  echo "loc_adhoc_bash=$LOC_ADHOC"
  echo "loc_local_runner=$LOC_RUNNER"
  echo "loc_airflow_dag_chain=$LOC_DAG"
  echo "loc_policy_yaml=$LOC_POLICY"
  echo "loc_workflows_json=$LOC_WF"
} | tee "$OUT/loc.txt"

echo "---- run ad-hoc bash (correct JSON overall) ----"
t0=$(date +%s.%N)
NAIVE=0 bash "$ROOT/adhoc/bash_fc_vortex_pipeline.sh" "$OUT/adhoc" | tee "$OUT/adhoc.stdout"
t1=$(date +%s.%N)
python3 -c "print(f'{float('$t1')-float('$t0'):.3f}')" | tee "$OUT/adhoc.time"

echo "---- run ad-hoc bash NAIVE=1 (grep trap) ----"
NAIVE=1 bash "$ROOT/adhoc/bash_fc_vortex_pipeline.sh" "$OUT/adhoc_naive" | tee "$OUT/adhoc_naive.stdout"

echo "---- run local_runner (Airflow hacks, no Airflow) ----"
t0=$(date +%s.%N)
python3 "$ROOT/scripts/local_runner.py" --out "$OUT/runner" --work-secs 0.2 | tee "$OUT/runner.stdout"
t1=$(date +%s.%N)
python3 -c "print(f'{float('$t1')-float('$t0'):.3f}')" | tee "$OUT/runner.time"

pip install -q pyyaml >/dev/null 2>&1 || true

python3 - "$OUT" "$LOC_ADHOC" "$LOC_DAG" "$LOC_POLICY" "$LOC_WF" <<'PY' | tee "$OUT/SUMMARY.txt"
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
loc_adhoc, loc_dag, loc_pol, loc_wf = map(int, sys.argv[2:])
summary = json.loads((out/"runner"/"runner_summary.json").read_text())
adhoc_time = (out/"adhoc.time").read_text().strip()
runner_time = (out/"runner.time").read_text().strip()
naive_lines = (out/"adhoc_naive.stdout").read_text().splitlines()
fair_lines = (out/"adhoc.stdout").read_text().splitlines()
naive_fp = sum(1 for l in naive_lines if "FALSE-POSITIVE" in l)
fair_clean = sum(1 for l in fair_lines if "ARCHIVE" in l)

# extract hack signals
by = {e["hack"]: e for e in summary["events"]}
h5 = by.get("5_short_circuit", {})
h7 = by.get("7_retry_backoff", {})
h34 = by.get("3_4_pool_vs_unlimited", {})
h12 = by.get("1_2_chain_branch", {})

gate = "CITEABLE=yes_airflow_hacks_demo"
lines = []
lines.append("=" * 72)
lines.append("SUMMARY — Airflow hacks for FC + Vortex workflow optimization")
lines.append("=" * 72)
lines.append("")
lines.append("SCOPE")
lines.append("  Demo uses mock FC + mock Vortex. Point FC_BIN/VORTEX_BIN for production.")
lines.append("  local_runner.py proves the hacks without installing Airflow.")
lines.append("")
lines.append("1) Lines of code (non-blank, non-comment)")
lines.append(f"   Ad-hoc Bash pipeline          {loc_adhoc:5d}")
lines.append(f"   Airflow DAG fc_vortex_chain   {loc_dag:5d}")
lines.append(f"   Policy YAML (Vortex rules)    {loc_pol:5d}")
lines.append(f"   workflows.json (job list)     {loc_wf:5d}")
lines.append("   Note: adding a corner in Airflow = edit params/JSON; in Bash = edit script.")
lines.append("")
lines.append("2) Wall time (demo mocks, illustrative)")
lines.append(f"   ad-hoc bash     {adhoc_time}s")
lines.append(f"   local_runner    {runner_time}s")
lines.append("")
lines.append("3) Killer insight — naive grep vs structured overall")
lines.append(f"   NAIVE=1 false-positive routes: {naive_fp}  (grep hits rule names in JSON)")
lines.append(f"   Fair JSON overall ARCHIVE (clean): {fair_clean}")
lines.append("   Airflow branch uses Vortex overall — not brittle grep.")
lines.append("")
lines.append("4) Hack outcomes (local_runner)")
lines.append(f"   #1/#2 chain→branch: overall={h12.get('vortex_overall')} branch={h12.get('branch')}")
lines.append(f"   #3/#4 pool wall={h34.get('pooled_wall_s')}s vs unlimited={h34.get('unlimited_wall_s')}s "
             f"(pool_slots={h34.get('pool_slots')})")
lines.append(f"   #5 short-circuit: skipped_vortex={h5.get('skipped_vortex')} branch={h5.get('branch')}")
lines.append(f"   #7 retry: retries={h7.get('retries')} overall={h7.get('vortex_overall')}")
lines.append(f"   #8 factory jobs: {len(by.get('8_yaml_factory',{}).get('jobs',[]))}")
lines.append("")
lines.append("5) Optimization guidance (what to do Monday)")
lines.append("   - Create Airflow pool fc_licenses = # of FC seats")
lines.append("   - Drop dags/*.py into AIRFLOW_HOME/dags")
lines.append("   - Keep rules in config/design_health.yaml (shared with Vortex)")
lines.append("   - Add corners in params / workflows.json — not in Bash")
lines.append("   - Branch on Vortex severity instead of tribal grep knowledge")
lines.append("")
lines.append("6) Claim gate")
lines.append(f"   {gate}")
lines.append("   Does NOT claim Synopsys FC runtime reduction; claims workflow control.")
lines.append("=" * 72)
print("\n".join(lines))
(out/"CLAIM_GATE.txt").write_text(gate+"\n")
(out/"summary.json").write_text(json.dumps({
    "loc_adhoc": loc_adhoc,
    "loc_dag": loc_dag,
    "adhoc_time": adhoc_time,
    "runner_time": runner_time,
    "naive_false_positives": naive_fp,
    "fair_archive_clean": fair_clean,
    "claim_gate": gate,
    "h12_branch": h12.get("branch"),
    "h5_skip": h5.get("skipped_vortex"),
    "pool": h34,
}, indent=2))
PY

echo
echo "Artifacts under $OUT/"
