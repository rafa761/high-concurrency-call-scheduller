# Outbound Call Scheduler — Design Spec

**Date:** 2026-06-21
**Status:** Approved (design), pending implementation plan
**Source:** `docs/diagrams/outbound-scheduller-2026-06-16-1.excalidraw`

## Purpose

A portfolio + learning build of an outbound voice-AI **call orchestration
platform**, run entirely locally on LocalStack. The goal is **architecture
fidelity at small scale**: faithfully reproduce the patterns and topology of a
system spec'd for 1M calls/day and 10K concurrent calls — queues, fan-out,
failure isolation, idempotency, concurrency caps — using thousands of fake
contacts rather than pretending a laptop can serve production load.

The build is structured as a sequence of self-contained **lessons**. Each
lesson ends with something runnable and observable, tests, and a written
takeaway.

## Original problem (from the diagram)

Ingest campaign CSV uploads (up to 5M contacts: phone, metadata, local
timezone) and execute outbound voice-AI calls against them via a third-party
telephony provider. Each call yields a transcript + structured outcome
(promise-to-pay, callback requested, voicemail, etc.) that must be delivered
back to the client's CRM via webhook.

**Functional requirements:** accept ≤5M-contact uploads; schedule/dispatch
respecting per-contact 8am–9pm local calling windows; retry with backoff up to
3 attempts; enforce per-campaign concurrency caps; integrate a telephony
provider; capture outcomes + transcripts; deliver outcomes to CRM via webhook.

**Non-functional requirements:** 1M calls/day, peak 10K concurrent; no single
component bottlenecks throughput; CRM delivery within 60s of call completion;
at-least-once outcome delivery; per-call failure isolation; AWS; ~3x MoM growth.

## Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Build goal | Architecture fidelity at small scale | Portfolio/learning; laptop cannot serve real load |
| Language | Python 3.13 (FastAPI, boto3, pydantic) | Matches existing `pyproject.toml` |
| Ingestion trigger | **Lambda** (S3 event) | Sparse/bursty event → serverless fits; teaches *when* to use it |
| High-throughput stages | Long-running **worker containers** | Sustained concurrency → Lambda is wrong tool here |
| Resource provisioning | **Terraform via `tflocal`** | Real IaC; same `.tf` runs on real AWS by dropping the wrapper |
| External systems | **Chaos-configurable mock** provider + CRM | Makes retries/backoff/DLQ/idempotency visibly work |
| Operational store | PostgreSQL container | Standard; not LocalStack RDS |
| Outcome handling | Merge diagram's "Webhook API" + "Call State Service" into one `outcome-service` | Keep container count sane; internally modular (can split later) |

## Architecture

Queue-decoupled fan-out pipeline. Every stage hands off through a durable
boundary (SQS or Postgres), never a direct synchronous call — this is what
delivers failure isolation, independent scaling, and backpressure.

```
Client → Campaign API → S3 (CSV)
                          │ (S3 ObjectCreated event)
                          ▼
                    Lambda: Ingestion ──► Postgres (contacts + call_tasks)
                                                │
                          Scheduler (worker) ◄──┘  picks eligible tasks
                                │  (reserves concurrency)
                                ▼
                          SQS: dispatch ──► Dispatch workers ──► Mock Provider
                                                                      │ (async webhook)
                                                                      ▼
                          Outcome service ◄── Provider Webhook (validate+dedupe)
                                │  transcript→S3, persist outcome, release concurrency
                                ▼
                          SQS: outcome ──► CRM workers ──► Mock CRM
                                                │ (retry/backoff)
                                                ▼
                                          SQS: crm-dlq (exhausted)
```

## Repository layout

```
src/
  common/              shared lib: config, db, sqs/s3 helpers, models
  campaign-api/        FastAPI — create campaign, presigned upload URL, stats
  ingestion/           Lambda handler — S3 event → parse/validate → Postgres
  scheduler/           worker — eligibility + concurrency reservation → SQS
  dispatch-worker/     worker — SQS → provider adapter
  outcome-service/     FastAPI — provider webhook receiver + call-state/outcome
  crm-worker/          worker — SQS outcome → CRM with retry/backoff/DLQ
  mock-provider/       FastAPI — chaos-configurable telephony simulator
  mock-crm/            FastAPI — chaos-configurable CRM receiver
infra/
  terraform/           *.tf — S3 buckets, SQS queues + DLQs, Lambda wiring (tflocal)
docker-compose.yml     orchestrates: localstack, postgres, all services, terraform-init
```

Each service is its own Dockerfile/image. `common` is a shared Python package
installed into each image to avoid duplicating DB and AWS glue.

## Data model (PostgreSQL)

- **campaigns** — id, name, status, s3_key, created_at
- **campaign_concurrency** — campaign_id, active_count, max_concurrency
  *(separate table for clean atomic updates)*
