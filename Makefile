# Outbound Call Scheduler — developer commands.
# Run `make` or `make help` to see everything available.

# Use bash for recipes (consistent across shells; the user's login shell is fish).
SHELL := /bin/bash

COMPOSE   := docker compose
# awslocal ships inside the LocalStack container; -T disables TTY for clean piping.
AWSLOCAL  := $(COMPOSE) exec -T localstack awslocal
# One-shot infra job that runs Terraform through the tflocal wrapper.
TFLOCAL   := $(COMPOSE) run --rm infra

.DEFAULT_GOAL := help

# These are sequential command wrappers — never run recipes in parallel,
# so multi-section output (e.g. `make info`) always prints in order.
.NOTPARALLEL:

# ----------------------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------------------

.PHONY: bootstrap
bootstrap: up apply info ## Zero-to-ready: start stack, provision infra, show resources

.PHONY: up
up: ## Start LocalStack + Postgres and wait until both are healthy
	$(COMPOSE) up -d --wait localstack postgres

.PHONY: down
down: ## Stop containers (keeps volumes/data)
	$(COMPOSE) down

.PHONY: clean
clean: ## Stop containers AND delete volumes (full reset)
	$(COMPOSE) down -v

.PHONY: ps
ps: ## Show container status
	$(COMPOSE) ps

.PHONY: logs
logs: ## Tail LocalStack logs (Ctrl-C to stop)
	$(COMPOSE) logs -f localstack

# ----------------------------------------------------------------------------
# Infrastructure (Terraform via tflocal)
# ----------------------------------------------------------------------------

.PHONY: apply
apply: ## Provision all AWS resources in LocalStack (terraform apply)
	$(TFLOCAL) sh -c "tflocal init -input=false && tflocal apply -auto-approve -input=false"

.PHONY: plan
plan: ## Preview infrastructure changes without applying
	$(TFLOCAL) sh -c "tflocal init -input=false && tflocal plan"

.PHONY: destroy
destroy: ## Tear down all Terraform-managed AWS resources
	$(TFLOCAL) sh -c "tflocal destroy -auto-approve -input=false"

.PHONY: outputs
outputs: ## Show Terraform outputs (bucket names, queue URLs)
	$(TFLOCAL) sh -c "tflocal output"

.PHONY: validate
validate: ## Validate the Terraform configuration (no LocalStack needed)
	$(TFLOCAL) sh -c "terraform init -backend=false -input=false >/dev/null && terraform validate"

# ----------------------------------------------------------------------------
# Application services (campaign-api + migrations)
# ----------------------------------------------------------------------------

.PHONY: build
build: ## Build all service images
	$(COMPOSE) build

.PHONY: start
start: up apply ## Full environment up: stack healthy + infra + migrate + API
	$(COMPOSE) up -d --build migrate campaign-api

.PHONY: migrate
migrate: ## Apply database migrations (alembic upgrade head)
	$(COMPOSE) run --rm migrate

.PHONY: revision
revision: ## Autogenerate a migration: make revision m="message" (needs postgres up)
	uv run alembic revision --autogenerate -m "$(m)"

.PHONY: api-logs
api-logs: ## Tail campaign-api logs (Ctrl-C to stop)
	$(COMPOSE) logs -f campaign-api

.PHONY: demo
demo: ## End-to-end smoke: create a campaign and upload the sample CSV
	@bash scripts/demo.sh

.PHONY: build-lambda
build-lambda: ## Build the ingestion Lambda deployment zip
	./scripts/build_lambda.sh

.PHONY: lambda-logs
lambda-logs: ## Show recent ingestion Lambda logs
	$(AWSLOCAL) logs tail /aws/lambda/ingestion --format short 2>/dev/null || echo "no logs yet"

# ----------------------------------------------------------------------------
# Inspect what actually exists in LocalStack
# ----------------------------------------------------------------------------

.PHONY: info
info: buckets queues redrive ## Show all provisioned resources at a glance

.PHONY: buckets
buckets: ## List S3 buckets
	@printf '── S3 buckets ─────────────────────────────\n%s\n' "$$($(AWSLOCAL) s3 ls)"

.PHONY: queues
queues: ## List SQS queues
	@printf '── SQS queues ─────────────────────────────\n%s\n' "$$($(AWSLOCAL) sqs list-queues --output text)"

.PHONY: redrive
redrive: ## Show the outcome-delivery -> crm-dlq redrive policy
	@printf '── DLQ redrive policy (outcome-delivery) ──\n%s\n' \
		"$$($(AWSLOCAL) sqs get-queue-attributes \
			--queue-url "$$($(AWSLOCAL) sqs get-queue-url --queue-name outcome-delivery --query QueueUrl --output text)" \
			--attribute-names RedrivePolicy --output text)"

.PHONY: health
health: ## Show LocalStack service health
	@$(AWSLOCAL) sqs list-queues >/dev/null 2>&1 && echo "LocalStack: healthy" || echo "LocalStack: NOT ready"

.PHONY: psql
psql: ## Open a psql shell on the Postgres container
	$(COMPOSE) exec postgres psql -U scheduler

# ----------------------------------------------------------------------------
# Development
# ----------------------------------------------------------------------------

.PHONY: test
test: ## Run the Python test suite
	uv run pytest -q

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} \
		/^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2} \
		/^# -+$$/ {next}' $(MAKEFILE_LIST)
