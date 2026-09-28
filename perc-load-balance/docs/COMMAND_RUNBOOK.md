# COMMAND_RUNBOOK

```bash
cd perc-load-balance
pip install -r requirements.txt

# Offline smoke (CI / laptop)
make smoke

# Plan
python3 scripts/plan_calibre_job.py --job configs/job_perc_example.yaml --json

# Compare naive vs full
python3 scripts/simulate_dispatch.py --job configs/job_overask_example.yaml

# Emit bundle for human review
python3 scripts/emit_launch_bundle.py --job configs/job_perc_example.yaml \
  --out-dir results/launch_perc
cat results/launch_perc/NOTES.md
```

## On a real LSF + Calibre host (TSRI / design-house sandbox)

```bash
busers
bhosts -w | head
lmstat -a | tee results/lmstat_before.txt

# Edit configs/farm.yaml licenses.* from lmstat
python3 scripts/plan_calibre_job.py --job configs/job_perc_example.yaml
python3 scripts/emit_launch_bundle.py --job configs/job_perc_example.yaml

# Review run.sh — then submit manually
# After completion:
# bacct -l <jobId> | tee results/bacct_<jobId>.txt
```

## Add your design

1. Copy `configs/job_perc_example.yaml` → `configs/job_<design>_perc.yaml`  
2. Set ruledeck/layout paths and `want_*`  
3. Plan → emit → checklist → submit  
4. Feed bacct back into next `want_*`
