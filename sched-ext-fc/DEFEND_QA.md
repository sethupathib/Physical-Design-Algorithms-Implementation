# Defend / Q&A

**Q: Did you run sched_ext?**  
A: No. `/sys/kernel/sched_ext` is absent on the measurement host. The post measures cgroup `cpu.weight` layers and maps them to `scx_layered` JSON.

**Q: Why not scx_simple/scx_rusty?**  
A: Cannot load BPF schedulers without `CONFIG_SCHED_EXT` and BTF. Shipping a fake “we ran rusty” claim would be the handwave.

**Q: Why is interactive a burn, not a latency probe?**  
A: Under CFS, short wake→burst requests already see p50/p99 ≈ burst on this host. Layer policy shows up as **CPU share** when interactive-class work is itself CPU-heavy (log forensics, re-STA, etc.).

**Q: Why did batch only drop to ~67% under 5:1 weights?**  
A: Work-conserving cgroups. Interactive entitlement exceeded what one thread can consume (1.0 CPU-eq on a 2-CPU pin); remainder went to batch.

**Q: nice matched layers — why prefer cgroups?**  
A: Farm orchestration matches cgroups (and later `scx_layered` match rules) more reliably than hoping every FC wrapper and engineer shell gets the right nice. nice is the magnitude control in the table.

**Q: SCHED_BATCH?**  
A: Null for always-runnable batch vs burn. Do not cite as a win.

**Q: Does this speed up Fusion Compiler place?**  
A: Not claimed. It changes how CPU is split when interactive-class work contends with FC batch on the same node.

**Q: protect vs layers?**  
A: Same outcome on a 2-CPU pin because `cpu.max` was not binding. On wider nodes, protect’s ceiling can bite batch harder — re-measure before citing.
