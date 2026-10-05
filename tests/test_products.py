"""
Unit tests for the Products and Prices endpoints.
Uses an in-memory SQLite database — no external services needed.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database as database_module
from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_database_directory_is_created_for_sqlite(tmp_path):
    db_path = tmp_path / "missing" / "nested" / "price_monitor.db"
    database_module.ensure_database_directory(f"sqlite:///{db_path}")
    assert db_path.parent.exists()


# ── Product CRUD ──────────────────────────────────────────────────────────────

def test_create_product():
    resp = client.post("/api/v1/products", json={"name": "Milk 1L", "category": "dairy"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Milk 1L"
    assert data["is_active"] is True


def test_list_products_empty():
    resp = client.get("/api/v1/products")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_products_with_category_filter():
    client.post("/api/v1/products", json={"name": "Milk", "category": "dairy"})
    client.post("/api/v1/products", json={"name": "Bread", "category": "bakery"})
    resp = client.get("/api/v1/products?category=dairy")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Milk" in names
    assert "Bread" not in names


def test_get_product_not_found():
    resp = client.get("/api/v1/products/999")
    assert resp.status_code == 404


def test_update_product():
    create = client.post("/api/v1/products", json={"name": "Old Name"})
    pid = create.json()["id"]
    resp = client.patch(f"/api/v1/products/{pid}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_delete_product():
    create = client.post("/api/v1/products", json={"name": "To Delete"})
    pid = create.json()["id"]
    resp = client.delete(f"/api/v1/products/{pid}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/products/{pid}").status_code == 404


def test_duplicate_barcode_rejected():
    client.post("/api/v1/products", json={"name": "A", "barcode": "123"})
    resp = client.post("/api/v1/products", json={"name": "B", "barcode": "123"})
    assert resp.status_code == 409


# ── Price Snapshots ───────────────────────────────────────────────────────────

def _create_product(name="Test Product"):
    return client.post("/api/v1/products", json={"name": name}).json()


def test_add_and_retrieve_snapshot():
    pid = _create_product()["id"]
    client.post(f"/api/v1/products/{pid}/snapshots", json={"price": 2.49})
    resp = client.get(f"/api/v1/products/{pid}/snapshots")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["price"] == 2.49


def test_snapshot_invalid_price():
    pid = _create_product()["id"]
    resp = client.post(f"/api/v1/products/{pid}/snapshots", json={"price": -1.0})
    assert resp.status_code == 422


def test_price_summary():
    pid = _create_product()["id"]
    for price in [1.0, 2.0, 3.0]:
        client.post(f"/api/v1/products/{pid}/snapshots", json={"price": price})
    resp = client.get(f"/api/v1/products/{pid}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["min_price"] == 1.0
    assert data["max_price"] == 3.0
    assert data["avg_price"] == 2.0
    assert data["snapshot_count"] == 3


def test_price_trend():
    pid = _create_product()["id"]
    for price in [1.5, 2.5]:
        client.post(f"/api/v1/products/{pid}/snapshots", json={"price": price})
    resp = client.get(f"/api/v1/products/{pid}/trend")
    assert resp.status_code == 200
    history = resp.json()["history"]
    assert len(history) == 2
    assert history[0]["price"] == 1.5


# ── Alerts ────────────────────────────────────────────────────────────────────

def test_create_and_check_alert_triggered():
    pid = _create_product()["id"]
    client.post(f"/api/v1/products/{pid}/snapshots", json={"price": 1.00})
    alert = client.post(
        f"/api/v1/products/{pid}/alerts", json={"threshold_price": 2.00}
    ).json()
    resp = client.get(f"/api/v1/products/{pid}/alerts/{alert['id']}/check")
    assert resp.status_code == 200
    assert resp.json()["triggered"] is True


def test_alert_not_triggered():
    pid = _create_product()["id"]
    client.post(f"/api/v1/products/{pid}/snapshots", json={"price": 5.00})
    alert = client.post(
        f"/api/v1/products/{pid}/alerts", json={"threshold_price": 2.00}
    ).json()
    resp = client.get(f"/api/v1/products/{pid}/alerts/{alert['id']}/check")
    assert resp.json()["triggered"] is False


def test_delete_alert():
    pid = _create_product()["id"]
    alert = client.post(
        f"/api/v1/products/{pid}/alerts", json={"threshold_price": 1.50}
    ).json()
    resp = client.delete(f"/api/v1/products/{pid}/alerts/{alert['id']}")
    assert resp.status_code == 204
