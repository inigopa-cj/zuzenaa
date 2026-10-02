SHELL := /bin/bash
COMPOSE := docker compose
COMPOSE_DEV := docker compose -f docker-compose.dev.yml

.DEFAULT_GOAL := help

.PHONY: help
help: ## Muestra esta ayuda
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

## --- Arranque (producción/local) ---

.PHONY: up
up: ## Arranca todo (db + backend + web) en segundo plano
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Para todo
	$(COMPOSE) down

.PHONY: build
build: ## Construye las imágenes
	$(COMPOSE) build

.PHONY: logs
logs: ## Logs en vivo
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Estado de los servicios
	$(COMPOSE) ps

.PHONY: clean
clean: ## Para y borra volúmenes (¡se pierden los datos!)
	$(COMPOSE) down -v
	$(COMPOSE_DEV) down -v

## --- Desarrollo (hot reload) ---

.PHONY: dev
dev: ## Arranca en modo desarrollo (backend y web con recarga)
	$(COMPOSE_DEV) up --build

.PHONY: dev-down
dev-down: ## Para el modo desarrollo
	$(COMPOSE_DEV) down

## --- Calidad ---

.PHONY: test
test: ## Backend: ruff + mypy + pytest
	cd backend && uv run ruff check . && uv run mypy && uv run pytest

.PHONY: test-web
test-web: ## Web: lint + build
	cd web && npm run lint && npm run build

.PHONY: test-all
test-all: test test-web ## Backend + web
