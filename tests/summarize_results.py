"""
tests/summarize_results.py
Summarize a JMeter results CSV (JTL) into the numbers recorded in RESULTS.md.

Usage:
    python tests/summarize_results.py results.csv

Reports total samples, wall-clock throughput, error rate, latency percentiles and the
response-code breakdown. Unlike check_performance.py it never fails the run, and it
separates HTTP 409 (out of stock, an expected business response) from real errors.
"""

import csv
import math
import sys
from collections import Counter


def percentile(sorted_values, pct):
    """Nearest-rank percentile of an already sorted list."""
    rank = max(1, math.ceil(pct / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def summarize(path):
    elapsed, codes, stamps, connect = [], Counter(), [], []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            elapsed.append(int(row["elapsed"]))
            codes[row["responseCode"]] += 1
            stamps.append((int(row["timeStamp"]), int(row["elapsed"])))
            if row.get("Connect", "").isdigit():
                connect.append(int(row["Connect"]))
    if not elapsed:
        sys.exit("no samples in " + path)

    elapsed.sort()
    start = min(t for t, _ in stamps)
    end = max(t + e for t, e in stamps)
    duration = max((end - start) / 1000.0, 0.001)
    total = len(elapsed)
    ok = codes.get("200", 0)
    out_of_stock = codes.get("409", 0)
    errors = total - ok - out_of_stock

    print(f"samples            : {total}")
    print(f"duration_s         : {duration:.2f}")
    print(f"throughput_rps     : {total / duration:.1f}")
    print(f"http_200           : {ok}")
    print(f"http_409           : {out_of_stock}")
    print(f"errors_excl_409    : {errors} ({errors / total * 100:.2f}%)")
    print(f"latency_ms avg     : {sum(elapsed) / total:.0f}")
    print(f"latency_ms p50     : {percentile(elapsed, 50)}")
    print(f"latency_ms p95     : {percentile(elapsed, 95)}")
    print(f"latency_ms p99     : {percentile(elapsed, 99)}")
    print(f"latency_ms max     : {elapsed[-1]}")
    print("response_codes     : " + ", ".join(f"{c}={n}" for c, n in sorted(codes.items())))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python tests/summarize_results.py results.csv")
    summarize(sys.argv[1])
