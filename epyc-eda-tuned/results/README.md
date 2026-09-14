# Results directory

Local experiment outputs land here. Tracked stubs only; raw logs are gitignored.

## Expected artifacts after a full lab day

| Path pattern | Contents |
|--------------|----------|
| `host_inventory.txt` | `detect_env.sh` |
| `sched_knobs*.txt` | knob dumps |
| `compare_<stamp>/` | A/B benches + summary |
| `claim_gate_<stamp>/` | gate header + compare copy + `gate.txt` |
| `bios_signoff_<date>.md` | filled BIOS checklist |

## Git policy

Ignore `compare_*`, `claim_gate_*`, and large logs. Optionally commit one anonymized **PASS** pack for posterity.
