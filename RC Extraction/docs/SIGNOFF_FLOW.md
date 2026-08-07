# Signoff flow context

```
RTL → Synthesis → Place & Route → GDSII
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                   LVS / DRC              Parasitic Extraction
              (devices + nets OK?)         (R, C from geometry)
                         │                     │
                         └──────────┬──────────┘
                                    ▼
                              SPEF (+ .lib)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
                   STA        Crosstalk/SI       EM / IR
              (setup/hold)   (noise, delay)    (power grid)
```

This project focuses on the **parasitic extraction** box and the SPEF handoff to STA (via Elmore as a teaching stand-in for a full timer).
