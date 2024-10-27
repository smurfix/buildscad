#!/usr/bin/make -f

PACKAGE = buildscad
PYPI ?= $(PACKAGE)

PATH := /usr/share/sphinx/scripts/python3:${PATH}
export PYTHONPATH := $(PYTHONPATH)$(if $(PYTHONPATH),:)$(shell pwd)

PYTHON ?= python3
PYTEST ?= pytest
PYTEST_OPTIONS ?= -x
TESTS ?= tests/
CODE ?= src/$(PACKAGE)

BUILD_DIR ?= build
INPUT_DIR ?= docs/source

RQ := grep -qs tool.ruff pyproject.toml

# Sphinx options (are passed to build_docs, which passes them to sphinx-build)
#   -W       : turn warning into errors
#   -a       : write all files
#   -b html  : use html builder
#   -i [pat] : ignore pattern

SPHINXOPTS ?= -a -W -b html
AUTOSPHINXOPTS := -i *~ -i *.sw* -i Makefile*

SPHINXBUILDDIR ?= $(BUILD_DIR)/sphinx/html
ALLSPHINXOPTS ?= -d $(BUILD_DIR)/sphinx/doctrees $(SPHINXOPTS) docs

ifneq ($(wildcard setup.py),)
	SETUP := setup.py
else
	SETUP :=
endif

it: untagged test push tag format deb pypi
itt: untagged test push ttag format deb pypi

deb: tagged
	merge-to-deb

tag:
	test $$(git ls-files -m | wc -l) = 0
	git nt
ttag:
	test $$(git ls-files -m | wc -l) = 0
	git ntt

doc:
	sphinx-build -a $(INPUT_DIR) $(BUILD_DIR)

livehtml: docs
	sphinx-autobuild $(AUTOSPHINXOPTS) $(ALLSPHINXOPTS) $(SPHINXBUILDDIR)

update:
	pip install -r ci/test-requirements.txt

cov:
	$(PYTEST) $(TESTS) --cov=$(CODE) --cov-report=term-missing

test: statictest pytest
statictest:
	${RQ} || black --check $(CODE) $(TESTS) $(SETUP)
	${RQ} || python3 -misort --check $(CODE) $(TESTS) $(SETUP)
	${RQ} || flake8p $(CODE) $(TESTS) $(SETUP)
	${RQ} || pylint $(CODE) $(TESTS) $(SETUP)
	${RQ} && ruff format $(CODE) $(TESTS) $(SETUP)
	${RQ} && ruff check $(CODE) $(TESTS) $(SETUP)

pytest:
	$(PYTEST) $(PYTEST_OPTIONS) $(TESTS)

format:
	${RQ} || black $(CODE) $(TESTS) $(SETUP)
	${RQ} || python3 -misort $(CODE) $(TESTS) $(SETUP)
	${RQ} && ruff format $(CODE) $(TESTS) $(SETUP)
	${RQ} && ruff check --fix $(CODE) $(TESTS) $(SETUP)

precommit: format test

tagged:
	git describe --tags --exact-match
	test $$(git ls-files -m | wc -l) = 0

untagged:
	if git describe --tags --exact-match ; then exit 1; else exit 0; fi

pypi:	tagged
	if test -f dist/${PYPI}-$(shell git describe --tags --exact-match).tar.gz ; then \
		echo "Source package exists."; \
	elif test -f setup.py ; then \
		python3 setup.py sdist bdist_wheel ; \
	else \
		python3 -mbuild -snw ; \
	fi
	twine upload \
		dist/${PYPI}-$(shell git describe --tags --exact-match).tar.gz \
		dist/$(subst -,_,${PYPI})-$(shell git describe --tags --exact-match)-py3-none-any.whl

upload: pypi
	git push --tags

push:
	git push-all

.PHONY: all tagged pypi upload precommit format test cov update doc livehtml statictest pytest it deb tag untagged push ttag itt
	@echo "Please fix 'python3 -mmoat src path'."
	@exit 1
