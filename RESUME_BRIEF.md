# Resume Brief: Retail API on Google Cloud Platform

Purpose of this file: give an LLM everything it needs to add or rewrite resume lines for this project. The project owner is Roshan K C. The GCP migration was built and tested on 2026-10-12 and 2026-10-13 (this file was last updated 2026-10-13). Read the rules first, then the facts (sections 4 and 7), then the full project details (section 10), then the templates and options (sections 6 and 11).

## 0. Rules for the LLM editing the resume (read first)

1. Never invent a number, service, or outcome. Every number must come from section 4 (verified) or from the table in section 7 that the owner fills in after finishing. If a value is still a placeholder like `[RPS]`, leave the placeholder in the output and tell the owner it needs filling.
2. Do not use em dashes anywhere in the output. Use commas, colons, hyphens or parentheses.
3. Do not attribute the GCP work to the iTuring.ai internship unless the owner confirms the internship used GCP. As far as this brief knows, the GCP migration is a personal project that extends the internship prototype. Default to a separate project entry (option A in section 6) or ask the owner.
4. Keep claims defensible in an interview. Each bullet must be something the owner can explain in depth (section 8 lists the talking points).
5. Match the existing resume style: past-tense action verb first, tech named explicitly, one metric where possible, 1 to 2 lines per bullet, no first person.
6. The resume is 2 pages. Page 1 is full. Page 2 has about half a page free, so a new project entry fits on page 2 (4 bullets maximum).
7. Do not change unrelated sections (education, research, other projects) unless asked.
8. Do not state "10,000+ concurrent requests" or "270+ req/sec" for the GCP version. See section 5 for why those two existing claims need care.

## 1. One-paragraph project summary

A FastAPI + PostgreSQL retail store API (customer storefront, admin dashboard with JWT auth, and a concurrency-safe purchase endpoint) originally built as a proof of concept during the iTuring.ai internship. It ran on Docker and Kubernetes (Minikube, 3 replicas, Nginx Ingress) with a self-hosted GitHub Actions pipeline gated on Apache JMeter load tests. The owner migrated it to Google Cloud: Cloud Run for the API, Cloud SQL (PostgreSQL 15) for the database, Artifact Registry and Cloud Build for images, Secret Manager for credentials, Workload Identity Federation for keyless GitHub Actions deploys, and Cloud Monitoring for dashboards and alerts. It was then load tested in the same region, deliberately broken once (connection pool exhaustion) to observe the failure and the alerting, and documented with a README, a results log and 28 console screenshots. The goal was a measured, documented, repeatable cloud deployment (a Minikube comparison was not measured).

## 2. Repositories

- New GCP repo (use this link on the resume after migration): https://github.com/RO-03/Retail-API-GCP (branch `gcp` holds the cloud work)
- Original repo (currently linked on the resume, under the iTuring.ai bullet): https://github.com/RO-03/Retail-API-stress-test
- GCP project ID: `retailgcp`, region `asia-south1` (Mumbai)

## 3. Technology inventory (only list a technology on the resume once its phase is complete)

Application:
- Python 3.11, FastAPI, Uvicorn (2 workers), SQLAlchemy, PostgreSQL 15, psycopg2, JWT (python-jose), bcrypt, Jinja2 templates, MVC layout (controllers, models, services, views)
- Pytest suite (20 tests, SQLite for unit tests)

Original infrastructure (already on the resume):
- Docker, Docker Compose, Kubernetes (Minikube), Nginx Ingress, 3 replicas, rolling updates (maxSurge 1, maxUnavailable 0), readiness and liveness probes on `/health`
- GitHub Actions on a self-hosted runner, Apache JMeter gate (error rate must be 0%, throughput floor 80 req/sec in CI)

GCP services (status in section 4):
- Cloud Run (service and Jobs), Cloud SQL for PostgreSQL, Artifact Registry, Cloud Build, Secret Manager, IAM service accounts with least privilege, Workload Identity Federation (GitHub OIDC), Cloud Monitoring (dashboard, uptime check, alert policies, log-based metric), Cloud Logging, Cloud Billing budgets

## 4. Status and verified facts

