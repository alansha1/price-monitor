# Price Monitor API

A REST API that tracks product prices over time, stores historical snapshots, and fires threshold alerts when prices drop below a target. Built with **FastAPI**, **SQLAlchemy**, **SQLite** (swappable to Postgres), and **APScheduler** for automated background polling.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Client                           │
│              (curl / Postman / frontend)                │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / JSON
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI  (main.py)                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Router  (routes.py)                │   │
│  │  GET/POST /products                             │   │
│  │  GET/PATCH/DELETE /products/{id}                │   │
│  │  POST/GET  /products/{id}/snapshots             │   │
│  │  GET       /products/{id}/summary               │   │
│  │  GET       /products/{id}/trend                 │   │
│  │  POST/GET  /products/{id}/alerts                │   │
│  │  GET       /products/{id}/alerts/{aid}/check    │   │
│  │  DELETE    /products/{id}/alerts/{aid}          │   │
│  └───────────────────────┬─────────────────────────┘   │
│                          │                              │
│  ┌───────────────────────▼─────────────────────────┐   │
│  │              CRUD layer  (crud.py)               │   │
│  │  Products · Snapshots · Alerts · Analytics       │   │
│  └───────────────────────┬─────────────────────────┘   │
│                          │  SQLAlchemy ORM              │
│  ┌───────────────────────▼─────────────────────────┐   │
│  │           Database  (SQLite / Postgres)          │   │
│  │   products ──< price_snapshots                   │   │
│  │   products ──< alert_rules                       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │        Background Scheduler  (scheduler.py)      │  │
│  │   APScheduler  →  Open Food Facts API (public)   │  │
│  │   Polls every N minutes, writes new snapshots    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.0 |
| Validation | Pydantic v2 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Scheduler | APScheduler 3.10 |
| HTTP client | httpx |
| Tests | pytest + FastAPI TestClient |
| Deploy | Render / Railway |

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-username/price-monitor.git
cd price-monitor
pip install -r requirements.txt

# 2. Configure
cp .env.example .env          # edit DATABASE_URL and POLL_INTERVAL_MINUTES if needed

# 3. Seed demo data
python seed.py

# 4. Run
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## API Reference

### Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/products` | List products (filter: `?category=dairy&active_only=true`) |
| `POST` | `/api/v1/products` | Create a product |
| `GET` | `/api/v1/products/{id}` | Get a product |
| `PATCH` | `/api/v1/products/{id}` | Update a product |
| `DELETE` | `/api/v1/products/{id}` | Delete a product (cascades snapshots + alerts) |

### Price History

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/products/{id}/snapshots` | Record a price manually |
| `GET` | `/api/v1/products/{id}/snapshots` | Retrieve all snapshots |
| `GET` | `/api/v1/products/{id}/summary` | Min / max / avg / latest price |
| `GET` | `/api/v1/products/{id}/trend` | Time-series for charting |

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/products/{id}/alerts` | Create a threshold alert |
| `GET` | `/api/v1/products/{id}/alerts` | List alerts for a product |
| `GET` | `/api/v1/products/{id}/alerts/{aid}/check` | Returns `{"triggered": true/false}` |
| `DELETE` | `/api/v1/products/{id}/alerts/{aid}` | Delete an alert |

### Example — create product + record price + check alert

```bash
# Create
curl -s -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Oat Milk 1L","category":"dairy","barcode":"1234567890"}' | jq .

# Record price
curl -s -X POST http://localhost:8000/api/v1/products/1/snapshots \
  -H "Content-Type: application/json" \
  -d '{"price":1.79}' | jq .

# Price summary
curl -s http://localhost:8000/api/v1/products/1/summary | jq .

# Create alert
curl -s -X POST http://localhost:8000/api/v1/products/1/alerts \
  -H "Content-Type: application/json" \
  -d '{"threshold_price":2.00,"label":"Alert if below €2"}' | jq .

# Check alert
curl -s http://localhost:8000/api/v1/products/1/alerts/1/check | jq .
# → {"triggered": true, "latest_price": 1.79, "threshold_price": 2.0}
```

---

## Background Polling

The scheduler queries the **Open Food Facts** public API (no key required) using each product's barcode. Because Open Food Facts carries nutritional data rather than retail prices, the scheduler derives a synthetic `price` proxy from energy density (kcal/100 g) scaled to a realistic grocery range — useful for demo purposes without needing a paid pricing feed. Swap `fetch_price_from_open_food_facts` in `scheduler.py` for any real pricing API.

---

## Tests

```bash
pytest tests/ -v
# 14 passed in < 1 s (in-memory SQLite, no network calls)
```

---

## Deployment (Render)

1. Push repo to GitHub.
2. New **Web Service** on Render → connect repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add env var `DATABASE_URL` pointing to a Render Postgres instance.
6. Deploy — live URL in ~2 min.

---

## Project Structure

```
price-monitor/
├── app/
│   ├── __init__.py
│   ├── main.py         # FastAPI app, lifespan, CORS
│   ├── database.py     # SQLAlchemy engine + session
│   ├── models.py       # ORM models
│   ├── schemas.py      # Pydantic v2 schemas
│   ├── crud.py         # Database operations
│   ├── routes.py       # API endpoints
│   └── scheduler.py    # Background price polling
├── tests/
│   └── test_products.py
├── seed.py             # Demo data loader
├── requirements.txt
├── .env.example
└── README.md
```
