# COMMAND_RUNBOOK — epyc-eda operations

All commands assume cwd = `epyc-eda-tuned/` unless noted.

---

## 0. Build & safe inventory (any Linux)

```bash
make bin
make test
./scripts/detect_env.sh
./scripts/dump_sched_knobs.sh
./scripts/apply_epyc_eda.sh show
./scripts/compare_profiles.sh --dry-run
```

Artifacts land in `results/`.

---

## 1. Discover whether `epyc-eda` exists

```bash
rpm -q tuned || dnf info tuned
tuned-adm list | grep -i epyc
tuned-adm recommend
```

Expected on Alma/RHEL/Rocky **≥ 8.10** with current BaseOS tuned: a line describing EDA / `epyc-eda`.

---

## 2. Apply the distro profile

```bash
sudo tuned-adm profile epyc-eda
tuned-adm active
sudo tuned-adm verify
./scripts/verify_profile.sh
./scripts/dump_sched_knobs.sh results/knobs_post_apply.txt
```

Success criteria:

- Active profile contains `epyc-eda`
- `sched_migration_cost_ns` reads **10000**
- `verify_profile.sh` exits 0

---

## 3. Install mirrored profile (air-gap / older package)

```bash
sudo ./scripts/install_local_profile.sh
# equivalent:
# sudo mkdir -p /etc/tuned/epyc-eda
# sudo cp profiles/epyc-eda/tuned.conf /etc/tuned/epyc-eda/
# sudo tuned-adm profile epyc-eda
```

`/etc/tuned/` overrides / custom profiles take precedence over `/usr/lib/tuned/`.

---

## 4. Pre-8.10 workaround (AMD-documented pattern)

```bash
sudo tuned-adm profile throughput-performance
sudo ./scripts/apply_epyc_eda.sh manual-sysctl
./scripts/verify_profile.sh   # checks the knob; tuned name may not say epyc-eda
```

---

## 5. A/B without changing TuneD profile name

```bash
sudo ./scripts/compare_profiles.sh
# writes results/compare_<stamp>/{bench_high,bench_low,summary}.txt
```

---

## 6. CLAIM_GATE (publishability)

```bash
sudo ./scripts/claim_gate.sh; echo exit=$?
# 0 PASS | 1 FAIL | 3 SKIP
```

---

## 7. Roll back

```bash
sudo tuned-adm profile throughput-performance
# or
sudo tuned-adm profile balanced
# or
sudo tuned-adm off
```

If you used `manual-sysctl`, restore from `results/migration_cost_before.txt`:

```bash
MIG=$(cat results/migration_cost_before.txt)
PATH_MIG=/proc/sys/kernel/sched_migration_cost_ns
# or debugfs path from dump_sched_knobs.sh
echo "$MIG" | sudo tee "$PATH_MIG"
```

---

## 8. Useful inspections

```bash
# governors
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort | uniq -c

# NUMA
numactl -H
lscpu -e

# TuneD plugin effective tree
tuned-adm profile_info epyc-eda 2>/dev/null || true
```

---

## 9. Combining with job pinning (grids)

TuneD is host-global. Per-job still use:

```bash
numactl --cpunodebind=0 --membind=0 <eda_tool> ...
taskset -c 0-15 <eda_tool> ...
```

Especially on **2P** hosts (AMD cites ~5% hit without pinning).

---

## 10. Failure cheat-sheet

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `epyc-eda` missing | tuned too old | upgrade or `install_local_profile.sh` |
| verify fails migration cost | debugfs / plugin path | mount debugfs; dump knobs |
| claim_gate SKIP | no write permission | run sudo on bare metal |
| Intel host, knob unchanged | `[scheduler.amd]` no match | expect no override |
| huge variance | noisy VM | quiet queue / bare metal |
