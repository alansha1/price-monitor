"""
Seed the database with demo products and price history.
Run once after first launch:  python seed.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine
from app import models, crud
from app.schemas import ProductCreate, SnapshotCreate, AlertCreate

# Ensure tables exist
models.Base.metadata.create_all(bind=engine)

PRODUCTS = [
    {"name": "Organic Whole Milk 1L",  "category": "dairy",   "barcode": "5391520025007", "unit": "1L"},
    {"name": "Sliced Wholegrain Bread", "category": "bakery",  "barcode": "5010029017875", "unit": "800g"},
    {"name": "Free-Range Eggs 6-pack",  "category": "eggs",    "barcode": "5391523030105", "unit": "6 pack"},
    {"name": "Cheddar Cheese Block",    "category": "dairy",   "barcode": "5010029098743", "unit": "400g"},
    {"name": "Atlantic Salmon Fillet",  "category": "seafood", "barcode": "5391529047218", "unit": "250g"},
]

# Price history (newest last) per product
PRICE_HISTORY = [
    [2.19, 2.25, 2.29, 2.35],
    [1.79, 1.85, 1.89, 1.95],
    [2.49, 2.55, 2.49, 2.65],
    [3.49, 3.59, 3.49, 3.75],
    [4.99, 5.25, 5.10, 5.49],
]

ALERT_THRESHOLDS = [2.50, 2.00, 2.70, 3.80, 5.50]

db = SessionLocal()
try:
    for i, prod_data in enumerate(PRODUCTS):
        # Skip if barcode already exists
        existing = crud.get_product_by_barcode(db, prod_data["barcode"])
        if existing:
            print(f"  skip  {prod_data['name']} (already seeded)")
            continue

        product = crud.create_product(db, ProductCreate(**prod_data))
        print(f"  + product  {product.name}  (id={product.id})")

        for price in PRICE_HISTORY[i]:
            crud.add_snapshot(db, product.id, SnapshotCreate(price=price, source="seed"))

        alert = crud.create_alert(
            db, product.id,
            AlertCreate(threshold_price=ALERT_THRESHOLDS[i],
                        label=f"Alert if {product.name} drops below €{ALERT_THRESHOLDS[i]:.2f}")
        )
        print(f"    alert set @ €{ALERT_THRESHOLDS[i]:.2f}  (id={alert.id})")

    print("\nSeed complete.")
finally:
    db.close()
