# JMeter load generator packaged for Cloud Run Jobs, so the test runs inside the
# same region as the service (no laptop internet in the numbers).
# Build: gcloud builds submit --config loadtest/cloudbuild.yaml --substitutions=_TAG=<tag> .
# (cloudbuild.yaml copies batches.jmx into this directory first; the repo root
# .dockerignore excludes it from the app image.)
FROM qainsights/jmeter:latest

COPY batches.jmx /test/batches.jmx
COPY run.sh /test/run.sh

# Replace the base entrypoint wrapper with our script.
ENTRYPOINT ["sh", "/test/run.sh"]
