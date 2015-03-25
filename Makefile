# Makefile to help automate tasks
WD := $(shell pwd)
PY := bin/python
PIP := bin/pip


# #######
# INSTALL
# #######
.PHONY: all
all: venv develop

venv: bin/python
bin/python:
	virtualenv .

.PHONY: clean_venv
clean_venv:
	rm -rf bin include lib local man

develop: lib/python*/site-packages/wanish.egg-link
lib/python*/site-packages/wanish.egg-link:
	$(PY) setup.py develop


# ###########
# Development
# ###########
.PHONY: clean_all
clean_all: clean_venv


# ###########
# Deploy
# ###########
.PHONY: dist
dist:
	$(PY) setup.py sdist

.PHONY: upload
upload:
	$(PY) setup.py sdist upload

.PHONY: version_update
version_update:
	$(EDITOR) setup.py
