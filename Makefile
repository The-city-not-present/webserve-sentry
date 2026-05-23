.PHONY: build init test run



VENV=.venv
PYTHON=$(VENV)/bin/python
PIP=$(PYTHON) -m pip
PYTEST=$(PYTHON) -m pytest
define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT
BROWSER := python -c "$$BROWSER_PYSCRIPT"



build:
	./build-scripts/build.sh



init:
	./build-scripts/init.sh



test:
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-html
	$(PYTEST) --ignore=src/endpoints/lib/htmltmpl/src-make/lib/pinliner



test-html:
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-html
	mkdir -p test-results
	$(PYTEST) --html=test-results/report.html --self-contained-html --ignore=src/endpoints/lib/htmltmpl/src-make/lib/pinliner
	$(BROWSER) test-results/report.html



test-cov:
	$(PYTEST) --cov



run:
	./build-scripts/run.sh
