# TSRI_BASELINE — facts pulled into this lab

Source document (user-provided baseline):

`dsd_EDA_tool_execution_in_TSRI_EDA_Cloud_2_0_UserGuide_r1_3_TC_aeeb.pdf`  
*EDA tool execution in TSRI EDA Cloud 2.0 User Guide, r1.3 (2025-04-17)*

## Encoded defaults

| Guide point | Lab encoding |
|-------------|--------------|
| Queues int / bat.m / bat.l | `farm.queues` |
| Max slot per user 128; 1 slot = 1 core | `max_slots_per_user`, planner math |
| bat.l for large multi-host work | default `queue: bat.l` |
| Calibre `-turbo`; example 3 hosts × 4 turbo = 12 | `job_drc_example.yaml` |
| Master 1 core for remote Calibre pattern | `defaults.master_slots: 1` |
| Hosts×CPU must not exceed user slot max | hard BLOCK in planner |
| mem select does not reserve | `mem_select_reserves: false` + warning |
| Avoid hyper on large layouts if OOM-killed | `enable_hyperflex: false` default |
| bacct HOG / CPU_EFFICIENCY feedback | `parse_bacct_fixture.py` |

## Not in the PDF (explicitly assumed)

Siemens **license feature names and MT token ratios** — must be site-calibrated via `lmstat`. The PDF focuses on LSF submission and slot/memory behavior.
