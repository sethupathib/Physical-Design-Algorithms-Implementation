# airflow-yaml-dags

**Templatized Airflow DAGs from YAML** for EDA-shaped farms — one Jinja skeleton × a design inventory → many DAGs via [dag-factory](https://github.com/astronomer/dag-factory).

> Self-contained lab; extractable as its own repo (`STANDALONE_REPO.md`).

## Why

PD pipelines are combinatorial (`design × stage`). Copy-pasting Python DAGs does not scale. This lab keeps:

| Layer | Owns |
|-------|------|
| `configs/designs.yaml` | Inventory (what to run) |
| `templates/eda_flow.yml.j2` | Skeleton (how the graph looks) |
| `scripts/render_dags.py` | Render (CI / local) |
| `dags/_loader.py` | dag-factory → Airflow DAG objects |

## Quick start

```bash
cd airflow-yaml-dags
pip install -r requirements.txt   # or use an existing Airflow env
make smoke                        # render + load DAGs (no scheduler UI required)
```

Expected: three DAGs

- `eda__demo_chip_a__place` — includes `vortex_slice`
- `eda__demo_chip_a__route` — includes `vortex_slice`
- `eda__demo_chip_b__sta` — engine only (vortex disabled)

## Layout

```
airflow-yaml-dags/
├── configs/designs.yaml      # inventory
├── configs/defaults.yml      # dag-factory defaults
├── templates/eda_flow.yml.j2 # skeleton
├── scripts/render_dags.py
├── scripts/smoke_test.sh
├── scripts/validate_yaml.sh
├── dags/_loader.py           # Airflow entrypoint
├── generated/                # rendered YAML (gitignored)
├── docs/COMMAND_RUNBOOK.md
├── WHITEPAPER.md
└── DEFEND_QA.md
```

## Drop into a real Airflow

1. `make render`
2. Copy `dags/_loader.py`, `dags/eda__*.yml`, and `configs/defaults.yml` (keep defaults path or adjust `_loader.py`) into your deployment’s DAG bag / image.
3. Trigger manually — these DAGs use `schedule: null` (external trigger).

## Non-claims

- Does not make FC/Innovus faster.
- Placeholders echo tool/vortex commands; swap for real binaries on your farm.
- Smoke test proves **DAG materialization**, not grid throughput.

## Product boundary note

Matches the Agent → Vortex → EDA engine split: Airflow runs the graph; optional `vortex_slice` task is log forensics only (does not drive APR).
