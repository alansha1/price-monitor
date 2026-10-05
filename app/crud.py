"""
CRUD operations — all raw SQL/ORM logic lives here, away from route handlers.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas


# ── Products ──────────────────────────────────────────────────────────────────

# Fetch one product by its unique ID.
def get_product(db: Session, product_id: int) -> Optional[models.Product]:
    return db.query(models.Product).filter(models.Product.id == product_id).first()


# Find a product using its barcode, if one exists.
def get_product_by_barcode(db: Session, barcode: str) -> Optional[models.Product]:
    return db.query(models.Product).filter(models.Product.barcode == barcode).first()


# Return products, with optional filters for category and active status.
def list_products(
    db: Session,
    category: Optional[str] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
) -> List[models.Product]:
    q = db.query(models.Product)
    if active_only:
        q = q.filter(models.Product.is_active == True)
    if category:
        q = q.filter(models.Product.category == category)
    return q.offset(skip).limit(limit).all()


# Create and save a new product in the database.
def create_product(db: Session, data: schemas.ProductCreate) -> models.Product:
    product = models.Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


# Update only the fields the user provides.
def update_product(
    db: Session, product_id: int, data: schemas.ProductUpdate
) -> Optional[models.Product]:
    product = get_product(db, product_id)
    if not product:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


# Remove a product from the database.
def delete_product(db: Session, product_id: int) -> bool:
    product = get_product(db, product_id)
    if not product:
        return False
    db.delete(product)
    db.commit()
    return True


# ── Price Snapshots ───────────────────────────────────────────────────────────

# Save a new price reading for a product.
def add_snapshot(
    db: Session, product_id: int, data: schemas.SnapshotCreate
) -> models.PriceSnapshot:
    snap = models.PriceSnapshot(product_id=product_id, **data.model_dump())
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


# Read the saved price history for one product.
def get_snapshots(
    db: Session,
    product_id: int,
    limit: int = 100,
) -> List[models.PriceSnapshot]:
    return (
        db.query(models.PriceSnapshot)
        .filter(models.PriceSnapshot.product_id == product_id)
        .order_by(models.PriceSnapshot.recorded_at.desc())
        .limit(limit)
        .all()
    )


# Get the newest recorded price for a product.
def get_latest_snapshot(
    db: Session, product_id: int
) -> Optional[models.PriceSnapshot]:
    return (
        db.query(models.PriceSnapshot)
        .filter(models.PriceSnapshot.product_id == product_id)
        .order_by(models.PriceSnapshot.recorded_at.desc())
        .first()
    )


# Calculate summary values such as average, min, and max price.
def get_price_summary(db: Session, product_id: int) -> Optional[schemas.PriceSummary]:
    product = get_product(db, product_id)
    if not product:
        return None

    agg = (
        db.query(
            func.min(models.PriceSnapshot.price).label("min_price"),
            func.max(models.PriceSnapshot.price).label("max_price"),
            func.avg(models.PriceSnapshot.price).label("avg_price"),
            func.count(models.PriceSnapshot.id).label("count"),
        )
        .filter(models.PriceSnapshot.product_id == product_id)
        .one()
    )

    latest = get_latest_snapshot(db, product_id)

    return schemas.PriceSummary(
        product_id=product_id,
        product_name=product.name,
        latest_price=latest.price if latest else None,
        min_price=round(agg.min_price, 2) if agg.min_price else None,
        max_price=round(agg.max_price, 2) if agg.max_price else None,
        avg_price=round(agg.avg_price, 2) if agg.avg_price else None,
        snapshot_count=agg.count,
    )


# Build a simple time-based trend using the product's saved price history.
def get_price_trend(
    db: Session, product_id: int, limit: int = 50
) -> Optional[schemas.PriceTrend]:
    product = get_product(db, product_id)
    if not product:
        return None

    snaps = (
        db.query(models.PriceSnapshot)
        .filter(models.PriceSnapshot.product_id == product_id)
        .order_by(models.PriceSnapshot.recorded_at.asc())
        .limit(limit)
        .all()
    )

    return schemas.PriceTrend(
        product_id=product_id,
        product_name=product.name,
        currency="EUR",
        history=[
            schemas.TrendPoint(recorded_at=s.recorded_at, price=s.price)
            for s in snaps
        ],
    )


# ── Alert Rules ───────────────────────────────────────────────────────────────

# Create a new alert rule for a product.
def create_alert(
    db: Session, product_id: int, data: schemas.AlertCreate
) -> models.AlertRule:
    alert = models.AlertRule(product_id=product_id, **data.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


# Get all alert rules connected to one product.
def list_alerts(db: Session, product_id: int) -> List[models.AlertRule]:
    return (
        db.query(models.AlertRule)
        .filter(models.AlertRule.product_id == product_id)
        .all()
    )


# Check whether the latest price has triggered a specific alert.
def check_alert(
    db: Session, product_id: int, alert_id: int
) -> Optional[schemas.AlertCheck]:
    alert = (
        db.query(models.AlertRule)
        .filter(
            models.AlertRule.id == alert_id,
            models.AlertRule.product_id == product_id,
        )
        .first()
    )
    if not alert:
        return None

    product = get_product(db, product_id)
    latest = get_latest_snapshot(db, product_id)
    latest_price = latest.price if latest else None
    triggered = latest_price is not None and latest_price <= alert.threshold_price

    if triggered:
        alert.last_triggered_at = datetime.utcnow()
        db.commit()

    return schemas.AlertCheck(
        product_id=product_id,
        product_name=product.name,
        threshold_price=alert.threshold_price,
        latest_price=latest_price,
        triggered=triggered,
        message=(
            f"ALERT: {product.name} is now €{latest_price:.2f} "
            f"(below threshold €{alert.threshold_price:.2f})"
            if triggered
            else f"No alert: current price €{latest_price} is above threshold €{alert.threshold_price}"
        ),
    )


# Remove one alert rule from the database.
def delete_alert(db: Session, alert_id: int) -> bool:
    alert = db.query(models.AlertRule).filter(models.AlertRule.id == alert_id).first()
    if not alert:
        return False
    db.delete(alert)
    db.commit()
    return True
