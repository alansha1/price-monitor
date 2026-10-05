"""
FastAPI route handlers — thin layer that delegates all logic to crud.py.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter()


# ── Products ──────────────────────────────────────────────────────────────────

# Return all products, with optional filtering by category and activity.
@router.get("/products", response_model=List[schemas.ProductOut], tags=["Products"])
def list_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Return only active products"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List all tracked products, with optional category filter."""
    return crud.list_products(db, category=category, active_only=active_only,
                               skip=skip, limit=limit)


# Create a new product entry in the database.
@router.post("/products", response_model=schemas.ProductOut, status_code=201,
             tags=["Products"])
def create_product(data: schemas.ProductCreate, db: Session = Depends(get_db)):
    """Add a new product to track."""
    if data.barcode:
        existing = crud.get_product_by_barcode(db, data.barcode)
        if existing:
            raise HTTPException(status_code=409,
                                detail=f"Product with barcode {data.barcode!r} already exists.")
    return crud.create_product(db, data)


# Fetch one product using its unique ID.
@router.get("/products/{product_id}", response_model=schemas.ProductOut,
            tags=["Products"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a single product by ID."""
    product = crud.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


# Update a product's details without replacing the whole record.
@router.patch("/products/{product_id}", response_model=schemas.ProductOut,
              tags=["Products"])
def update_product(product_id: int, data: schemas.ProductUpdate,
                   db: Session = Depends(get_db)):
    """Partially update a product."""
    product = crud.update_product(db, product_id, data)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


# Remove a product and its related records.
@router.delete("/products/{product_id}", status_code=204, tags=["Products"])
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Delete a product and all its price history."""
    if not crud.delete_product(db, product_id):
        raise HTTPException(status_code=404, detail="Product not found.")


# ── Price Snapshots ───────────────────────────────────────────────────────────

# Save a new price reading for the selected product.
@router.post("/products/{product_id}/snapshots",
             response_model=schemas.SnapshotOut, status_code=201,
             tags=["Prices"])
def add_snapshot(product_id: int, data: schemas.SnapshotCreate,
                 db: Session = Depends(get_db)):
    """Record a new price for a product."""
    if not crud.get_product(db, product_id):
        raise HTTPException(status_code=404, detail="Product not found.")
    return crud.add_snapshot(db, product_id, data)


# Get the price history for one product.
@router.get("/products/{product_id}/snapshots",
            response_model=List[schemas.SnapshotOut], tags=["Prices"])
def get_snapshots(
    product_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get price history for a product (most recent first)."""
    if not crud.get_product(db, product_id):
        raise HTTPException(status_code=404, detail="Product not found.")
    return crud.get_snapshots(db, product_id, limit=limit)


# Calculate the summary statistics for a product's price history.
@router.get("/products/{product_id}/summary",
            response_model=schemas.PriceSummary, tags=["Analytics"])
def get_price_summary(product_id: int, db: Session = Depends(get_db)):
    """Return min / max / avg / latest price statistics for a product."""
    summary = crud.get_price_summary(db, product_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Product not found.")
    return summary


# Show the product's price trend over time.
@router.get("/products/{product_id}/trend",
            response_model=schemas.PriceTrend, tags=["Analytics"])
def get_price_trend(
    product_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Return time-series price trend for a product."""
    trend = crud.get_price_trend(db, product_id, limit=limit)
    if not trend:
        raise HTTPException(status_code=404, detail="Product not found.")
    return trend


# ── Alert Rules ───────────────────────────────────────────────────────────────

# Create a rule that warns when the price drops below a threshold.
@router.post("/products/{product_id}/alerts",
             response_model=schemas.AlertOut, status_code=201, tags=["Alerts"])
def create_alert(product_id: int, data: schemas.AlertCreate,
                 db: Session = Depends(get_db)):
    """Create a price alert rule for a product."""
    if not crud.get_product(db, product_id):
        raise HTTPException(status_code=404, detail="Product not found.")
    return crud.create_alert(db, product_id, data)


# Show all alert rules for a product.
@router.get("/products/{product_id}/alerts",
            response_model=List[schemas.AlertOut], tags=["Alerts"])
def list_alerts(product_id: int, db: Session = Depends(get_db)):
    """List all alert rules for a product."""
    if not crud.get_product(db, product_id):
        raise HTTPException(status_code=404, detail="Product not found.")
    return crud.list_alerts(db, product_id)


# Check whether the latest price has triggered a specific alert.
@router.get("/products/{product_id}/alerts/{alert_id}/check",
            response_model=schemas.AlertCheck, tags=["Alerts"])
def check_alert(product_id: int, alert_id: int, db: Session = Depends(get_db)):
    """Check whether a specific alert has been triggered by the latest price."""
    result = crud.check_alert(db, product_id, alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert or product not found.")
    return result


# Delete one alert rule from the system.
@router.delete("/products/{product_id}/alerts/{alert_id}",
               status_code=204, tags=["Alerts"])
def delete_alert(product_id: int, alert_id: int, db: Session = Depends(get_db)):
    """Delete an alert rule."""
    if not crud.delete_alert(db, alert_id):
        raise HTTPException(status_code=404, detail="Alert not found.")
