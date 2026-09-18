# WHITEPAPER — Templatized Airflow DAGs from YAML (EDA lab)

## 1. Problem

EDA farms run the same workflow shape many times:

```text
prepare → run_engine → collect_logs → (optional) vortex_slice
```

Varying only `design`, `stage`, paths, and flags. Maintaining one Python file per combo creates drift (retries differ, tags missing, vortex hook forgotten).

## 2. Pattern

**Templatized YAML DAGs** separate:

1. **Inventory** — which jobs exist (`designs.yaml`)
2. **Skeleton** — task graph (`eda_flow.yml.j2`)
3. **Materialization** — render + `dag-factory` load

Airflow still executes Python DAG objects. YAML is a generation front-end, not a second scheduler.

## 3. Control flow in this lab

```text
configs/designs.yaml
        │
        ▼
scripts/render_dags.py  +  templates/eda_flow.yml.j2
        │
        ▼
generated/eda__<design>__<stage>.yml  (+ copy into dags/)
        │
        ▼
dags/_loader.py  →  dagfactory.load_yaml_dags(...)
        │
        ▼
Airflow DagBag / UI
```

## 4. Design choices

| Choice | Rationale |
|--------|-----------|
| `schedule: null` | PD jobs are event/API triggered, not `@daily` |
| Stable `dag_id` = `eda__{design}__{stage}` | Idempotent naming for triggers & ACL |
| Jinja `{% if enable_vortex %}` | Optional forensics task without a second template |
| Render in CI, not at parse-time from DB | Reviewable YAML diffs; deterministic bag |
| BashOperator placeholders | Zero license deps in the lab; swap cmds later |

## 5. What we verify

`make smoke` asserts:

- Expected DAG ids exist after load
- Task sets match vortex on/off
- `run_engine` depends on `prepare_dirs`

That is a **materialization CLAIM**, not a runtime SLA claim.

## 6. Failure modes

- Editing generated YAML by hand → overwritten next render
- Putting heavy Python logic into `bash_command` strings → untestable; use real operators
- Generating thousands of DAGs into one bag → scheduler parse cost; shard or use dynamic task mapping for ultra-high cardinality
- Pointing loader at both `dags/` and `generated/` with duplicates → double registration; loader prefers `dags/`

## 7. Relation to Vortex

Optional last task documents the contract:

```text
vortex <log_dst> certify_high_quality 1 --search_by_rule <yaml>
```

Airflow orchestrates; Vortex reads logs only (does not drive APR). Same boundary as the product diagram.
