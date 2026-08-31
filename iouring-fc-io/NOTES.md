# Technical notes — io_uring × Fusion Compiler

## Where FC spends I/O

Typical digital PnR jobs touch:

- **Startup / link** — thousands of small technology and library files
- **Design load** — large netlist + DEF/ODB
- **Checkpoint / reports** — periodic large writes + end-of-stage logs
- **Signoff handoff** — SPEF/RCDB, timing reports

Kernel path today for most tools: POSIX `read`/`write` or memory-map. `io_uring` reduces syscall transitions and enables deeper queueing when many fds are in flight.

## What a methodology team can change Monday

| Lever | Effort | Expectation |
|---|---|---|
| Local NVMe stage-in before FC | Low | Big win if NFS-cold |
| io_uring copy/hydrate tool | Medium | Wins on many-small-file decks |
| Ask Synopsys AE about I/O | Soft | Unknown; closed source |
| Vortex/log post-process via io_uring | Medium | Helps GB log ingest |

## How to A/B on the farm

1. Same deck hash, same host SKU  
2. Cold cache: `echo 3 > /proc/sys/vm/drop_caches` (root) or reboot  
3. Time **only** stage-in with posix vs io_uring copier  
4. Then time FC with staged local tree (identical for both)  
5. Cite stage-in delta from this harness; cite FC delta only if measured separately

## Kernel requirements

- Linux 5.1+ (`io_uring`); 5.10+ preferred  
- `liburing` userspace  
- Check `/proc/sys/kernel/io_uring_disabled` is `0`
