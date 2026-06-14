.PHONY: install test run docker deploy clean lint fmt check

# ------------------------------------------------------------------------------
# Development helpers for StockScope
# ------------------------------------------------------------------------------

VENV          := .venv
PYTHON        := $(VENV)/bin/python
PIP           := $(VENV)/bin/pip
PYTEST        := $(VENV)/bin/pytest
IMAGE_NAME    := stockscope
CONTAINER_NAME := stock-analysis
PORT          := 5000

# ------------------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------------------

$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

## Install Python dependencies into local virtual environment
install: $(VENV)
	$(PIP) install -r requirements.txt

# ------------------------------------------------------------------------------
# Quality gates
# ------------------------------------------------------------------------------

## Run all tests with verbose output and shortened tracebacks
test:
	$(PYTEST) -v --tb=short

## Run tests + lint checks (future: add ruff / mypy here)
check: test

# ------------------------------------------------------------------------------
# Local server
# ------------------------------------------------------------------------------

## Start Flask development server
run:
	$(PYTHON) app.py

# ------------------------------------------------------------------------------
# Docker
# ------------------------------------------------------------------------------

## Build the production Docker image
docker:
	docker build -t $(IMAGE_NAME):latest .

## Stop any running container and start a fresh one
docker-run: docker
	-docker rm -f $(CONTAINER_NAME) 2>/dev/null || true
	docker run -d --name $(CONTAINER_NAME) --restart unless-stopped \
		-p $(PORT):$(PORT) -v stock-charts:/app/charts \
		$(IMAGE_NAME):latest

## Full deploy sequence (build → replace container)
deploy: docker docker-run
	@echo "✅ StockScope deployed on http://localhost:$(PORT)"

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------

## Remove build artifacts, cache, and virtual environment
clean:
	rm -rf $(VENV) __pycache__ .pytest_cache *.pyc .coverage htmlcov
	rm -rf charts/ *.egg-info build/ dist/

# ------------------------------------------------------------------------------
# GitHub Actions (local simulation)
# ------------------------------------------------------------------------------

## Simulate the CI pipeline locally
ci: install check docker
	@echo "🎉 CI pipeline passed locally"

# ------------------------------------------------------------------------------
# Help
# ------------------------------------------------------------------------------

## Show this help message
help:
	@echo "StockScope — Make targets"
	@echo ""
	@awk 'BEGIN{FS=":.*?## "}/^\S+:[^=].*##/{print "  make " $$1 "  →   " $$2}' $(MAKEFILE_LIST)
