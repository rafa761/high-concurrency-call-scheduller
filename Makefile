# Outbound Call Scheduler — developer commands.
# Run `make` or `make help` to see everything available.
#
# Convention: top-level lifecycle commands are unprefixed (the daily drivers);
# tool-specific commands are grouped by prefix:
#   tf-*      terraform / infrastructure
#   db-*      alembic migrations + postgres
#   lambda-*  the ingestion lambda
#   aws-*     localstack resource inspection

SHELL := /bin/bash

COMPOSE  := docker compose
# awslocal ships inside the LocalStack container; -T disables TTY for clean piping.
AWSLOCAL := $(COMPOSE) exec -T localstack awslocal
# One-shot infra job that runs Terraform through the tflocal wrapper.
TFLOCAL  := $(COMPOSE) run --rm infra

.DEFAULT_GOAL := help

# Sequential command wrappers — never run recipes in parallel, so multi-section
# output (e.g. `make aws-info`) always prints in order.
.NOTPARALLEL:

# ----------------------------------------------------------------------------
# Stack lifecycle
# ----------------------------------------------------------------------------

.PHONY: up
up: lambda-build ## Build and launch the entire stack (all compose services)
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop all containers (keeps volumes/data)
	$(COMPOSE) down

.PHONY: clean
clean: ## Stop all containers AND delete volumes (full reset)
	$(COMPOSE) down -v

.PHONY: ps
ps: ## Show status of all containers
	$(COMPOSE) ps

.PHONY: logs
logs: ## Follow logs from all containers (Ctrl-C to stop)
	$(COMPOSE) logs -f

.PHONY: test
test: ## Run the Python test suite
	uv run pytest -q

.PHONY: demo
demo: ## End-to-end smoke: create a campaign and upload the sample CSV
	@bash scripts/demo.sh

.PHONY: chaos-on
chaos-on: ## Crank failure rates on the provider and CRM mocks
	@curl -s -X POST localhost:9001/config -H 'content-type: application/json' \
		-d '{"failure_rate":0.3,"call_failure_rate":0.3,"duplicate_rate":0.3}' >/dev/null && echo "provider chaos ON"
	@curl -s -X POST localhost:9003/config -H 'content-type: application/json' \
		-d '{"failure_rate":0.3}' >/dev/null && echo "crm chaos ON"

.PHONY: chaos-off
chaos-off: ## Reset all mocks to healthy
	@curl -s -X POST localhost:9001/config -H 'content-type: application/json' \
		-d '{"failure_rate":0,"call_failure_rate":0,"duplicate_rate":0,"drop_callback_rate":0}' >/dev/null && echo "provider chaos OFF"
	@curl -s -X POST localhost:9003/config -H 'content-type: application/json' \
		-d '{"failure_rate":0}' >/dev/null && echo "crm chaos OFF"

# ----------------------------------------------------------------------------
# tf-*  Terraform / infrastructure (via tflocal)
# ----------------------------------------------------------------------------

.PHONY: tf-apply
tf-apply: ## Provision AWS resources in LocalStack
	$(TFLOCAL) sh -c "tflocal init -input=false && tflocal apply -auto-approve -input=false"

.PHONY: tf-plan
tf-plan: ## Preview infrastructure changes without applying
	$(TFLOCAL) sh -c "tflocal init -input=false && tflocal plan"

.PHONY: tf-output
tf-output: ## Show Terraform outputs (bucket names, queue URLs)
	$(TFLOCAL) sh -c "tflocal output"

# ----------------------------------------------------------------------------
# db-*  Database: alembic migrations + postgres
# ----------------------------------------------------------------------------

.PHONY: db-migrate
db-migrate: ## Apply database migrations (alembic upgrade head)
	$(COMPOSE) run --rm migrate

.PHONY: db-revision
db-revision: ## Autogenerate a migration: make db-revision m="message"
	uv run alembic revision --autogenerate -m "$(m)"

.PHONY: db-shell
db-shell: ## Open a psql shell on Postgres
	$(COMPOSE) exec postgres psql -U scheduler

# ----------------------------------------------------------------------------
# lambda-*  Ingestion lambda
# ----------------------------------------------------------------------------

.PHONY: lambda-build
lambda-build: ## Build the ingestion Lambda deployment zip
	./scripts/build_lambda.sh

.PHONY: lambda-logs
lambda-logs: ## Tail the ingestion Lambda logs (CloudWatch, not docker)
	$(AWSLOCAL) logs tail /aws/lambda/ingestion --format short 2>/dev/null || echo "no logs yet"

# ----------------------------------------------------------------------------
# aws-*  LocalStack resource inspection
# ----------------------------------------------------------------------------

.PHONY: aws-info
aws-info: ## Show provisioned S3 buckets, SQS queues, and DLQ redrive
	@printf '── S3 buckets ─────────────────────────────\n%s\n' "$$($(AWSLOCAL) s3 ls)"
	@printf '── SQS queues ─────────────────────────────\n%s\n' "$$($(AWSLOCAL) sqs list-queues --output text)"
	@printf '── DLQ redrive (outcome-delivery) ─────────\n%s\n' \
		"$$($(AWSLOCAL) sqs get-queue-attributes \
			--queue-url "$$($(AWSLOCAL) sqs get-queue-url --queue-name outcome-delivery --query QueueUrl --output text)" \
			--attribute-names RedrivePolicy --output text)"

# ----------------------------------------------------------------------------

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} \
		/^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
