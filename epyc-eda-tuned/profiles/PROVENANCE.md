# Profile provenance

Mirrored **verbatim** from AlmaLinux 8.10 package:

| Field | Value |
|-------|-------|
| Package | `tuned-2.22.1-5.el8_10.noarch` |
| RPM URL | `https://repo.almalinux.org/almalinux/8.10/BaseOS/x86_64/os/Packages/tuned-2.22.1-5.el8_10.noarch.rpm` |
| RPM SHA256 | `0f4df49f483e4e3939a64464e677085ff4672f84431dfb55097b6b8e5da54ff5` |
| Upstream note | Profile added in tuned `2.22.1-2` (RHEL-27528) |

Do **not** edit mirrored `tuned.conf` files for experiments.  
Create overlays under `/etc/tuned/<name>/` on the target host, or `profiles/overlays/<name>/` in-repo.

## Files

| Path | Role |
|------|------|
| `epyc-eda/tuned.conf` | Subject profile |
| `throughput-performance/tuned.conf` | Parent (`include=`) |
| `hpc-compute/tuned.conf` | Contrast profile (different parent) |
