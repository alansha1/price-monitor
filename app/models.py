"""
SQLAlchemy ORM models.
Product  — the item being tracked (name, category, source URL)
PriceSnapshot — one price reading for a product at a point in time
AlertRule — user-defined threshold: notify when price drops below X
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


# A product is the main item being tracked, such as a food item or grocery product.
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    source_url = Column(Text, nullable=True)
    barcode = Column(String(50), nullable=True, unique=True)
    unit = Column(String(50), nullable=True)          # e.g. "100g", "1L"
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    snapshots = relationship("PriceSnapshot", back_populates="product",
                             cascade="all, delete-orphan")
    alerts = relationship("AlertRule", back_populates="product",
                          cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product id={self.id} name={self.name!r}>"


# A price snapshot stores one recorded price value at a specific time.
class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="EUR")
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String(100), nullable=True)       # e.g. "open_food_facts"

    product = relationship("Product", back_populates="snapshots")

    def __repr__(self):
        return f"<PriceSnapshot product_id={self.product_id} price={self.price}>"


# An alert rule tells the app when a product should be considered too expensive or too cheap.
class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    threshold_price = Column(Float, nullable=False)   # alert when price <= this
    label = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_triggered_at = Column(DateTime, nullable=True)

    product = relationship("Product", back_populates="alerts")

    def __repr__(self):
        return (f"<AlertRule product_id={self.product_id} "
                f"threshold={self.threshold_price}>")
