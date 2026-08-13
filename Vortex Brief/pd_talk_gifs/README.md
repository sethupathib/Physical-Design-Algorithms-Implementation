# Floorplan continuous build-up GIF

Teaching GIF for a 1-hour PD talk: each frame **keeps** prior layers (util → size → pins → power → macros → DRC → `defOut` / `saveDesign`).

## Regenerate

```bash
python3 gen_floorplan_gif.py
```

Writes `floorplan_frames/*.png` and `floorplan_flow.gif`.

## Macro layout

Clean frames use non-overlapping macros with ≥~45 px channels. Frame `f06` intentionally abuts `SRAM0`/`SRAM1` to show a **halo!** spacing violation; `f06b` restores the clean pack.
