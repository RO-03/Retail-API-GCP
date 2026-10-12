<div align="center">
  <h1> High-Performance Retail API </h1>
  <p><i>A highly scalable, containerized REST API engineered for extreme concurrency</i></p>
  
  [![CI/CD Pipeline](https://github.com/RO-03/Retail-API-stress-test/actions/workflows/deploy.yml/badge.svg)](https://github.com/RO-03/Retail-API-stress-test/actions/workflows/deploy.yml)
  ![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
  ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)
  ![Kubernetes](https://img.shields.io/badge/Kubernetes-Minikube-326ce5?logo=kubernetes&logoColor=white)
  ![Docker](https://img.shields.io/badge/Docker-Ready-2496ed?logo=docker&logoColor=white)
</div>

---

## 📖 Overview

This project is a full-stack **Retail Store Inventory and Purchasing API** built to handle high-concurrency workloads (10,000+ simultaneous requests). 

**The Engineering Challenge:** The original monolithic architecture suffered from severe database locking bottlenecks under load. 
**The Solution:** This system was systematically refactored into a clean **MVC architecture**, migrated to **PostgreSQL** with aggressive connection pooling, containerized via **Docker**, and orchestrated across a **Kubernetes** cluster utilizing an **Nginx Ingress Controller** to bypass NodePort networking limits.

This repository serves as a showcase of modern backend engineering, performance tuning, and DevOps best practices.

---

## 🏗️ System Architecture

Traffic is routed through an Nginx Ingress Controller, which bypasses `kube-proxy` for direct upstream load balancing, feeding into a highly available API deployment connected to a persistently provisioned PostgreSQL database.

```text
                                    ┌──────────────────────────────────────────────┐
                                    │              Kubernetes Cluster              │
                                    │                                              │
 retail-store.local:80 ────────────►│  [Nginx Ingress Controller]                  │
                                    │    - ingressClassName: nginx                 │
                                    │    - path: / → retail-api-service:8000       │
                                    │                   │                          │
                                    │        ClusterIP Service (port 8000)         │
                                    │                   │                          │
                                    │   ┌───────────────┼───────────────┐          │
                                    │   ▼               ▼               ▼          │
                                    │ [Pod 1]        [Pod 2]        [Pod 3]        │
                                    │ 2 workers      2 workers      2 workers      │
                                    │       = 6 total Uvicorn workers              │
                                    │                   │                          │
                                    │     ClusterIP Service (db:5432)              │
                                    │                   │                          │
                                    │           [Postgres Pod]                     │
                                    │        max_connections=350                   │
                                    │           PVC (2Gi)                          │
                                    └──────────────────────────────────────────────┘
```

---

## ⚡ Performance Engineering & Tuning

This API isn't just containerized; it is mathematically tuned for its execution environment.

### 1. ASGI Worker Optimization
The optimal number of workers prevents excessive CPU context switching while maximizing throughput.
* **Step 1 – Calculate Worker Count:** `workers = CPU cores × 0.75`
* **Implementation:** In this K8s deployment, we run **3 Replicas**, each configured with **2 Uvicorn workers** in the `Dockerfile`, yielding an optimal **6 system workers**.

### 2. Database Connection Pooling
To prevent PostgreSQL connection exhaustion under a 10k user load, the connection pool was carefully sized.
* **Step 2 – Configure PostgreSQL Connections:** `max_connections = workers × 5 + 50`
* **Implementation:** `max_connections` is strictly set to **350** in the Postgres deployment. The SQLAlchemy engine is configured with `pool_size=20` and `max_overflow=30` per worker.

### 3. Nginx Ingress Migration
Standard Kubernetes `NodePort` routes traffic through `iptables`/`kube-proxy`, which capped throughput at ~146 req/sec during load testing. By migrating to an **Nginx Ingress Controller**, we achieved direct upstream routing, recovering the baseline **270+ req/sec** throughput with zero error rates.

---

## 🚀 CI/CD Pipeline

The `.github/workflows/deploy.yml` pipeline automates the entire delivery process on pushes to the `main` or `minikubeMVC` branches using a self-hosted runner:

1. **Unit Testing:** Provisions a Conda environment and executes `pytest` against an isolated, in-memory SQLite database to ensure business logic integrity.
2. **Performance Quality Gate:** Spins up a throwaway Docker container running **Apache JMeter** to execute a stress test against the cluster. A custom Python script (`check_performance.py`) parses the JMeter CSV results and immediately fails the build if error rates exceed thresholds.
3. **Build & Push:** Uses `eval $(minikube docker-env)` to build the optimized Docker image directly into the Minikube daemon, bypassing external container registries for ultra-fast deployments.
4. **Zero-Downtime Deployment:** Triggers a `kubectl rollout restart`. The pipeline strictly waits for the new pods to pass their `/health` Readiness and Liveness probes before marking the deployment as successful.

---

## 🛠️ Technology Stack

| Category | Technologies |
|---|---|
| **Backend Framework** | FastAPI (Python 3.11), Uvicorn, Jinja2 Templates |
| **Database & ORM** | PostgreSQL 15, SQLAlchemy, Pydantic |
| **Security** | JWT (python-jose), bcrypt password hashing, passlib |
| **Infrastructure** | Kubernetes (Minikube manifests), Docker |
| **Networking** | Nginx Ingress Controller |
| **CI/CD & Testing** | GitHub Actions, Pytest, HTTPX, Apache JMeter |

---

## 💻 Local Development Setup

### Prerequisites
* Docker Desktop or Minikube
* `kubectl` CLI
* Apache JMeter (for manual load testing)

### 1. Cluster Initialization
```bash
# Start Minikube and enable the required Nginx Ingress addon
minikube start
minikube addons enable ingress

# Point Docker CLI to Minikube's internal daemon
eval $(minikube docker-env)  # Linux/macOS
& minikube -p minikube docker-env --shell powershell | Invoke-Expression # Windows
```

### 2. Build & Deploy
```bash
# Build the application image
docker build -t retail-api:latest .

# Deploy the database, API, and Ingress routing
kubectl create namespace retail
kubectl apply -f k8s/postgres.yaml -n retail
kubectl apply -f k8s/api.yaml -n retail
kubectl apply -f k8s/ingress.yaml -n retail
```

### 3. Accessing the Application
Since the Nginx Ingress Controller listens on port 80 and expects the `retail-store.local` host, you must map it:

**On Windows (using Docker driver):**
1. Start the tunnel in a dedicated terminal: `minikube tunnel`
2. Run PowerShell as Administrator and append to your hosts file:
   ```powershell
   Add-Content -Path "C:\Windows\System32\drivers\etc\hosts" -Value "`n127.0.0.1`tretail-store.local"
   ```

You can now access the application at:
* **Storefront UI:** `http://retail-store.local/`
* **Admin Dashboard UI:** `http://retail-store.local/admin/`
* **Swagger Documentation:** `http://retail-store.local/docs`

---

## 🧪 Load Testing

A pre-configured JMeter test plan (`batches.jmx`) is included in the root directory. To validate the concurrency optimizations:
1. Open Apache JMeter and load `batches.jmx`.
2. The test is configured to ramp up 10,000 threads (users) making atomic purchases.
3. Review the aggregate graph for 95th percentile response times and error rates under heavy contention.

---

## 📂 Project Structure (MVC)

```text
├── app/
│   ├── controllers/   # APIRouters separating Admin, Customer, and Health domains
│   ├── core/          # App initialization and SQLAlchemy Engine configuration
│   ├── models/        # SQLAlchemy ORM definitions
│   ├── schemas/       # Pydantic validation and serialization schemas
│   ├── services/      # Reusable business logic (e.g., JWT generation, Auth)
│   ├── views/         # Jinja2 HTML templates for the frontend
│   └── main.py        # FastAPI app factory
├── k8s/               # Production-grade Kubernetes manifests
├── scripts/           # Utilities for seeding the database
├── tests/             # Comprehensive Pytest test suite
└── batches.jmx        # JMeter load testing configuration
```

---

## ⚡ Execution Command Reference

Below is a reference list of execution commands utilized throughout this project for local dev, Docker, and Minikube deployment.

```bash
# ── Local dev server ─────────────────────────────────────────────────────────
uvicorn app.main:app --reload

# ── Run tests (with SQLite override) ─────────────────────────────────────────
$env:DATABASE_URL="sqlite:///./test_retail.db"; $env:PYTHONPATH="."; pytest tests/test_api.py -v

# ── Run seed scripts locally ─────────────────────────────────────────────────
$env:PYTHONPATH="."; python scripts/create_admin.py
$env:PYTHONPATH="."; python scripts/seed_items.py

# ── Docker Compose ───────────────────────────────────────────────────────────
docker compose up -d --build
docker compose logs -f
docker compose down

# ── Minikube (Windows PowerShell) ────────────────────────────────────────────
minikube start --cpus=6 --memory=8192 --driver=docker
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -t retail-api:latest .
minikube addons enable ingress
kubectl create namespace retail
kubectl apply -f k8s/postgres.yaml -n retail
kubectl apply -f k8s/api.yaml -n retail
kubectl apply -f k8s/ingress.yaml -n retail
kubectl rollout status deployment/retail-api -n retail

# ── Seed K8s DB ──────────────────────────────────────────────────────────────
$pod = kubectl get pods -n retail -l app=retail-api -o jsonpath="{.items[0].metadata.name}"
kubectl exec $pod -n retail -- env PYTHONPATH=/app python scripts/create_admin.py
kubectl exec $pod -n retail -- env PYTHONPATH=/app python scripts/seed_items.py
```
