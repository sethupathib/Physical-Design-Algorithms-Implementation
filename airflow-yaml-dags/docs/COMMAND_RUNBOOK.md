# COMMAND_RUNBOOK

```bash
cd airflow-yaml-dags

# Install (use your Airflow venv in production)
pip install -r requirements.txt

# Render only
python3 scripts/render_dags.py
ls generated/

# Render into dags/ for Airflow
python3 scripts/render_dags.py --also-dags

# Structural YAML checks
make validate

# Load via dag-factory (needs airflow + dag-factory installed)
make smoke
```

## Add a design

1. Append a row under `designs:` in `configs/designs.yaml`
2. `make render`
3. Confirm new `eda__<design>__<stage>.yml`
4. Trigger: `airflow dags trigger eda__<design>__<stage>` (on a real deploy)

## Change the skeleton

Edit `templates/eda_flow.yml.j2` once → re-render → all DAGs pick up the graph change.

## CI suggestion

```yaml
- run: pip install -r airflow-yaml-dags/requirements.txt
- run: make -C airflow-yaml-dags smoke
```
