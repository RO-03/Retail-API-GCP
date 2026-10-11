import os
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from app.core.database import engine
import app.models.item as models
from app.controllers import health, customer, admin

# ── Optional table creation at import time (local / Docker / K8s / tests only) ──
# On Cloud Run leave AUTO_CREATE_TABLES unset and run scripts/init_db.py as a Job instead,
# so concurrent instances and workers do not race to create tables.
if os.getenv("AUTO_CREATE_TABLES") == "1":
    models.Base.metadata.create_all(bind=engine)

# ── FastAPI application instance ──────────────────────────────────────────────
app = FastAPI(title="Retail Store API")

# ── Jinja2 Templates — point at the View layer ────────────────────────────────
templates = Jinja2Templates(directory="app/views")

# Inject the shared templates instance into controllers that serve HTML pages
customer.set_templates(templates)
admin.set_templates(templates)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(customer.router)
app.include_router(admin.router)
