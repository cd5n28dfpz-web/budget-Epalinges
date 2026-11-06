# Pipeline : PDF -> extraction -> fusion -> site -> tests
# Prérequis : Python 3.9+ ; pour repartir des PDF : pdftotext (poppler-utils)

PY ?= python3

all: extraction rebuild

extraction:
	$(PY) pipeline/extract.py
	$(PY) pipeline/dette.py
	$(PY) pipeline/projet2027.py

fusion:
	$(PY) pipeline/merge.py

site:
	$(PY) pipeline/build_site.py

test:
	$(PY) -m unittest discover tests

# Reconstruit données et site sans les PDF (extractions déjà dans sources/extraits)
rebuild: fusion site test

.PHONY: all extraction fusion site test rebuild
