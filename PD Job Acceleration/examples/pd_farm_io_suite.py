#!/usr/bin/env python3
"""
Multi-phase I/O-bound Physical Design farm suite.

Phases (all PD-shaped, minimal compute):
  1) liberty_vault   — tens of thousands of tiny .lib cell files
  2) lib_lookups     — hundreds of thousands of random cell opens/reads
  3) spef_shards     — many per-net SPEF fragments + merge stream
  4) eco_checkpoints — repeated fat DB write+read storms
  5) report_spam     — thousands of tiny window reports + growing log

Optional NFS RTT emulation (--nfs-us): sleep this many microseconds around
each tiny file open/read/write. Use on the baseline (durable) path to model
farm NFS metadata latency. Leave at 0 on tmpfs.

This is the difference the tmpfs+rsync pattern is designed for.
"""
from __future__ import annotations

import argparse
import os
import random
import struct
import sys
import time
from pathlib import Path


def now() -> float:
    return time.perf_counter()


def stamp(log, **kv):
    line = " ".join(f"{k}={v}" for k, v in kv.items())
    print(line, flush=True)
    log.write(line + "\n")
    log.flush()


class IOFS:
    """Filesystem helper with optional per-op NFS RTT emulation."""

    def __init__(self, nfs_us: int = 0):
        self.nfs_us = max(0, int(nfs_us))
        self.ops = 0
        self.bytes_r = 0
        self.bytes_w = 0

    def _rtt(self):
        if self.nfs_us:
            time.sleep(self.nfs_us / 1_000_000.0)
        self.ops += 1

    def write_text(self, path: Path, text: str):
        self._rtt()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode()
        path.write_bytes(data)
        self.bytes_w += len(data)
        if self.nfs_us:
            # metadata/commit cost on NFS-like durable stores
            self._rtt()

    def write_bytes(self, path: Path, data: bytes):
        self._rtt()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.bytes_w += len(data)
        if self.nfs_us:
            self._rtt()

    def read_bytes(self, path: Path) -> bytes:
        self._rtt()
        data = path.read_bytes()
        self.bytes_r += len(data)
        return data

    def write_db(self, path: Path, mb: int):
        """Fat sequential write (checkpoint)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        chunk = os.urandom(1024 * 1024)
        self._rtt()
        with path.open("wb") as f:
            for _ in range(mb):
                f.write(chunk)
                self.bytes_w += len(chunk)
            if self.nfs_us:
                f.flush()
                os.fsync(f.fileno())
                self._rtt()

    def read_db(self, path: Path):
        self._rtt()
        with path.open("rb") as f:
            while True:
                b = f.read(1024 * 1024)
                if not b:
                    break
                self.bytes_r += len(b)
        if self.nfs_us:
            self._rtt()


def phase_liberty_vault(fs: IOFS, vault: Path, n_cells: int, log):
    t0 = now()
    if vault.exists():
        for p in vault.glob("cell_*.lib"):
            p.unlink()
    vault.mkdir(parents=True, exist_ok=True)
    for i in range(n_cells):
        text = (
            f"cell(CELL_{i:05d}) {{\n"
            f"  area : {1.0 + (i % 50) * 0.01};\n"
            f"  pin(A) {{ direction : input; capacitance : 0.{i % 900:03d}; }}\n"
            f"  pin(Z) {{ direction : output; function : \"A\"; }}\n"
            f"}}\n"
        )
        fs.write_text(vault / f"cell_{i:05d}.lib", text)
    stamp(log, phase="liberty_vault", cells=n_cells, seconds=f"{now()-t0:.3f}")


def phase_lib_lookups(fs: IOFS, vault: Path, n_cells: int, n_lookups: int, log):
    t0 = now()
    rng = random.Random(42)
    checksum = 0
    for _ in range(n_lookups):
        i = rng.randrange(n_cells)
        data = fs.read_bytes(vault / f"cell_{i:05d}.lib")
        checksum = (checksum + data[0] + len(data)) & 0xFFFFFFFF
    stamp(
        log,
        phase="lib_lookups",
        lookups=n_lookups,
        checksum=checksum,
        seconds=f"{now()-t0:.3f}",
    )
    return checksum


def phase_spef_shards(fs: IOFS, shard_dir: Path, n_nets: int, log):
    t0 = now()
    shard_dir.mkdir(parents=True, exist_ok=True)
    # Write many tiny per-net SPEF fragments (common hierarchical SPEF pattern)
    for i in range(n_nets):
        body = (
            f"*D_NET net_{i:05d} 0.{i%999:03d}\n"
            f"*CONN\n*I inst_{i%97}/Z O\n*I inst_{i%91}/A I\n"
            f"*CAP\n1 inst_{i%97}/Z 0.{i%50:02d}\n"
            f"*RES\n1 inst_{i%97}/Z inst_{i%91}/A {1+(i%20)}.{i%10}\n"
            f"*END\n"
        )
        fs.write_text(shard_dir / f"net_{i:05d}.spef", body)

    # Merge stream: read all shards sequentially into one SPEF
    out = []
    out.append("SPEF\n*DESIGN \"chip\"\n")
    for i in range(n_nets):
        out.append(fs.read_bytes(shard_dir / f"net_{i:05d}.spef").decode())
    merged = "".join(out).encode()
    fs.write_bytes(shard_dir / "merged.spef", merged)
    stamp(
        log,
        phase="spef_shards",
        nets=n_nets,
        merged_bytes=len(merged),
        seconds=f"{now()-t0:.3f}",
    )


def phase_eco_checkpoints(fs: IOFS, tmp: Path, n_ckpts: int, db_mb: int, log):
    t0 = now()
    for c in range(1, n_ckpts + 1):
        p = tmp / f"eco_iter{c}.db"
        fs.write_db(p, db_mb)
        fs.read_db(p)
    stamp(
        log,
        phase="eco_checkpoints",
        checkpoints=n_ckpts,
        db_mb=db_mb,
        seconds=f"{now()-t0:.3f}",
    )


def phase_report_spam(fs: IOFS, report_dir: Path, grow_log: Path, n_reports: int, log):
    t0 = now()
    report_dir.mkdir(parents=True, exist_ok=True)
    # growing opt log + many tiny window reports
    chunks = []
    for i in range(n_reports):
        fs.write_text(
            report_dir / f"win_{i:04d}.rpt",
            f"WINDOW {i}\nwns=-0.{i%99:02d}\ntns=-{i%500}.0\ndensity=0.{50+i%40}\n",
        )
        chunks.append(f"OPT step={i} cost={i*17%10007} dens=0.{50+i%40}\n")
    fs.write_text(grow_log, "".join(chunks))
    stamp(log, phase="report_spam", reports=n_reports, seconds=f"{now()-t0:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="job root (cwd usually)")
    ap.add_argument("--nfs-us", type=int, default=0, help="emulated NFS RTT per tiny op (µs)")
    ap.add_argument("--cells", type=int, default=25000)
    ap.add_argument("--lookups", type=int, default=200000)
    ap.add_argument("--nets", type=int, default=20000)
    ap.add_argument("--checkpoints", type=int, default=4)
    ap.add_argument("--db-mb", type=int, default=32)
    ap.add_argument("--reports", type=int, default=4000)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    tmp = root / "tmp"
    logs = root / "logs"
    outputs = root / "outputs"
    for d in (tmp, logs, outputs):
        d.mkdir(parents=True, exist_ok=True)

    fs = IOFS(nfs_us=args.nfs_us)
    log_path = logs / "pd_farm_io.log"
    with log_path.open("w") as log:
        stamp(
            log,
            cwd=str(root),
            TMPDIR=os.environ.get("TMPDIR", "unset"),
            tmp_resolved=str(tmp.resolve()),
            logs_resolved=str(logs.resolve()),
            nfs_us=args.nfs_us,
            start_epoch=f"{time.time():.9f}",
            start=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        )
        t_all = now()

        vault = tmp / "lib_vault"
        phase_liberty_vault(fs, vault, args.cells, log)
        checksum = phase_lib_lookups(fs, vault, args.cells, args.lookups, log)
        phase_spef_shards(fs, tmp / "spef_shards", args.nets, log)
        phase_eco_checkpoints(fs, tmp, args.checkpoints, args.db_mb, log)
        phase_report_spam(fs, tmp / "reports", logs / "opt_grow.log", args.reports, log)

        # Durable deliverables only
        fs.write_text(outputs / "lookup_checksum.txt", f"{checksum}\n")
        # Keep a compact SPEF head as proof of merge (not full multi‑MB unless small)
        merged = tmp / "spef_shards" / "merged.spef"
        data = merged.read_bytes()
        # copy without extra NFS tax accounting on outputs (still real write)
        (outputs / "merged_head.spef").write_bytes(data[: min(len(data), 1_000_000)])
        last_db = tmp / f"eco_iter{args.checkpoints}.db"
        if last_db.exists():
            (outputs / "design_final.db").write_bytes(last_db.read_bytes())

        summary = (
            f"checksum={checksum}\n"
            f"nfs_us={args.nfs_us}\n"
            f"ops={fs.ops}\n"
            f"bytes_r={fs.bytes_r}\n"
            f"bytes_w={fs.bytes_w}\n"
            f"cells={args.cells}\n"
            f"lookups={args.lookups}\n"
            f"nets={args.nets}\n"
        )
        (outputs / "JOB_SUMMARY.txt").write_text(summary)
        (logs / "STATUS").write_text("PASS\n")

        stamp(
            log,
            phase="all_done",
            seconds=f"{now()-t_all:.3f}",
            ops=fs.ops,
            bytes_r=fs.bytes_r,
            bytes_w=fs.bytes_w,
            checksum=checksum,
        )
        stamp(
            log,
            done_epoch=f"{time.time():.9f}",
            done=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        )

    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
