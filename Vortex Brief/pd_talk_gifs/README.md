# PD talk GIFs — continuous build-up

Teaching GIFs for a 1-hour PD talk. Each frame **keeps** prior layers (nothing resets).

## Floorplan — `floorplan_flow.gif`

util → size → pins → power → macros → DRC → `defOut` / `saveDesign`

```bash
python3 gen_floorplan_gif.py
```

Clean frames use non-overlapping macros with clear channels. Frame `f06` intentionally abuts `SRAM0`/`SRAM1` for a **halo!** spacing violation; `f06b` restores the clean pack.

Physical cells (endcap / welltap / decap) are **not** shown — mention verbally if needed.

## Placement — `placement_flow.gif`

Starts from the finished floorplan, then:

1. Global placement  
2. HFNS (high-fanout buffer tree)  
3. Detail placement  
4. Legalization (on-row / site-aligned)  
5. Density / congestion overlay  
6. Timing optimization (WNS path → fix) → handoff to CTS  

```bash
python3 gen_placement_gif.py
```

Writes `placement_frames/*.png` and `placement_flow.gif`.
