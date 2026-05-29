PYTHON ?= python3
DATA_SOURCE ?= mathlib-source
RAW_INPUT ?=
PROCESSED_DIR ?= data/processed
HF_ROW_LIMIT ?= 0
MATHLIB_SOURCE_DIR ?= data/raw/mathlib4
MATHLIB_REF ?= master
MATHLIB_FORCE ?= 0
MATHLIB_FORCE_FLAG := $(if $(filter 1 true yes,$(MATHLIB_FORCE)),--force,)

.PHONY: all data web test clean web-vite mathlib-source

all: data web

data:
	HF_ROW_LIMIT=$(HF_ROW_LIMIT) $(PYTHON) scripts/build_data.py --source $(DATA_SOURCE) --input "$(RAW_INPUT)" --output-dir $(PROCESSED_DIR)

mathlib-source:
	$(PYTHON) scripts/fetch_mathlib_source.py --output-dir $(MATHLIB_SOURCE_DIR) --ref $(MATHLIB_REF) $(MATHLIB_FORCE_FLAG)

web:
	$(PYTHON) scripts/build_static_site.py --data-dir $(PROCESSED_DIR) --docs-dir docs

web-vite:
	npm --prefix web install
	npm --prefix web run build
	rm -rf docs/assets
	cp -R web/dist/. docs/

test:
	DATA_SOURCE=sample $(PYTHON) -m unittest discover -s tests

clean:
	rm -rf data/processed/* docs/index.html docs/graph.json docs/assets web/dist