### Completed and verified (safe to claim now)

- GCP project created, billing linked, budget alerts set (monthly budget with alerts at 25%, 50%, 100%), gcloud CLI configured, 8 APIs enabled (Run, Artifact Registry, Cloud SQL Admin, Secret Manager, Cloud Build, Monitoring, Logging, IAM Credentials).
- Application made cloud-ready (committed on branch `gcp`):
  - Container reads `PORT` (Cloud Run requirement) and `WORKERS` from the environment.
  - Database layer supports the Cloud SQL Unix socket (`/cloudsql/<instance>`) and configurable connection pool size per worker.
  - JWT secret and admin password moved out of source code into environment variables (to be backed by Secret Manager). The app refuses to start in production without the secret.
  - Added a DB-free liveness endpoint `/livez`, keeping `/health` (checks the DB) for readiness.
  - Table creation moved out of app import time into a separate init script (`scripts/init_db.py`) to run as a Cloud Run Job. Reason: with two workers (and several instances) importing the app, concurrent `create_all` calls raced and one worker crashed with a duplicate-key error. This was reproduced locally.
  - Fixed a latent build bug: SQLAlchemy 2.1 maps a bare `postgresql://` URL to the psycopg v3 driver while the project installs psycopg2, so fresh Docker builds failed. Fixed by pinning the driver in the URL.
  - Added an `orders` table. Each purchase writes the stock decrement and the order row in a single transaction.
- Verified on real PostgreSQL 15 via Docker Compose: 40 concurrent purchase requests against an item with 15 in stock produced exactly 15 successes (HTTP 200) and 25 rejections (HTTP 409), final stock 0, exactly 15 order rows. No overselling, no lost writes. Deleting an item preserves its orders.
- Pytest: 20 tests passing.

### Also completed and verified on Google Cloud (as of 2026-10-13; full numbers and run settings are in `RESULTS.md` in the repo)

- Artifact Registry repo with a keep-last-5 cleanup policy; images built with Cloud Build and tagged with the git commit SHA, never `latest`.
- Runtime service account `retail-run-sa` with only Cloud SQL Client (project) and Secret Accessor on three individual secrets.
- Cloud SQL for PostgreSQL 15 (`db-f1-micro`; the instance has a public IP but no authorized networks, so the only access path is the Cloud SQL connector with IAM, which Cloud Run uses through the Unix socket; private IP was not set up, so do not claim "private" networking). Measured `max_connections` = 25, 22 usable.
- Three secrets in Secret Manager (database password, JWT key, admin password), created with random values; none stored in the repo.
- Cloud Run service (2 vCPU, 1 GiB, concurrency 40, max 3 instances, CPU boost, startup probe on `/health`, liveness probe on `/livez`), plus Cloud Run Jobs for schema init, admin creation, seeding and a DB report.
- Revision practice: no-traffic deploy on a tagged URL, 10% traffic split, promotion, rollback and roll forward.
- Load tests with Apache JMeter, from a laptop and from a Cloud Run Job in the same region (a JMeter image in `loadtest/`), plus a Python summarizer (`tests/summarize_results.py`).
- Cloud Monitoring as code in `monitoring/`: a dashboard (request rate by status, latency percentiles, instance count, Cloud SQL connections and CPU, 409 count), an uptime check on `/livez`, three alert policies (5xx, p95 latency, uptime), a log-based metric for HTTP 409, and an email notification channel. The 5xx alert was seen firing and recovering during a deliberate failure test.
- Keyless CI/CD in `.github/workflows/gcp-deploy.yml`: GitHub Actions authenticates through Workload Identity Federation (provider restricted to this repo and the gcp and main branches), builds and pushes an image tagged with the commit SHA, deploys a no-traffic revision, smoke tests it and promotes it. The deployer service account has resource-scoped roles only and no stored keys. Verified: a push triggered a run that succeeded and the live service now runs that commit's image.

### Measured experiments (use these facts; do not exaggerate them)

