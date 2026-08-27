# Airflow Hacks for FC + Vortex — cheat sheet
#
# Full prose: README.md + WHITEPAPER.md
# Laptop demo (no Airflow install):  python3 scripts/local_runner.py
# Real Airflow: copy dags/ into $AIRFLOW_HOME/dags and create pool `fc_licenses`

## Hack map

| # | Hack | Airflow feature | Why CAD/methodology cares |
|---|---|---|---|
| 1 | FC → Vortex chain | TaskFlow + XCom (log path) | Automatic forensics after every run |
| 2 | Severity router | `@task.branch` | Fatal pages on-call; clean archives |
| 3 | License seats | **Pool** `fc_licenses` | Stop license thrash / queue storms |
| 4 | Multi-corner | `.expand()` dynamic mapping | Add PVT corner without copy-paste |
| 5 | Short-circuit | `@task.short_circuit` | Skip Vortex if FC already dead |
| 6 | Log landing | **Dataset** schedule | Vortex fires when NFS log appears |
| 7 | Flaky license | `retries` + `retry_delay` | Survive checkout blips |
| 8 | Workflow-as-YAML/JSON | DAG factory / `workflows.json` | Methodology edits jobs, not Python |
| 9 | SLA miss | `sla` + callback | Know when FC overruns the night |
| 10 | One-click trigger | DAG `params` + UI/API | Design/corner from the form |

## 30-second optimization guide

1. Create Airflow pool `fc_licenses` with slots = purchased seats.  
2. Drop `dags/fc_vortex_chain.py` and `dags/fc_multicorner_map.py` into `dags/`.  
3. Set `VORTEX_POLICY` to your YAML; optionally `FC_BIN` / `VORTEX_BIN`.  
4. Trigger with params `{design, corner}`.  
5. Read Vortex JSON / branch outcome — not raw `grep` scrolls.

## Anti-patterns these replace

- Cron + 200-line Bash that nobody owns  
- 8 terminals of interactive `fc_shell`  
- “Did anyone run Vortex on last night’s log?”  
- 40 concurrent FC jobs fighting 8 licenses  
