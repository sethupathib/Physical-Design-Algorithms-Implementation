.PHONY: render validate smoke clean

render:
	python3 scripts/render_dags.py --also-dags

validate:
	bash scripts/validate_yaml.sh

smoke:
	bash scripts/smoke_test.sh

clean:
	rm -f generated/eda__*.yml generated/MANIFEST.txt dags/eda__*.yml
