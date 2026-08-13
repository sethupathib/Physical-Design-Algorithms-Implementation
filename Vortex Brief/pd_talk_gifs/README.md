# PD talk GIFs — continuous build-up

Teaching GIFs for a 1-hour PD talk. Each frame **keeps** prior layers (nothing resets).

## Floorplan — `floorplan_flow.gif`

util → size → pins → power → macros → DRC → `defOut` / `saveDesign`

```bash
python3 gen_floorplan_gif.py
```

## Placement — `placement_flow.gif`

global → HFNS → detail → legal → density/congestion → timing opt → CTS

```bash
python3 gen_placement_gif.py
```

## CTS — `cts_flow.gif`

cluster → balance → clock route → post-route conditioning → ID/skew/timing opt → Route

```bash
python3 gen_cts_gif.py
```

## Routing — `route_flow.gif`

1. Global routing (G-cell corridors)  
2. Track assignment  
3. Detail routing (wires + vias)  
4. DRC fix (short/spacing → clean)  
5. Timing optimization → signoff handoff  

```bash
python3 gen_route_gif.py
```
