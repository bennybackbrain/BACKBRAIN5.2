# Simple helper Makefile
.PHONY: help dev test coverage smoke summarizer build docker-run compose logs lint clean precommit spec-check spec-hash

help:
	@echo "Targets: dev test coverage smoke summarizer build docker-run compose logs lint clean"

dev:
	./run_dev.sh

test:
	pytest -q

coverage:
	pytest --cov=app --cov-report=term-missing

smoke:
	bash scripts/smoke_test.sh || true

summarizer:
	bash scripts/summarizer_smoke.sh || true

auto-summary-errorpath:
	bash scripts/auto_summary_errorpath.sh || true

build:
	docker build -t backbrain:dev .

docker-run:
	docker run --rm -p 8000:8000 backbrain:dev

compose:
	docker compose up --build

logs:
	docker compose logs -f api

lint:
	python -m py_compile $(git ls-files '*.py')

precommit:
	python -m pip install pre-commit ruff >/dev/null 2>&1 || true
	pre-commit install

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ backbrain.db

spec-check:
	pytest -q app/tests/test_spec_drift.py

actions-spec-hash:
	python3 scripts/spec_hash.py actions/openapi-actions-private.yaml > openapi-actions-private.sha256

actions-spec-check:
	pytest -q app/tests/test_actions_private_spec_drift.py

spec-hash:
	python scripts/spec_hash.py
