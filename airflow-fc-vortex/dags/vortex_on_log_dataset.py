"""
DAG: vortex_on_log_dataset  — Hack #6 Dataset-driven scheduling (Airflow 2.4+)

Idea: when an FC log "lands" (Dataset updated), Vortex runs automatically.
Demo uses a FileSensor-like pattern via Dataset for clarity.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

try:
    from airflow import DAG, Dataset
    from airflow.decorators import task
except ImportError as e:  # pragma: no cover
    raise ImportError("Need apache-airflow, or use scripts/local_runner.py") from e

ROOT = Path(os.environ.get("AFV_ROOT", Path(__file__).resolve().parents[1]))
VORTEX_MOCK = ROOT / "mock_tools" / "vortex_mock.py"
POLICY = Path(os.environ.get("VORTEX_POLICY", ROOT / "config" / "design_health.yaml"))
LOG_DATASET = Dataset("file:///tmp/airflow_fc_vortex/latest_fc.log")

with DAG(
    dag_id="vortex_on_log_landing",
    start_date=datetime(2024, 1, 1),
    schedule=[LOG_DATASET],  # Hack #6 — runs when dataset is updated by producer
    catchup=False,
    tags=["vortex", "dataset"],
) as dag:

    @task
    def search_by_rule() -> dict:
        log = Path("/tmp/airflow_fc_vortex/latest_fc.log")
        if not log.exists():
            return {"overall": "clean", "note": "no log yet"}
        out = log.with_suffix(".vortex.json")
        subprocess.run(
            [
                "python3",
                str(VORTEX_MOCK),
                "--policy",
                str(POLICY),
                "--log",
                str(log),
                "--json-out",
                str(out),
            ],
            check=False,
        )
        return json.loads(out.read_text())

    search_by_rule()


# Producer sketch (separate DAG or task outlets=[LOG_DATASET]) updates the Dataset
# after FC finishes — see docs in Hacks.md / WHITEPAPER.md.
