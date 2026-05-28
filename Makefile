PYTHON ?= python3
DATA_SOURCE ?= sample
RAW_INPUT ?=
PROCESSED_DIR ?= data/processed
HF_ROW_LIMIT ?= 0
MATHLIB_SOURCE_DIR ?= data/raw/mathlib4
MATHLIB_REF ?= master

.PHONY: all data analyze web report video test clean web-vite mathlib-source

all: data analyze web report video

data:
	HF_ROW_LIMIT=$(HF_ROW_LIMIT) $(PYTHON) scripts/build_data.py --source $(DATA_SOURCE) --input "$(RAW_INPUT)" --output-dir $(PROCESSED_DIR)

mathlib-source:
	$(PYTHON) scripts/fetch_mathlib_source.py --output-dir $(MATHLIB_SOURCE_DIR) --ref $(MATHLIB_REF)

analyze:
	$(PYTHON) scripts/build_figures.py --data-dir $(PROCESSED_DIR) --figures-dir figures

web:
	$(PYTHON) scripts/build_static_site.py --data-dir $(PROCESSED_DIR) --docs-dir docs

web-vite:
	npm --prefix web install
	npm --prefix web run build
	rm -rf docs/assets
	cp -R web/dist/. docs/

report:
	$(PYTHON) scripts/build_report.py --data-dir $(PROCESSED_DIR) --figures-dir figures --output report/mathlib-network-report.pdf

video:
	$(PYTHON) scripts/build_video.py --figures-dir figures --output outputs/mathlib-network-demo.mp4

test:
	$(PYTHON) -m unittest discover -s tests

clean:
	rm -rf data/processed/* figures/* outputs/* report/* docs/index.html docs/graph.json docs/assets web/dist
