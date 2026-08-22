# Example results (fill on your multi-socket host)

Machine: _______________________________
OS / kernel: ___________________________
numactl -H summary:
```
(paste here)
```

## STREAM-triad bandwidth (GiB/s) — higher is better

| Binding | Threads | Bytes | Triad GiB/s |
|---------|---------|-------|-------------|
| unbound |         |       |             |
| `--cpunodebind=0 --membind=0` | | | |
| `--cpunodebind=0 --membind=1` (remote) | | | |
| `--interleave=all` | | | |

Remote / local triad ratio: ______  (expect ~0.5–0.8 on typical dual-socket)

## Pointer-chase latency (ns/hop) — lower is better

| Binding | Bytes | Latency ns/hop |
|---------|-------|----------------|
| local   |       |                |
| remote  |       |                |

Remote / local latency ratio: ______  (expect >1.0)

## Notes

- What surprised you?
- Did interleave help or hurt for this workload?
- Would you pin FC to one node or interleave for your design size?
