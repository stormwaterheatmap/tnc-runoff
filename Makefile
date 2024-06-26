MAKEFLAGS += --silent
.PHONY: clean clean-test clean-pyc clean-build test coverage
.DEFAULT_GOAL := help
define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT
BROWSER := python -c "$$BROWSER_PYSCRIPT"

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	rm -fr wheelhouse/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## remove Python file artifacts
	find . -wholename '**/__pycache__/*.pyc' -exec rm -f {} +
	find . -wholename '**/__pycache__/*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

clean-numba: ## remove Python file artifacts
	find . -wholename '**/__pycache__/*.nbc' -exec rm -f {} +
	find . -wholename '**/__pycache__/*.nbi' -exec rm -f {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .coverage*
	rm -fr htmlcov/
	rm -fr .pytest_cache

test: clean
	pytest

coverage: clean
	pytest --cov

lint: clean
	ruff check . --fix
	ruff format .
	pre-commit run --all-files
