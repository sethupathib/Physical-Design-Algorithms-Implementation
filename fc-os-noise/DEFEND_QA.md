# Defend / Q&A — fc-os-noise

**Q: Did you enable isolcpus on this cloud VM?**  
A: No. Cmdline has no `isolcpus` / `nohz_full` / `rcu_nocbs`. The demo uses `taskset` soft-isolation. Boot knobs are documented for farm nodes.

**Q: Why is soft isolation enough for a CLAIM_GATE?**  
A: It isolates the **partition effect** under contention — the part you can prove without reboot. Dynticks/RCU are extra; don’t claim them from this host.

**Q: Why fixed-iteration burn instead of timed spin?**  
A: Timed spins exit on wall clock and hide preemption. Fixed work makes OS noise stretch round latency — required for an honest probe.

**Q: Will this speed up every FC stage?**  
A: No. Target CPU-bound parallel phases. I/O, licenses, and RAM pressure need other tools (local NVMe, NUMA bind, etc.).

**Q: How many threads on an 8-CPU quiet set?**  
A: Match the tool — e.g. `set_host_options -max_cores 8`. Oversubscription undoes isolation.

**Q: Is isolcpus deprecated?**  
A: Some docs prefer cpusets. Both work; isolcpus+nohz_full+rcu_nocbs remains common HPC practice. Use what your farm can reboot with.

**Q: Chinese LLM suggested this — is it cargo cult?**  
A: The knobs are real kernel features with a long HPC paper trail. Always verify against kernel docs / source and **measure** FC wall before/after.
