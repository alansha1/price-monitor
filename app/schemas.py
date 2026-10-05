"""
Pydantic schemas — request/response validation and serialisation.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator


# ── Product ──────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    category: Optional[str] = None
    source_url: Optional[str] = None
    barcode: Optional[str] = None
    unit: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    unit: Optional[str] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: Optional[str]
    source_url: Optional[str]
    barcode: Optional[str]
    unit: Optional[str]
    is_active: bool
    created_at: datetime


# ── PriceSnapshot ─────────────────────────────────────────────────────────────

class SnapshotCreate(BaseModel):
    price: float
    currency: str = "EUR"
    source: Optional[str] = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("price must be greater than zero")
        return v


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    price: float
    currency: str
    recorded_at: datetime
    source: Optional[str]


# ── AlertRule ─────────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    threshold_price: float
    label: Optional[str] = None

    @field_validator("threshold_price")
    @classmethod
    def threshold_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("threshold_price must be greater than zero")
        return v


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    threshold_price: float
    label: Optional[str]
    is_active: bool
    created_at: datetime
    last_triggered_at: Optional[datetime]


# ── Analytics responses ───────────────────────────────────────────────────────

class PriceSummary(BaseModel):
    product_id: int
    product_name: str
    latest_price: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]
    avg_price: Optional[float]
    snapshot_count: int
    currency: str = "EUR"


class AlertCheck(BaseModel):
    product_id: int
    product_name: str
    threshold_price: float
    latest_price: Optional[float]
    triggered: bool
    message: str


class TrendPoint(BaseModel):
    recorded_at: datetime
    price: float


class PriceTrend(BaseModel):
    product_id: int
    product_name: str
    currency: str
    history: List[TrendPoint]
