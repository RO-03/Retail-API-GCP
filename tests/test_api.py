"""
tests/test_api.py
──────────────────────────────────────────────────────────────────────────────
Pytest suite for the Retail Store FastAPI application.

Runs against an isolated SQLite in-memory database (no PostgreSQL needed).
The pipeline sets:  DATABASE_URL=sqlite:///./test_retail.db

Coverage:
  - GET  /health            → 200 + {"status": "ok"}
  - GET  /items             → 200, returns list
  - POST /purchase/{id}     → 200 on success, 409 when out-of-stock
  - POST /admin/login       → 200 with JWT token (valid creds)
  - POST /admin/login       → 401 (bad creds)
  - GET  /admin/items/all   → 200 (with token), 401 (without token)
  - POST /admin/items       → 201 / item added
  - PUT  /admin/items/{id}  → 200 / price + stock updated
  - DELETE /admin/items/{id}→ 200 / item removed
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Override DATABASE_URL before importing any app module ─────────────────────
TEST_DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./test_retail.db")

os.environ["AUTO_CREATE_TABLES"] = "1"  # tests create tables on import of app.main

from app.core.database import engine
import app.models.item as models
from app.services.auth import get_password_hash, get_db
from app.main import app

# ─── Test database setup ─────────────────────────────────────────────────────

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_tables():
    """Wipe all rows before each test for full isolation."""
    db = TestingSessionLocal()
    db.query(models.Order).delete()
    db.query(models.Item).delete()
    db.query(models.Admin).delete()
    db.commit()
    db.close()
    yield


@pytest.fixture
def seeded_item():
    """Insert one item and return its id."""
    db = TestingSessionLocal()
    item = models.Item(name="Test Widget", price=9.99, stock=10)
    db.add(item)
    db.commit()
    db.refresh(item)
    db.close()
    return item.id


@pytest.fixture
def admin_token(seeded_item):
    """Create an admin user and return a valid Bearer token."""
    db = TestingSessionLocal()
    hashed = get_password_hash("secret123")
    admin = models.Admin(username="testadmin", hashed_password=hashed)
    db.add(admin)
    db.commit()
    db.close()

    resp = client.post(
        "/admin/login",
        data={"username": "testadmin", "password": "secret123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ─── Health endpoint ─────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_livez_returns_alive(self):
        resp = client.get("/livez")
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}


# ─── Public customer routes ───────────────────────────────────────────────────

class TestItems:
    def test_list_items_empty(self):
        resp = client.get("/items")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_items_with_stock(self, seeded_item):
        resp = client.get("/items")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == seeded_item
        assert data[0]["stock"] == 10


class TestPurchase:
    def test_purchase_success(self, seeded_item):
        resp = client.post(f"/purchase/{seeded_item}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Purchase successful"

        # Verify stock decremented
        items = client.get("/items").json()
        assert items[0]["stock"] == 9

    def test_purchase_records_exactly_one_order(self, seeded_item):
        client.post(f"/purchase/{seeded_item}")
        db = TestingSessionLocal()
        orders = db.query(models.Order).filter(models.Order.item_id == seeded_item).all()
        db.close()
        assert len(orders) == 1
        assert orders[0].created_at is not None

    def test_failed_purchase_records_no_order(self):
        client.post("/purchase/99999")
        db = TestingSessionLocal()
        count = db.query(models.Order).count()
        db.close()
        assert count == 0

    def test_purchase_out_of_stock(self):
        """Insert item with 0 stock — must return 409."""
        db = TestingSessionLocal()
        item = models.Item(name="Empty Widget", price=1.00, stock=0)
        db.add(item)
        db.commit()
        db.refresh(item)
        item_id = item.id
        db.close()

        resp = client.post(f"/purchase/{item_id}")
        assert resp.status_code == 409

    def test_purchase_nonexistent_item(self):
        resp = client.post("/purchase/99999")
        assert resp.status_code == 409


# ─── Admin auth ───────────────────────────────────────────────────────────────

class TestAdminLogin:
    def test_login_valid_credentials(self, admin_token):
        # admin_token fixture already asserts 200; just confirm token is a string
        assert isinstance(admin_token, str)
        assert len(admin_token) > 0

    def test_login_invalid_credentials(self):
        # Create admin first
        db = TestingSessionLocal()
        admin = models.Admin(username="otheradmin", hashed_password=get_password_hash("pw"))
        db.add(admin)
        db.commit()
        db.close()

        resp = client.post(
            "/admin/login",
            data={"username": "otheradmin", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_login_unknown_user(self):
        resp = client.post(
            "/admin/login",
            data={"username": "ghost", "password": "pass"},
        )
        assert resp.status_code == 401


# ─── Protected admin routes ───────────────────────────────────────────────────

class TestAdminItems:
    def test_get_all_items_requires_auth(self):
        resp = client.get("/admin/items/all")
        assert resp.status_code == 401

    def test_get_all_items_with_token(self, auth_headers, seeded_item):
        resp = client.get("/admin/items/all", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["id"] == seeded_item for item in data)

    def test_add_item(self, auth_headers):
        payload = {"name": "New Gadget", "price": 49.99, "stock": 100}
        resp = client.post("/admin/items", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Item added successfully"

        items = client.get("/admin/items/all", headers=auth_headers).json()
        assert any(i["name"] == "New Gadget" for i in items)

    def test_update_item_price(self, auth_headers, seeded_item):
        resp = client.put(
            f"/admin/items/{seeded_item}",
            json={"price": 19.99},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        items = client.get("/admin/items/all", headers=auth_headers).json()
        updated = next(i for i in items if i["id"] == seeded_item)
        assert float(updated["price"]) == pytest.approx(19.99)

    def test_update_item_restock(self, auth_headers, seeded_item):
        resp = client.put(
            f"/admin/items/{seeded_item}",
            json={"stock_add": 50},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        items = client.get("/admin/items/all", headers=auth_headers).json()
        updated = next(i for i in items if i["id"] == seeded_item)
        assert updated["stock"] == 60   # 10 original + 50 added

    def test_update_nonexistent_item(self, auth_headers):
        resp = client.put(
            "/admin/items/99999",
            json={"price": 5.00},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_delete_item(self, auth_headers, seeded_item):
        resp = client.delete(f"/admin/items/{seeded_item}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Item deleted"

        items = client.get("/admin/items/all", headers=auth_headers).json()
        assert all(i["id"] != seeded_item for i in items)

    def test_delete_nonexistent_item(self, auth_headers):
        resp = client.delete("/admin/items/99999", headers=auth_headers)
        assert resp.status_code == 404
