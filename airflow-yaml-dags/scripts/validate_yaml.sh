#!/usr/bin/env bash
# validate_yaml.sh — structural checks without Airflow import.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/render_dags.py"
python3 <<'PY'
from pathlib import Path
import yaml

gen = Path("generated")
files = sorted(gen.glob("eda__*.yml"))
assert files, "no generated YAML"
for f in files:
    data = yaml.safe_load(f.read_text())
    assert isinstance(data, dict) and len(data) == 1, f
    dag_id, body = next(iter(data.items()))
    assert dag_id == f.stem, (dag_id, f.stem)
    tasks = body["tasks"]
    ids = [t["task_id"] for t in tasks]
    assert ids[0] == "prepare_dirs"
    assert "run_engine" in ids and "collect_logs" in ids
    print(f"ok={f.name} tasks={ids}")
print(f"validate_result=PASS count={len(files)}")
PY
