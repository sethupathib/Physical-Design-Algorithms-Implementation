.PHONY: test build eval compare figures pdf gif all-docs
test:
	PYTHONPATH=src python3 tests/test_pdkg.py
build:
	PYTHONPATH=src python3 scripts/build_kg.py
eval:
	PYTHONPATH=src python3 scripts/eval_qa.py
compare:
	bash examples/compare_all.sh
figures:
	python3 docs/gen_figures.py
gif:
	python3 demo/gen_gif.py
pdf:
	python3 docs/build_whitepaper_pdf.py
all-docs: figures gif pdf
