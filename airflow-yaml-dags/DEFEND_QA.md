# DEFEND_QA — templatized Airflow DAGs

### Q1. Why not just write Python DAGs?
**A.** You can for one-offs. At `design × stage` cardinality, YAML inventory + one skeleton prevents copy-paste drift.

### Q2. Is YAML a second Airflow?
**A.** No. Airflow only runs Python DAG objects. dag-factory builds those objects from YAML at parse time.

### Q3. Why Jinja *and* dag-factory?
**A.** Jinja multiplies near-identical configs from an inventory. dag-factory turns each YAML into a DAG. Either alone is weaker for EDA farms.

### Q4. Why `schedule: null`?
**A.** Most PD jobs are kicked by humans/agents/queues, not cron. Use Airflow’s trigger API / CLI with conf.

### Q5. Does this replace an Agent?
**A.** No. Agent/decision layer chooses *which* design row to trigger. Airflow runs the graph. Vortex (optional task) forensics logs.

### Q6. Can I put Innovus commands in YAML?
**A.** Yes as `tool_cmd`, but keep secrets/modules out of git — use env vars, Connections, or a wrapper script on the worker.

### Q7. Dynamic Task Mapping instead?
**A.** Better when one DAG fans out over a runtime list. Static render is better when each design needs its own DAG-level ACL, SLA, or clear UI entry. Both are valid; this lab teaches the static render path.
