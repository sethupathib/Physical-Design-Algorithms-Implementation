.PHONY: demo compare test figures pdf gif all-docs clean
demo:
	python3 scripts/local_runner.py
compare:
	bash examples/compare_all.sh
test:
	python3 tests/test_smoke.py
figures:
	python3 docs/gen_figures.py
gif:
	python3 demo/gen_gif.py
pdf:
	python3 docs/build_whitepaper_pdf.py
all-docs: figures gif pdf
clean:
	rm -rf results/adhoc results/adhoc_naive results/runner
