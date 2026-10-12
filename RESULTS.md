# Results Log

Measured results for the Retail API on Google Cloud Run. Every number here was measured, and the raw configuration of each run is listed so it can be repeated. Add new runs at the bottom of the run table and in the notes. Do not edit old numbers.

## Environment (as deployed)

| Item | Value |
|---|---|
| Region | asia-south1 (Mumbai) |
| Cloud Run service | `retail-api`, 2 vCPU, 1 GiB, concurrency 40, min instances 1, max instances 3, CPU boost on |
| App | FastAPI on Uvicorn, 2 workers per instance |
| DB pool per worker | pool_size 2 + max_overflow 1 = 3 (3 instances x 2 workers x 3 = 18 connections) |
| Cloud SQL | PostgreSQL 15.19, `db-f1-micro`, Enterprise edition, zonal, 10 GB SSD, no backups |
| Measured `max_connections` | 25 (3 reserved for superusers, 22 usable) |
| Load tool | Apache JMeter (`qainsights/jmeter:latest` in Docker), `batches.jmx`, POST `/purchase/{item}` |
| JMeter shape | 200 threads, 5 loops, ramp 1 s, synchronized start (1,000 requests) unless noted |

Measurement notes:
- Throughput is requests divided by wall-clock time from the first request start to the last request end.
- Percentiles are nearest-rank on JMeter's `elapsed` (client-side, includes network and TLS).
- Server-side latency comes from Cloud Run request logs (`httpRequest.latency`).
- Laptop runs measure the path from the owner's laptop over the internet, so they understate what the service can do.
- Summaries are produced by `tests/summarize_results.py`. Consistency is checked by `scripts/db_report.py` (Cloud Run Job `retail-tools`).

## Baseline before load tests

Item 1 stock 14,980 with 20 orders (after a 20-request smoke test), item 3 stock 14 with 1 order. Starting seed: item 1 = 15,000, item 2 = 30, item 3 = 15, item 4 = 100.

## Run table

| Run | From | Target | Requests | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | Errors (non-409) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| smoke | laptop | item 1 | 20 | 27.7 | 146 | 564 | 575 | 575 | 0 | 10 users x 2 loops, checks setup only |
| L1 | laptop | item 1 | 1,000 | 35.4 | 1,052 | 2,222 | 7,463 | 21,433 | 0 | First burst after idle; all 3 instances used (329 / 353 / 318 requests) |
| L1b | laptop | item 1 | 1,000 | 103.8 | 1,050 | 1,992 | 2,449 | 2,541 | 0 | Identical shape, repeated 2 minutes later |
| R1 | Cloud Run Job (asia-south1) | item 1 | 1,000 | 81.9 | 1,300 | 3,390 | 3,795 | 3,977 | 0 | Same shape as L1, load generator inside the region |
| R2 | Cloud Run Job | item 1 | 1,000 | 99.0 | 1,115 | 2,643 | 2,943 | 3,065 | 0 | Hot row |
| R3 | Cloud Run Job | items 1-4 random | 1,000 | 203.3 | 310 | 2,779 | 2,890 | 2,926 | 0 | Spread across 4 items |
| R4 | Cloud Run Job | item 1 | 1,000 | 94.9 | 1,098 | 3,063 | 3,361 | n/a | 0 | Hot row, repeat of R2 |
| R5 | Cloud Run Job | items 1-4 random | 1,000 | 108.0 | 307 | 6,803 | 7,097 | n/a | 0 | Spread, repeat of R3 (heavy tail, short run) |
| S1b | Cloud Run Job | item 1 | 5,000 | 159.0 | 441 | 1,668 | 3,215 | 3,646 | 0 | **Mixed run**: stock ran out, 3,146 x 200 and 1,854 x 409. Not comparable. |
| S2b | Cloud Run Job | items 1-4 random | 5,000 | 251.6 | 351 | 746 | 2,803 | 3,073 | 0 | **Mixed run**: 3,729 x 200 and 1,271 x 409. Not comparable. |
| **S1c** | Cloud Run Job | item 1 | 5,000 | **106.5** | 955 | 1,785 | 3,455 | 3,884 | 0 | Clean: all 5,000 x 200 (stock topped up first). Hot row |
| **S2c** | Cloud Run Job | items 1-4 random | 5,000 | **276.3** | 260 | 524 | 4,892 | 5,107 | 0 | Clean: all 5,000 x 200. Spread across 4 items |

