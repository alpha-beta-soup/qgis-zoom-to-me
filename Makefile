PLUGIN = zoom_to_me
QGIS_PLUGIN_DIR ?= $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins

QGIS_ENV ?= $(HOME)/.conda/envs/qgis-env

.PHONY: test test-qgis deploy zip clean

# Pure-Python tests; the QGIS-dependent module is skipped if qgis is not importable.
test:
	python3 -m unittest discover -s tests -v

# All tests, inside the conda QGIS environment, with an offscreen Qt platform.
test-qgis:
	QT_QPA_PLATFORM=offscreen PYTHONPATH="$(QGIS_ENV)/share/qgis/python" \
		"$(QGIS_ENV)/bin/python" -m unittest discover -s tests -v

deploy:
	mkdir -p "$(QGIS_PLUGIN_DIR)/$(PLUGIN)"
	rsync -a --delete --exclude '__pycache__' $(PLUGIN)/ "$(QGIS_PLUGIN_DIR)/$(PLUGIN)/"
	@echo "Deployed to $(QGIS_PLUGIN_DIR)/$(PLUGIN)"

zip: clean
	mkdir -p dist
	cd . && zip -r dist/$(PLUGIN).zip $(PLUGIN) -x '*/__pycache__/*' '*.pyc'

clean:
	rm -rf dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
