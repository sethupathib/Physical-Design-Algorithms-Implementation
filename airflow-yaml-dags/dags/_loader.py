"""Airflow DAG loader — turns generated YAML into DAG objects via dag-factory.

Drop this file (and the rendered ``eda__*.yml`` files) into your Airflow
``dags/`` folder, or point ``AIRFLOW__CORE__DAGS_FOLDER`` here.
"""

from __future__ import annotations

from pathlib import Path

from dagfactory import load_yaml_dags

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GENERATED = ROOT / "generated"
DEFAULTS_DIR = ROOT / "configs"

# Prefer YAML sitting next to this loader (Airflow dags folder).
# Fall back to generated/ for local smoke tests before --also-dags copy.
yaml_here = list(HERE.glob("eda__*.yml")) + list(HERE.glob("eda__*.yaml"))
folder = HERE if yaml_here else GENERATED

load_yaml_dags(
    globals_dict=globals(),
    dags_folder=str(folder),
    defaults_config_path=str(DEFAULTS_DIR),
    suffix=["yml", "yaml"],
)
