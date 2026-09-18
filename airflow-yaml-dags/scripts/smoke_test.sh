#!/usr/bin/env bash
# smoke_test.sh — render YAML and load DAGs via dag-factory (no scheduler required).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"
export AIRFLOW_HOME="${AIRFLOW_HOME:-$ROOT/.airflow_home}"
mkdir -p "$AIRFLOW_HOME"

cd "$ROOT"
python3 scripts/render_dags.py --also-dags

python3 <<'PY'
import os, sys
from pathlib import Path

root = Path(".").resolve()
sys.path.insert(0, str(root / "dags"))

# Import loader which calls load_yaml_dags into its module globals
import importlib.util
spec = importlib.util.spec_from_file_location("eda_loader", root / "dags" / "_loader.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

dags = {k: v for k, v in vars(mod).items() if hasattr(v, "dag_id")}
print(f"loaded_dag_count={len(dags)}")
for dag_id in sorted(dags):
    dag = dags[dag_id]
    tasks = list(dag.task_dict.keys())
    print(f"dag_id={dag_id} tasks={tasks}")

expect = {
    "eda__demo_chip_a__place": {"prepare_dirs", "run_engine", "collect_logs", "vortex_slice"},
    "eda__demo_chip_a__route": {"prepare_dirs", "run_engine", "collect_logs", "vortex_slice"},
    "eda__demo_chip_b__sta": {"prepare_dirs", "run_engine", "collect_logs"},
}
missing = [k for k in expect if k not in dags]
if missing:
    raise SystemExit(f"FAIL missing dags: {missing}")

for dag_id, want in expect.items():
    got = set(dags[dag_id].task_dict)
    if got != want:
        raise SystemExit(f"FAIL {dag_id}: got={got} want={want}")

# Dependency check: run_engine <- prepare_dirs
for dag_id in expect:
    eng = dags[dag_id].task_dict["run_engine"]
    ups = {t.task_id for t in eng.upstream_list}
    if ups != {"prepare_dirs"}:
        raise SystemExit(f"FAIL deps {dag_id} run_engine upstream={ups}")

print("smoke_result=PASS")
PY
