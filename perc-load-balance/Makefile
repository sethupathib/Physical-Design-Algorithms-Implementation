.PHONY: smoke plan-drc plan-perc simulate clean

smoke:
	bash scripts/smoke_test.sh

plan-drc:
	python3 scripts/plan_calibre_job.py --job configs/job_drc_example.yaml

plan-perc:
	python3 scripts/plan_calibre_job.py --job configs/job_perc_example.yaml

simulate:
	python3 scripts/simulate_dispatch.py --job configs/job_perc_example.yaml

clean:
	rm -rf results/plan_*.json results/plan_*.txt results/sim_*.txt results/launch_* results/bacct_score.txt