- **contacts** — id, campaign_id, phone, timezone, metadata (jsonb)
- **call_tasks** — id, campaign_id, contact_id, status, attempts,
  next_eligible_at, last_attempt_at *(work-item state machine)*
- **call_attempts** — id, call_task_id, attempt_number, provider_call_id,
  status, outcome, transcript_s3_key
- **outcomes** — id, call_task_id, outcome_type, payload (jsonb)
- **provider_events** — provider_event_id (unique) → webhook dedupe / idempotency
- **crm_delivery_attempts** — id, outcome_id, attempt_number, status,
  response_code, idempotency_key

`call_task.status` lifecycle: `pending → eligible → dispatching → calling →
completed | failed → (retry: eligible) | exhausted`.

### Crown-jewel patterns (dwell on these)

- **`SELECT … FOR UPDATE SKIP LOCKED`** — many workers claim tasks concurrently
  without ever double-processing one.
- **`UPDATE campaign_concurrency SET active_count = active_count + 1
  WHERE active_count < max_concurrency RETURNING …`** — atomic concurrency cap
  with no race; released when a call finishes (success or failure).
- **Calling window** — contact-local hour must be in `[8, 21)`; otherwise
  `next_eligible_at` is set to the next window open.
- **Retry/backoff** — on failure `attempts += 1`, `next_eligible_at = now +
  backoff(attempts)`, until `attempts == 3` → `exhausted`.

## AWS resources (LocalStack, via Terraform/tflocal)

- **S3**: `campaign-uploads` (CSVs), `call-artifacts` (transcripts)
- **SQS**: `dispatch`, `outcome-delivery`, `crm-dlq` (redrive target)
- **Lambda**: `ingestion`, triggered by S3 `ObjectCreated` on `campaign-uploads`

## Mock fidelity (chaos-configurable)

Both mocks are env-var configurable for: latency, random failure rate, and
duplicate/late webhook delivery. This is what makes resilience demonstrable —
dial failure up and watch retries, backoff, idempotency, and the DLQ work.

- **mock-provider**: accepts "place call", responds async via webhook to
  `outcome-service` after a configurable delay, with configurable
  success/failure/duplicate/late behaviour.
- **mock-crm**: receives CRM webhooks, configurable to fail/slow, honours the
  idempotency key to detect duplicate deliveries.

## Lesson-by-lesson build plan

Each lesson ends with something runnable + observable, tests (TDD), and a
written takeaway.

| # | Lesson | Build | Learn |
|---|--------|-------|-------|
| 0 | Foundations | compose skeleton: LocalStack + Postgres + Terraform provisioning + `common` lib | how LocalStack, IaC, and compose fit together |
| 1 | Upload API + S3 | `campaign-api`: create campaign → presigned PUT URL; upload CSV to S3 | presigned URLs, why the API never touches the bytes |
| 2 | Ingestion Lambda | S3 event → Lambda → chunked parse/validate → Postgres | event-driven serverless, chunked big-file processing, idempotent ingest |
| 3 | Data model + task lifecycle | migrations + `call_task` state machine | modeling durable work items, DB-as-queue tradeoffs |
| 4 | Eligibility Scheduler | claiming, 8am–9pm windows, atomic concurrency reservation, enqueue | SKIP LOCKED, atomic counters, backpressure |
| 5 | Dispatch + mock provider | SQS consumer + provider adapter; chaos mock provider w/ async callback | SQS visibility timeout, adapter pattern, async call model |
| 6 | Provider webhook + outcome | validate signature, dedupe, transcript→S3, persist, release concurrency, publish | idempotent webhooks, releasing capacity, signature checks |
| 7 | CRM delivery + DLQ | CRM worker: idempotency key, retry/backoff, attempt log, DLQ on exhaustion | at-least-once, idempotency, DLQ + redrive |
| 8 | Chaos & failure isolation | turn up mock failure rates; prove one bad call never blocks the campaign | resilience under load, observing recovery |
| 9 | Monitoring | stats view: queue depths, active-vs-cap, DLQ depth, ingest progress, CRM lag | the operational metrics that matter |

## Testing & verification

- Per-service `pytest` (unit + FastAPI via `httpx`); `asyncio_mode = auto`
  already configured.
- Per-lesson integration checks hitting the running stack through
  `docker-compose`.
- Every lesson has an explicit "run this, see this" so learning is grounded in
  observed behaviour.

## Out of scope

- Real telephony / real CRM integration.
- Real high-throughput load (10K concurrent) — patterns only, at small scale.
- Authentication/authorization, multi-tenancy, production hardening.
- Real Claude-generated transcripts (deferred; possible later optional lesson).
```

## Open items intentionally deferred to the plan

- Exact backoff curve and visibility-timeout values.
- Migration tooling choice (e.g. Alembic vs plain SQL).
- Whether `common` is `pip install -e` per image or copied in at build.
