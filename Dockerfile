# SRN: PES2UG23CS495
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects PORT; local and K8s fall back to 8000.
EXPOSE 8000

# K8s: 3 pods x 2 workers = 6 total system workers (stress-tested optimum)
# Shell form via sh -c so ${PORT} and ${WORKERS} expand; exec keeps uvicorn as PID 1 for clean SIGTERM.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}"]