- Sustained in-region load (200 concurrent users, 5,000 requests, all HTTP 200, zero errors): 106.5 req/s with every request on one item (p50 955 ms, p95 1,785 ms) versus 276.3 req/s when the same load was spread over 4 items (p50 260 ms, p95 524 ms). Spreading the load across 4 rows gave about 2.6x the throughput and about 3.7x lower median latency, which points to row-lock contention on the single hot row. This is supported by the measurements but lock waits were not inspected directly.
- Deliberate connection pool exhaustion: with oversized pools (10 + 10 per worker, up to 120 connections against a database allowing 25), only 452 of 2,000 requests succeeded (22.6%). Postgres rejected connections (`remaining connection slots are reserved`, `too many clients already`). The median stayed low (246 ms) while p95 reached about 21 s. The normal configuration (2 + 1 per worker, 3 x 2 x 3 = 18 connections) had zero errors afterwards.
- Consistency: across 34,296 purchases on 4 items (including runs with HTTP 409 responses), orders equalled stock removed on every item. No overselling and no lost writes.
- Run-to-run variance is large (the same 1,000-request test gave 35 and 104 req/s on two runs), so quote the sustained 5,000-request numbers and say "measured", not "guaranteed".

### Still NOT done (do not claim)

- A Minikube versus Cloud Run comparison: the Minikube side was not re-measured with the same test.
- A JMeter performance gate in the pipeline (left out on purpose because of the variance above).
- Terraform or any other infrastructure-as-code tool (the monitoring definitions are JSON files applied through the Cloud Monitoring API, which is "monitoring as code", not Terraform), private IP for Cloud SQL, Cloud Armor, Cloud Trace, GKE.
- Done since the earlier version of this brief: README with architecture diagram, 28 screenshots (emails redacted), RESULTS.md, the old self-hosted Minikube workflow disabled in the repo.
- Cloud SQL and the Cloud Run service are still running; they will be deleted when the project is finished, so a live link may not work later. Do not put a live demo URL on the resume.

## 5. Claims on the current resume that need checking (important for honesty)

The resume currently says: "tuned connection pooling to eliminate database locking under 10,000+ concurrent requests" and "sustaining 270+ req/sec with zero error rates."

What the repository actually contains:
- `batches.jmx` is configured for 200 threads x 5 loops (about 1,000 requests) with a 1 second ramp-up. The README mentions 10,000 users, but the JMX file does not match that.
- The CI gate enforces an error rate of 0% and a throughput floor of only 80 req/sec.

So those two numbers are not reproducible from the repo as it stands. The owner may have measured them in an actual run, but the owner must confirm. The LLM must not copy these numbers into any new GCP bullet. After the GCP load tests, prefer numbers that were measured and logged in this repo (section 7).

## 6. Where and how to add it on the resume

Option A (recommended): a new entry under PROJECTS on page 2, titled for example:

`Retail API on Google Cloud: Cloud Run, Cloud SQL and Keyless CI/CD - [GitHub]`

It links to the new repo and is described as a migration and load-test study of the earlier prototype. This is accurate even if the internship did not use GCP.

Option B: only if the owner confirms the internship work moved to GCP, edit the third iTuring.ai bullet to mention Cloud Run. Otherwise do not touch the internship section.

Also update the existing iTuring.ai GitHub link only if the owner wants it to point at the new repo. The old link is still valid for the Minikube version.

Skills section, under "DevOps & Cloud Computing" (add only services that were actually completed):
`Google Cloud Platform (Cloud Run, Cloud SQL, Artifact Registry, Cloud Build, Secret Manager, Cloud Monitoring, IAM, Workload Identity Federation)`

Optionally add "Infrastructure as code" only if the stretch goal Terraform is completed. Do not add it otherwise.

### Template bullets (replace every `[PLACEHOLDER]` with a value from section 7; delete any bullet whose facts did not get completed)

Project entry title:
`Retail API on Google Cloud (Cloud Run, Cloud SQL, Keyless CI/CD) - [GitHub]`

Full version (4 bullets):

- Migrated a FastAPI/PostgreSQL retail API from Kubernetes to Google Cloud Run with Cloud SQL, Artifact Registry and Cloud Build, using a least-privilege service account and Secret Manager for the database password and JWT key.
- Sized per-worker connection pools against Cloud SQL's measured `max_connections` limit of 25 (3 instances x 2 workers x 3 connections = 18) and moved schema creation into a Cloud Run Job, removing a startup race between workers. A deliberate oversized-pool test confirmed the limit: only 22.6% of requests succeeded.
- Load tested with Apache JMeter from a Cloud Run Job in the same region: 276 req/s at p95 524 ms with zero errors over 5,000 requests spread across 4 items, versus 106 req/s on a single hot row, which pointed to row-lock contention. Orders matched stock removed exactly across 34,296 purchases (no overselling).
- Built a GitHub Actions pipeline that deploys through Workload Identity Federation (no stored keys) with a no-traffic candidate revision, smoke test and traffic promotion, and added Cloud Monitoring dashboards, an uptime check and alerts on 5xx rate and latency (5xx alert verified firing and recovering).

Compact version (2 bullets, use if page space is tight):

- Migrated a FastAPI/PostgreSQL retail API from Kubernetes to Google Cloud Run and Cloud SQL, with Secret Manager, least-privilege IAM, and keyless GitHub Actions deploys via Workload Identity Federation.
- Load tested with Apache JMeter in-region (276 req/s, p95 524 ms, zero errors over 5,000 requests), sized connection pools against the measured Cloud SQL limit, and added Cloud Monitoring dashboards and alerts.

One bullet that can be used today, before the load tests are finished, because every fact in it is already verified:

- Hardened a FastAPI/PostgreSQL service for Cloud Run: externalized secrets, added a DB-free liveness probe, moved schema creation out of app startup to fix a multi-worker race, and verified atomic purchases under 40 concurrent requests (15 sold of 15 in stock, 25 rejected, 15 order rows, no overselling).

## 7. Numbers to fill in after the project is finished

The owner records these from the JMeter summary, Cloud Monitoring and the Cloud Run configuration. The LLM must only use values that appear in this table once filled.

| Placeholder | Meaning | Where it comes from | Value |
|---|---|---|---|
| `[RPS]` | Sustained throughput on Cloud Run | JMeter summary report | **276.3 req/s** (5,000 requests spread over 4 items, run S2c); **106.5 req/s** with every request on one item (run S1c) |
| `[P95]` | 95th percentile latency in ms | JMeter or Cloud Monitoring | **524 ms** (spread), **1,785 ms** (single item) |
| `[P99]` | 99th percentile latency in ms | JMeter or Cloud Monitoring | **4,892 ms** (spread), **3,455 ms** (single item). Tails of 3 to 5 s were seen in most runs and were not diagnosed, so avoid quoting p99 as a strength |
| `[ERROR_RATE]` | Error rate in % | JMeter | **0%** in S1c and S2c (all 5,000 requests HTTP 200 in each) |
| `[LOAD_SOURCE]` | Where the load ran | Owner note | Cloud Run Job in asia-south1 (same region as the service). Laptop runs also exist and were slower and noisier |
| `[THREADS_TOTAL]` | Total requests or threads in the test | JMX config | 200 concurrent users, 5,000 requests per sustained run (also 1,000-request runs) |
| `[INSTANCES]` | Cloud Run max instances | Deploy command | 3 |
| `[WORKERS]` | Uvicorn workers per instance | Deploy config | 2 |
| `[POOL]` | pool_size + max_overflow per worker | Env config | 3 (pool 2 + overflow 1); 3 x 2 x 3 = 18 connections |
| `[MAX_CONN]` | Cloud SQL max_connections observed | `SHOW max_connections;` | 25 (3 reserved, 22 usable) |
| `[TIER]` | Cloud SQL machine tier | Instance config | `db-f1-micro`, PostgreSQL 15.19, Enterprise edition, 10 GB SSD, zonal |
| `[ORDERS]` | Order rows after a run | SQL count | 34,296 total orders after all runs |
| `[STOCK_DROP]` | Stock decrease after a run | SQL | Equal to orders on every item (21,221 / 4,415 / 4,318 / 4,342) |
| `[MINIKUBE_RPS]` | Minikube throughput measured the same way | JMeter on Minikube | NOT MEASURED. Do not write any comparison. The repo's own CI comment says about 120 req/s, which is unverified |
| `[COLD_START_MS]` | Cloud Run cold start observed | Logs or test | NOT MEASURED |
| `[COST]` | Total spend for the project | Billing report | NOT KNOWN YET (billing data lags; check Billing, Reports after the project is deleted) |

Rules for using the table: laptop-based load tests mostly measure the owner's internet connection, so any bullet using laptop numbers must say so or use the same-region numbers instead. If the Minikube and Cloud Run numbers were not measured the same way, do not write a "X times faster" claim.

## 8. Interview talking points (keep bullets consistent with these)

- Why Cloud Run instead of GKE: managed, scales to zero or to a minimum, simple for a stateless API. Concurrency per instance replaces replica counts.
- Connection pool math: `max_instances x workers x (pool_size + max_overflow)` must stay below Cloud SQL `max_connections` minus a small reserve. The shared-core tier allows roughly 25 connections, so the original 20 + 30 per worker pool would have exhausted it with a single instance.
- Why schema creation is a Job: concurrent import-time `create_all` calls raced and crashed a worker (reproduced locally).
- Liveness versus readiness: `/livez` does not touch the DB so a database outage does not restart healthy containers; `/health` checks the DB for readiness and startup.
- Atomic purchase: a single `UPDATE ... WHERE stock > 0 RETURNING` plus the order insert in the same transaction, returning 409 when out of stock. Verified with 40 concurrent requests.
- Workload Identity Federation: GitHub issues a short-lived OIDC token, Google exchanges it for temporary credentials, restricted to one repository, so no long-lived keys are stored.
- Least privilege: runtime service account only has Cloud SQL Client and Secret Accessor; the deployer account only has what deploys need.
- Cost control: Cloud SQL is the main cost, so it is created for the testing window and deleted afterwards; budget alerts only notify and do not cap spending.
- Honest limits: single region, small instance sizes, no private networking unless the stretch goal was done.

## 9. Things the LLM should ask the owner before finalizing

1. Is the GCP work a personal project (separate entry) or part of the internship (edit the internship bullet)?
2. Which load-test numbers were measured, and from where did the load run?
3. Were any stretch goals finished (Terraform, private IP, Cloud Armor, Cloud Trace, GKE)? Only mention those that were.
4. Is there still space on page 2 for the full 4-bullet version or should the compact 2-bullet version be used?
5. Should the internship link point to the old repo or the new one?

## 10. Full project details (the raw material for any resume line)

### 10.1 What was built, component by component

| Area | What exists | Evidence in the repo |
|---|---|---|
| Application | FastAPI app with a customer storefront, JSON API, admin dashboard (JWT login, bcrypt hashes), atomic purchase endpoint, DB-free `/livez` and DB-checking `/health` | `app/`, `tests/test_api.py` (20 tests) |
| Data model | `items`, `admins`, and a new `orders` table written in the same transaction as each stock decrement | `app/models/item.py`, `app/controllers/customer.py` |
| Container | Dockerfile reads `PORT` and `WORKERS` from the environment, runs Uvicorn with `exec` so SIGTERM reaches it | `Dockerfile` |
| Configuration | Cloud SQL Unix-socket connection via `INSTANCE_CONNECTION_NAME`, per-worker pool size from `DB_POOL_SIZE` and `DB_MAX_OVERFLOW`, secrets from environment, production refuses to start without `SECRET_KEY` | `app/core/database.py`, `app/services/auth.py` |
| Database lifecycle | Schema creation, admin creation, seeding and a consistency report run as Cloud Run Jobs from the same image | `scripts/init_db.py`, `create_admin.py`, `seed_items.py`, `db_report.py` |
| Registry and builds | Artifact Registry repo with a keep-last-5 cleanup policy, Cloud Build, images tagged with the git SHA (never `latest`), pinned dependencies | `requirements.txt`, `IMPLEMENTATION_PLAN.md` |
| Identity | Runtime service account with Cloud SQL Client plus Secret Accessor on three individual secrets; separate deployer service account with resource-scoped roles only | `IMPLEMENTATION_PLAN.md` phases 2, 3 and 6 |
| Secrets | Three Secret Manager secrets (database password, JWT key, admin password) generated randomly, never printed or committed | console screenshot 13 |
| Database | Cloud SQL for PostgreSQL 15.19, `db-f1-micro`, Enterprise, zonal, 10 GB SSD, no backups, no authorized networks | screenshots 08 and 09 |
| Runtime | Cloud Run service: 2 vCPU, 1 GiB, concurrency 40, max 3 instances, CPU boost, startup probe on `/health`, liveness probe on `/livez`, secrets as references | screenshots 05a to 05c |
| Release practice | No-traffic deploy on a tagged URL, 10% traffic split, promotion, rollback, roll forward | screenshot 05a, `IMPLEMENTATION_PLAN.md` phase 4 |
| Load testing | Parameterized JMeter test, in-region JMeter Cloud Run Job image, Python summarizer, results log | `batches.jmx`, `loadtest/`, `tests/summarize_results.py`, `RESULTS.md` |
| Observability | Dashboard (6 charts), uptime check on `/livez`, 3 alert policies, log-based metric for HTTP 409, email notification channel, all defined as JSON | `monitoring/`, screenshots 01 to 04 |
| CI/CD | GitHub Actions workflow: tests, image build tagged with the SHA, keyless auth via Workload Identity Federation, no-traffic deploy, smoke test, traffic promotion, retries on push, docs-only changes skipped | `.github/workflows/gcp-deploy.yml`, screenshots 06 and 07 |
| Documentation | README with Mermaid architecture diagram and screenshots, `RESULTS.md`, `IMPLEMENTATION_PLAN.md`, 28 redacted screenshots, original Minikube README preserved | `README.md`, `docs/` |

### 10.2 Problems found and solved (good material for "challenge and result" lines)

| # | Symptom | Root cause | Fix | Evidence |
|---|---|---|---|---|
| 1 | Fresh Docker build failed with `No module named 'psycopg'` | SQLAlchemy 2.1 maps a bare `postgresql://` URL to the psycopg v3 driver while the project installs psycopg2; dependencies were unpinned | URL rewritten to `postgresql+psycopg2://`, requirements pinned to the tested versions | Reproduced on the original code; plan, phase 1 |
| 2 | A Uvicorn worker crashed on startup with a duplicate-key error | Both workers ran `create_all` at import time and raced | Table creation moved to `scripts/init_db.py`, run once as a Cloud Run Job; import-time creation is opt-in | Reproduced locally with Docker Compose |
| 3 | Cloud SQL pool example in the plan (3 x 2 x 5 = 30) could not work | Measured `max_connections` was 25 with 3 reserved | Pools sized 2 + 1 per worker, 3 x 2 x 3 = 18 connections | `db_report` output; `RESULTS.md` |
| 4 | `/healthz` returned a Google 404 page on the public URL | Cloud Run's front end reserves that path on `*.run.app` | Liveness route renamed `/livez`, uptime check pointed at it | Smoke test and logs showed the request never reached the app |
| 5 | Throughput stayed near 100 req/s whatever the client | Every request updated the same row (item 1), so row locks serialized work | Same load spread over 4 items gave 276 req/s | S1c versus S2c in `RESULTS.md` |
| 6 | Misleading comparison runs | Stock ran out partway, so some runs mixed HTTP 409 (cheap path) with 200 | Stock topped up, runs repeated clean; mixed runs kept in the log but labeled not comparable | `RESULTS.md` run table |
| 7 | Raw JMeter CSV read back through Cloud Logging lost lines on 5,000-request runs | Cloud Logging drops lines under bursts | Summary computed inside the load generator container with `sort` and `awk`; only a few lines are logged | `loadtest/run.sh` |
| 8 | Pipeline run failed at `docker push` with "Unable to retrieve Identity Pool subject token" | Transient timeout fetching GitHub's short-lived token after a long idle build | Build first, authenticate right before the push, retry the push up to 3 times | Next run passed; plan, phase 6 |
| 9 | Pipeline failed on its first run | `pytest` did not put the repo on the import path | `python -m pytest` | Plan, phase 6 |
| 10 | Rolling back after the pool test would have kept the broken settings | The service's latest template still held the oversized pool env vars | Pool settings reset in the same update that changed `min-instances` | Cloud Run revisions screenshot |

### 10.3 Design decisions and the reasoning behind them

- **Cloud Run over GKE:** stateless API, managed scaling, revision traffic splitting built in, much cheaper to run for a short project.
- **Cloud SQL socket instead of a public connection:** the app connects through the Cloud SQL connector with IAM; there are no authorized networks. (The instance still has the default public IP, so do not describe it as private.)
- **Secrets as references, not values:** Cloud Run env vars point at Secret Manager versions; the runtime account can read only the three named secrets.
- **Keyless deploys:** GitHub's OIDC token is exchanged through Workload Identity Federation; the provider only trusts `RO-03/Retail-API-GCP` on the `gcp` and `main` branches; the deployer service account has no stored keys and no project-level roles.
- **Tag by SHA:** each Cloud Run revision maps to an exact commit, so any revision can be rolled back or audited.
- **No performance gate in CI:** the measured variance (35 to 104 req/s on identical runs) would make a throughput gate flaky, so it was left out on purpose.
- **Percentiles over averages:** the pool failure test kept a low median (246 ms) while p95 reached about 21 s and most requests failed, which is why the dashboard and alerts use percentiles and error rate.

### 10.4 Scale of the work (facts, safe to quote)

- 8 console services used directly: Cloud Run (service and Jobs), Cloud SQL, Artifact Registry, Cloud Build, Secret Manager, Cloud Monitoring, Cloud Logging, IAM with Workload Identity Federation.
- 2 service accounts, 3 secrets, 3 alert policies, 1 dashboard (6 charts), 1 uptime check, 1 log-based metric, 1 notification channel.
- 20 unit tests, 28 screenshots, 34,296 purchases verified for consistency, 5,000-request sustained load tests, 1 deliberate failure test.
- Cloud Run revision numbers in the console reached 20 while practicing releases and testing (not all were serving traffic).

### 10.5 Keywords for ATS and recruiter scanning (use only what is true)

- **Cloud and infrastructure:** Google Cloud Platform (GCP), Cloud Run, Cloud Run Jobs, Cloud SQL, Artifact Registry, Cloud Build, Secret Manager, Cloud Monitoring, Cloud Logging, IAM, service accounts, least privilege, Workload Identity Federation, OIDC, containers, Docker.
- **Delivery:** CI/CD, GitHub Actions, canary release (no-traffic revision, 10% split, rollback), traffic splitting, immutable image tags, smoke tests, keyless authentication.
- **Reliability and performance:** load testing, Apache JMeter, connection pooling, database connection limits, p95 and p99 latency, throughput, alerting, uptime checks, log-based metrics, observability, failure testing, health probes (liveness, readiness, startup).
- **Backend:** Python, FastAPI, PostgreSQL, SQLAlchemy, REST APIs, JWT, transactions, concurrency control, row-level contention.
- **Do not include unless done:** Terraform, Kubernetes on GKE, Cloud Armor, VPC, private networking, high availability, autoscaling to thousands of requests, SLOs.

## 11. Resume line options (all numbers are measured; use the length that fits)

### 11.1 One-line headline (for a skills-heavy resume or a project subtitle)

- Migrated a FastAPI/PostgreSQL retail API to Google Cloud Run and Cloud SQL with Secret Manager, least-privilege IAM, keyless GitHub Actions deploys and Cloud Monitoring alerts.

### 11.2 Two bullets (tight on space)

- Migrated a FastAPI/PostgreSQL retail API from Kubernetes to Google Cloud Run and Cloud SQL, using Secret Manager, least-privilege service accounts and a keyless GitHub Actions pipeline (Workload Identity Federation) with no-traffic canary releases.
- Load tested with Apache JMeter in-region (276 req/s, p95 524 ms, zero errors over 5,000 requests), sized connection pools to Cloud SQL's measured 25-connection limit, and added Cloud Monitoring dashboards and alerts.

### 11.3 Four bullets (full entry, backend plus cloud emphasis)

- Migrated a FastAPI/PostgreSQL retail API to Google Cloud Run and Cloud SQL, with images in Artifact Registry tagged by git SHA, credentials in Secret Manager and a least-privilege runtime service account.
- Diagnosed throughput limits with in-region JMeter load tests: 106 req/s when every request hit one database row versus 276 req/s (p95 524 ms, zero errors, 5,000 requests) when spread over four rows, pointing to row-lock contention.
- Sized per-worker connection pools against Cloud SQL's measured limit (3 instances x 2 workers x 3 connections = 18 of 22 usable) and confirmed it with a deliberate failure test where oversized pools let only 22.6% of requests succeed; verified exact order and stock consistency across 34,296 purchases.
- Built a keyless GitHub Actions pipeline (Workload Identity Federation) that builds, deploys a no-traffic revision, smoke tests and promotes it, plus Cloud Monitoring dashboards, an uptime check and alerts (5xx alert verified firing and recovering).

### 11.4 Four bullets (DevOps and SRE emphasis)

- Designed a keyless CI/CD pipeline on GitHub Actions and Workload Identity Federation (repository and branch restricted, no stored keys, resource-scoped deployer roles) that deploys to Cloud Run through a no-traffic revision, smoke test and traffic promotion.
- Practiced release safety on Cloud Run revisions: tagged candidate URLs, 10% traffic splits, rollback and roll forward, with every image tagged by commit SHA.
- Built observability as code: a six-chart Cloud Monitoring dashboard, uptime check, alert policies for 5xx rate, p95 latency and uptime, and a log-based metric for out-of-stock responses; validated the 5xx alert by deliberately exhausting the database connection pool.
- Measured and documented limits: Cloud SQL `max_connections` 25, pool sizing math, run-to-run variance (35 to 104 req/s on identical tests) and a logged results file with per-run settings.

### 11.5 One-line skills entry

`Google Cloud Platform (Cloud Run, Cloud SQL, Artifact Registry, Cloud Build, Secret Manager, Cloud Monitoring, IAM, Workload Identity Federation)`

### 11.6 Cold start (fill in after the measurement is recorded in RESULTS.md)

- Measured on four idle old revisions: first request 6.1 to 6.4 seconds versus 0.2 to 0.3 seconds once warm (measured from a laptop, includes network). A test of a shorter startup-probe interval is recorded in RESULTS.md if it was completed. Until then do not write a cold-start improvement claim.

### 11.7 Words and claims to avoid (not supported by the evidence)

- "Production", "production-grade" or "serving users": it was a test deployment that has been or will be deleted.
- "Zero downtime", "high availability", "99.9% uptime": the database is a single zonal instance and uptime was not measured over time.
- "Scales to thousands of requests" or any number larger than the measured 276 req/s on this setup.
- "X times faster than Kubernetes" or any Minikube comparison: not measured.
- "Private networking", "VPC", "Terraform", "GKE": not done.
- "Eliminated database locking": the measured result is that spreading the load across rows reduced contention; locking itself was not removed.
- A live demo link: the service is deleted after the project.

### 11.8 Interview preparation (the owner should be able to explain every line above)

Be ready to explain, in your own words, with the numbers:
1. Why a hot row caps throughput, and how spreading the load changed p50 from 955 ms to 260 ms.
2. The pool formula, why 25 connections is small, and what "remaining connection slots are reserved" means.
3. How Workload Identity Federation replaces a service account key, and what the attribute condition restricts.
4. The difference between the liveness, readiness and startup probes, and why `/livez` does not touch the database.
5. Why the median stayed low while p95 and the error rate exposed the pool failure.
6. How a no-traffic revision, a tagged URL, a 10% split and a rollback work on Cloud Run.
7. What you would do next: private IP and a connector-only network path, Terraform, a connection pooler such as PgBouncer, a larger Cloud SQL tier, and an in-pipeline performance check once variance is understood.

To prepare, read `README.md`, `RESULTS.md`, the findings in `IMPLEMENTATION_PLAN.md`, and re-run one load test and one deploy yourself while the environment still exists, or follow the commands in the README against a fresh project.
