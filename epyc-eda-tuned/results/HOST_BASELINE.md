# Host baseline — Cursor Cloud agent VM (inventory only)

Generated during initial repo bring-up. **No performance claim.**

```
os: Ubuntu 24.04
cpu: Intel Xeon (not AMD)
tuned: absent
sched_migration_cost_ns: unreadable (debugfs permission denied)
claim_gate: SKIP (exit 3)
publishable_claim: NO
```

Re-run on an AMD EPYC RHEL/Alma/Rocky 8.10+ host:

```bash
sudo ./scripts/apply_epyc_eda.sh apply
sudo ./scripts/claim_gate.sh
```
