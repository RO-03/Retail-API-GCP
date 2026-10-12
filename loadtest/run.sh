#!/bin/sh
# Runs batches.jmx against $TARGET_HOST and prints a summary between markers, so the
# numbers can be read back from Cloud Logging without shipping thousands of CSV rows
# (Cloud Logging drops lines under bursts, so raw CSV is only printed when PRINT_CSV=1).
# Env: TARGET_HOST (required), TARGET_PORT=443, TARGET_PROTOCOL=https,
#      THREADS=200, LOOPS=5, RAMP=1, ITEMS=1
# ITEMS=N picks a random item id in 1..N per request (1 = every request hits item 1).
set -e
jmeter -n -t /test/batches.jmx -l /tmp/results.csv -j /tmp/jmeter.log \
  "-Jhost=${TARGET_HOST:?TARGET_HOST is required}" \
  "-Jport=${TARGET_PORT:-443}" \
  "-Jprotocol=${TARGET_PROTOCOL:-https}" \
  "-Jitems=${ITEMS:-1}" \
  "-Jthreads=${THREADS:-200}" \
  "-Jloops=${LOOPS:-5}" \
  "-Jramp=${RAMP:-1}"

# Columns: 1 timeStamp, 2 elapsed, 4 responseCode. No commas occur in columns 1 to 4.
tail -n +2 /tmp/results.csv > /tmp/body.csv
cut -d, -f2 /tmp/body.csv | sort -n > /tmp/elapsed.txt
N=$(wc -l < /tmp/elapsed.txt)
pct() { sed -n "$(( (N * $1 + 99) / 100 ))p" /tmp/elapsed.txt; }
SPAN_MS=$(awk -F, 'NR==1{s=$1;e=$1+$2} {if($1<s)s=$1; if($1+$2>e)e=$1+$2} END{print e-s}' /tmp/body.csv)
AVG=$(awk '{s+=$1} END{printf "%.0f", s/NR}' /tmp/elapsed.txt)
CODES=$(cut -d, -f4 /tmp/body.csv | sort | uniq -c | awk '{printf "%s=%s ", $2, $1}')
RPS=$(awk -v n="$N" -v ms="$SPAN_MS" 'BEGIN{printf "%.1f", n/(ms/1000)}')

echo "SUMMARY_BEGIN"
echo "samples: $N"
echo "duration_s: $(awk -v ms="$SPAN_MS" 'BEGIN{printf "%.2f", ms/1000}')"
echo "throughput_rps: $RPS"
echo "latency_ms avg: $AVG"
echo "latency_ms p50: $(pct 50)"
echo "latency_ms p95: $(pct 95)"
echo "latency_ms p99: $(pct 99)"
echo "latency_ms max: $(tail -n 1 /tmp/elapsed.txt)"
echo "response_codes: $CODES"
echo "SUMMARY_END"

if [ "${PRINT_CSV:-0}" = "1" ]; then
  echo "JTL_BEGIN"; cat /tmp/results.csv; echo "JTL_END"
fi
