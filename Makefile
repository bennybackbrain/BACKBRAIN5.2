# Simple helper Makefile
.PHONY: help dev test coverage smoke summarizer build docker-run compose logs lint clean precommit

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