Run shape for all Cloud Run Job runs: 200 threads, ramp 1 s, loops 5 (1,000 requests) or 25 (5,000 requests), load generator `retail-loadtest` (2 vCPU, 2 GiB) calling the public service URL over HTTPS. Runs R1 to R5 had their raw CSV read back through Cloud Logging, which worked at 1,000 requests. Two further 5,000-request runs (one hot row, one spread) were discarded because Cloud Logging dropped CSV lines, so the load generator now computes the summary inside the container. A 400-request check run and the smoke tests are also not in the table. All of those runs still consumed stock and created orders, which is why the consistency totals below exceed the sum of the recorded runs.

## Server-side view of L1

From Cloud Run request logs for the L1 window: 1,000 requests, all HTTP 200, server latency avg 642 ms, p50 619 ms, p95 1,302 ms, p99 1,503 ms, max 5,456 ms. Client-side p50 was 1,052 ms, so roughly 400 ms per request is network, TLS and queueing outside the container (laptop to Mumbai over the internet).

## Consistency checks (no overselling, no lost writes)

| After run | Item 1 stock | Item 1 orders | Check |
|---|---|---|---|
| Baseline | 14,980 | 20 | 15,000 - 20 = 14,980 |
| L1 + L1b (2,000 purchases) | 12,980 | 2,020 | 15,000 - 2,020 = 12,980, orders equal stock removed |

Final per-item check after all runs. Stock was topped up through the admin API twice: items 2 to 4 got +5,000, then all four items got +30,000.

| Item | Total stock ever added | Stock now | Removed | Orders | Match |
|---|---|---|---|---|---|
| 1 Wireless Mouse | 45,000 (15,000 seed + 30,000) | 23,779 | 21,221 | 21,221 | yes |
| 2 Mechanical Keyboard | 35,030 (30 + 5,000 + 30,000) | 30,615 | 4,415 | 4,415 | yes |
| 3 27-inch Monitor | 35,015 (15 + 5,000 + 30,000) | 30,697 | 4,318 | 4,318 | yes |
| 4 USB-C Hub | 35,100 (100 + 5,000 + 30,000) | 30,758 | 4,342 | 4,342 | yes |

Total orders 34,296. Orders equal stock removed on every item, including through runs with 409 responses, so there was no overselling and no lost writes. Postgres showed 13 current connections for the database at that moment, under the 22 usable.

## Experiment: hot row versus spread load

Hypothesis: with every request updating the same `items` row (item 1), the row lock serializes purchases, so throughput is capped by how long each transaction holds the lock, not by Cloud Run capacity or by the 18 pooled connections.

Method: same load generator, same shape, same service, only the target item changed (`ITEMS=1` versus `ITEMS=4`, a random item from 1 to 4 per request). Stock was topped up first so that no request returned 409.

| | Hot row (item 1) | Spread (items 1-4) | Change |
|---|---|---|---|
| Throughput, 5,000 requests (S1c vs S2c) | 106.5 req/s | 276.3 req/s | about 2.6x |
| p50 latency | 955 ms | 260 ms | about 3.7x lower |
| p95 latency | 1,785 ms | 524 ms | about 3.4x lower |
| p99 latency | 3,455 ms | 4,892 ms | worse (tail) |
| Short 1,000-request runs, p50 (R2/R4 vs R3/R5) | 1,115 / 1,098 ms | 310 / 307 ms | about 3.5x lower, consistent |

Result: spreading the same load over 4 rows roughly 2.6 times the throughput and cuts the median latency by about 3.5 times, which supports the hot-row hypothesis. It is evidence, not proof: it was not tested by inspecting lock waits in Postgres. The p99 tail did not improve and was worse in the spread runs (about 3 to 5 seconds), so something else causes the occasional slow request (candidates: the 3 + 3 pool limit queueing, instance start-up, or Cloud SQL `db-f1-micro` CPU limits). That was not diagnosed.

## Notes and findings so far

- The same test shape gave 35 req/s on its first run and 104 req/s on the repeat. Run-to-run variance is large, so single runs should not be quoted as "the" number. The first run came after an idle period and the service scaled from 1 to 3 instances during it.
- All 1,000 requests of each run succeeded (HTTP 200) and database counts matched exactly.
- Repo comparison: CI's own comment (`tests/check_performance.py`) records the earlier Minikube baseline as about 120 req/s with a gate of 80 req/s. The resume currently says 270+ req/s. Those figures do not agree, and none of them have been re-measured on the same test.
