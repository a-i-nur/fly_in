VENV := .venv
PYTHON := $(VENV)/bin/python
PATH := $(CURDIR)/$(VENV)/bin:$(PATH)

.PHONY: install run visualize debug clean lint

install: $(PYTHON)
	$(PYTHON) -m pip install -r requirements.txt

$(PYTHON):
	python3 -m venv $(VENV)

run:
	$(PYTHON) main.py $(if $(MAP),"$(MAP)")

visualize:
	$(PYTHON) main.py $(if $(MAP),"$(MAP)") --visualize

debug:
	$(PYTHON) -m pdb main.py $(if $(MAP),"$(MAP)")

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .mypy_cache

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs