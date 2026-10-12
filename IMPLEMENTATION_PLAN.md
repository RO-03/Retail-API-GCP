# GCP Migration: Implementation Plan

Goal: run the Retail API on Google Cloud (Cloud Run + Cloud SQL), load test it, automate deployment with keyless CI/CD, and document it. Region: `asia-south1` (Mumbai). Working branch: `gcp`.

## Repo findings that shape the plan

| Finding | Action |
|---|---|
| Dockerfile hardcodes port 8000 and 2 workers | Read `PORT` and `WORKERS` from env (Cloud Run injects `PORT`) |
| `DATABASE_URL` is a single string with a hardcoded fallback | Add a Cloud SQL socket mode, keep `DATABASE_URL` for local and tests |
| Pool is 20 + 30 per worker, up to 50 connections each | Shrink via env; size against Cloud SQL `max_connections` (f1-micro allows about 25) |
| `create_all()` runs at import time; seeding is manual | Move to `scripts/init_db.py`, run as a Cloud Run Job |
| `SECRET_KEY` and `admin123` are hardcoded | Move to Secret Manager |
| `/health` hits the DB | Keep for readiness and startup; add DB-free `/livez` for liveness |
| CI is self-hosted and Minikube-only | Add a separate GCP workflow on GitHub-hosted runners |
| JMeter targets `retail-store.local:80` over http | Parameterize host, port and protocol |

## Phase 0: Account and safety (about 1 hour) - DONE
- [x] Create the GCP project (`retailgcp`), link billing, set budget alerts. Done as one monthly budget of 2,420 INR with alerts at 25%, 50% and 100% (about $7, $14, $28).
- [x] Install gcloud; run `gcloud init` and `gcloud auth application-default login`.
- [x] Set the default region to `asia-south1`.
- [x] Enable APIs: run, artifactregistry, sqladmin, secretmanager, cloudbuild, monitoring, logging, iamcredentials.

Learn: projects vs billing accounts; budget alerts only notify, they do not cap spending.

## Phase 1: Make the code cloud-ready (Day 1) - DONE
- [x] Dockerfile: use `${PORT:-8000}` and `${WORKERS:-2}`; add `.git` to `.dockerignore`.
- [x] `app/core/database.py`: if `INSTANCE_CONNECTION_NAME` is set, build the URL with `URL.create` and `host=/cloudsql/<conn>`; otherwise use `DATABASE_URL`. Read `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` from env.
- [x] `app/services/auth.py`: read `SECRET_KEY` from env; fail loudly if missing outside dev.
- [x] Add `/livez` with no DB access.
- [x] Move `create_all` out of import time into `scripts/init_db.py`; make `create_admin.py` read its password from env.
- [x] Add an `orders` table (id, item_id, created_at) in `app/models/item.py`; insert a row inside the same transaction as the stock decrement in `POST /purchase/{item_id}`, so a purchase either does both or neither. Add a pytest check that stock drops by one and exactly one order row exists. This makes the load test write real data.
- [x] Run pytest and `docker compose up` to confirm local mode still works; commit.

Verified on real Postgres 15 via docker compose: 40 concurrent purchases on an item with 15 in stock gave 15 x 200 and 25 x 409, final stock 0, exactly 15 order rows. Deleting an item keeps its orders (item_id set to NULL). pytest: 20 passed.

Findings during Phase 1:
- SQLAlchemy 2.1+ maps a bare `postgresql://` URL to the psycopg v3 driver, but requirements install psycopg2, so fresh builds failed. Fixed by rewriting the URL to `postgresql+psycopg2://` in `database.py`.
- With `AUTO_CREATE_TABLES=1` (legacy compose and K8s path) two workers race on `create_all` and one crashes and is respawned. This is the reason Cloud Run uses `scripts/init_db.py` as a Job instead.
- Dependencies in `requirements.txt` were unpinned; pinned in Phase 2.

Learn: 12-factor config, why import-time side effects break at scale, liveness vs readiness vs startup probes.

## Phase 2: Registry, build, identity (Day 1) - DONE
- [x] Pin dependency versions in `requirements.txt` (the versions the tests passed against).
- [x] Create Artifact Registry `retail-repo` (asia-south1) with a cleanup policy keeping the last 5 images.
- [x] Build with Cloud Build; tag with the git SHA, never `latest`. First image: `asia-south1-docker.pkg.dev/retailgcp/retail-repo/retail-api:6a2cd31` (build took 1m05s).
- [x] Create service account `retail-run-sa` with only `roles/cloudsql.client` and `roles/secretmanager.secretAccessor`. Verified: exactly those two roles.

Note: the secretAccessor role is granted project-wide for now; in Phase 3 it can be narrowed to the three individual secrets.

Learn: Cloud Build vs local build, immutable tags, least privilege.

## Phase 3: Data and secrets (Day 2) - DONE (except secret rotation)
- [x] Create Cloud SQL Postgres 15 with `--edition=ENTERPRISE`. Instance `retail-db`, `db-f1-micro`, 10 GB SSD, zonal, no backups. Measured `SHOW max_connections;` = **25** (3 reserved for superusers, so 22 usable). Kept `db-f1-micro`.
- [x] No authorized networks; Cloud Run connects through the Cloud SQL connector socket (verified from a Cloud Run Job and the service).
- [x] Create secrets `db-password`, `jwt-secret-key`, `admin-password` (random values, never printed). Narrowed `secretAccessor` for `retail-run-sa` from project-wide to these three secrets only.
- [ ] Rotate one secret to see versioning (optional, do if time allows).

Learn: what Google manages vs what you still own; secret versions.

## Phase 4: Deploy and operate (Day 2) - DONE
- [x] Deploy to Cloud Run with: `--service-account retail-run-sa`, `--cpu 2 --memory 1Gi`, `--concurrency 40`, `--min-instances 1 --max-instances 3`, `--cpu-boost`, `--set-secrets`, startup probe on `/health`, liveness probe on `/livez`. Service: `retail-api` in asia-south1.
- [x] Pool budget check: `max_instances x workers x (pool + overflow) <= max_connections - reserved`. The original example (3 x 2 x 5 = 30) does not fit the measured limit of 25. Actual: 3 x 2 x (2 + 1) = 18 connections, under the 22 usable.
- [x] Cloud Run Job `retail-tools` (same image, Cloud SQL socket, secrets) ran `init_db`, `create_admin`, `seed_items` and `db_report` (max_connections and an orders-versus-stock check).
- [x] Practice revisions: deployed revision 2 with `--no-traffic` on a tagged URL, tested it, split 10%, promoted to 100%, rolled back to revision 1, rolled forward again.

Findings during Phase 4:
- Cloud Run's front end reserves `/healthz` on public `*.run.app` URLs and answers 404 itself, so the liveness route was renamed to `/livez`.
- Google's front end rejects a POST without a body or `Content-Length` with HTTP 411. Check that JMeter's POST sends `Content-Length: 0`.

Learn: Cloud Run concurrency vs Kubernetes replicas, cold starts, jobs vs services.

## Phase 5: Load test and observability (Day 3) - DONE (Minikube comparison not measured)
- [x] Parameterize `batches.jmx` with `${__P(host)}`, `${__P(port)}`, `${__P(protocol)}` (also item, threads, loops, ramp; defaults match the old Minikube setup).
- [x] Run from your laptop and from a Cloud Run Job in `asia-south1` (image in `loadtest/`); results are labeled by where the load ran. See `RESULTS.md`.
- [ ] Record RPS, p50/p95/p99 and error rate in a Minikube vs Cloud Run table. Cloud Run numbers are measured; the Minikube side has NOT been re-measured with the same test, so no comparison is claimed.
- [x] After each run, check that `orders` row count equals the stock decrease (no oversell, no lost writes). Verified across 34,296 orders on all 4 items.
- [x] Monitoring dashboard: request rate by status, latency percentiles, instance count, Cloud SQL connections and CPU, 409 count (`monitoring/dashboard.json`).
- [x] Uptime check on `/livez`; alerts on 5xx rate (verified firing), p95 latency, and uptime failure (the last two created, not yet seen firing).
- [x] Log-based metric `out_of_stock_409`, verified with deliberate 409s.
- [x] Deliberately exceed the connection budget once. Result: only 22.6% of 2,000 requests succeeded; Postgres rejected connections ("remaining connection slots are reserved", "too many clients already").
- [x] Extra experiment: hot row versus spread load. Spreading across 4 items gave about 2.6x throughput and about 3.7x lower median latency (RESULTS.md).

Learn: golden signals, alerting, why p50 can look fine while p95 and p99 and error rate show pool exhaustion.

## Phase 6: CI/CD with Workload Identity Federation (Day 3)
- [ ] Create a Workload Identity Pool and GitHub OIDC provider restricted to `RO-03/Retail-API-GCP`.
- [ ] Create a deployer service account with `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser`.
- [ ] Add `.github/workflows/gcp-deploy.yml` (GitHub-hosted runners, `gcp` branch): pytest, auth, build and push by SHA, deploy with `--no-traffic`, smoke test, promote traffic, short JMeter gate.
- [ ] Enable Actions on the repo; pin action versions.

Learn: OIDC token exchange, no long-lived keys, attribute conditions.

## Phase 7: Docs, resume, cleanup
- [ ] README: GCP architecture diagram, deploy steps or `deploy.sh`, results table, screenshots, cost notes, pool math. Fix badges that still point at the old repo.
- [ ] Delete the Cloud Run service and Cloud SQL instance; verify in Billing.
- [ ] Write resume bullets using only measured numbers.

## Stretch goals (by learning value)
1. Private IP for Cloud SQL via Direct VPC egress.
2. Terraform for the whole stack.
3. Load balancer with Cloud Armor rate limiting.
4. Cloud Trace via OpenTelemetry.
5. GKE with the existing `k8s/` manifests, compared to Cloud Run.

## Cost note
Cloud SQL is the main cost. Do Phases 3 to 5 in one or two sittings, then delete it.
