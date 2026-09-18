# STANDALONE_REPO

```bash
cp -a airflow-yaml-dags ~/src/airflow-yaml-dags
cd ~/src/airflow-yaml-dags
git init
git add .
git commit -m "Initial import: templatized Airflow DAGs from YAML"
gh repo create airflow-yaml-dags --public --source=. --remote=origin --push
```

Suggested topics: `airflow`, `dag-factory`, `eda`, `yaml`, `physical-design`
