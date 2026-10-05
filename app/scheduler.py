"""
Background scheduler — fetches prices automatically at a set interval.
Uses APScheduler. In production this would call real retailer APIs or scrapers;
here it pulls from Open Food Facts (free, no API key required).
"""

import logging
import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import crud, schemas

logger = logging.getLogger(__name__)

OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"


# Call the Open Food Facts API and turn the returned data into a demo price value.
def fetch_price_from_open_food_facts(barcode: str) -> float | None:
    """
    Open Food Facts doesn't carry live prices, but it carries nutriscores and
    product metadata. For demo purposes we derive a synthetic 'price' from
    the product's energy value so the scheduler has a real HTTP call to make.

    In a real deployment this would call a supermarket API or scraper endpoint.
    """
    try:
        url = OPEN_FOOD_FACTS_URL.format(barcode=barcode)
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        product = data.get("product", {})
        nutriments = product.get("nutriments", {})
        # Use energy-kcal per 100g as a proxy value (demo only)
        energy = nutriments.get("energy-kcal_100g")
        if energy:
            # Map kcal to a plausible price range (€0.50 – €5.00)
            price = round(min(max(energy / 100, 0.5), 5.0), 2)
            return price
    except Exception as exc:
        logger.warning("Failed to fetch data for barcode %s: %s", barcode, exc)
    return None


# Run one check for all active products and save new prices to the database.
def poll_prices():
    """
    Called by the scheduler on each tick.
    Iterates active products that have a barcode, fetches the latest price,
    and writes a new PriceSnapshot to the database.
    """
    db: Session = SessionLocal()
    try:
        products = crud.list_products(db, active_only=True)
        for product in products:
            if not product.barcode:
                continue
            price = fetch_price_from_open_food_facts(product.barcode)
            if price is not None:
                crud.add_snapshot(
                    db,
                    product.id,
                    schemas.SnapshotCreate(price=price, source="open_food_facts"),
                )
                logger.info("Recorded price %.2f for product %s", price, product.name)
    finally:
        db.close()


# Start the timer that checks prices automatically in the background.
def start_scheduler(interval_minutes: int = 60) -> BackgroundScheduler:
    """Start the background polling scheduler and return it."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        poll_prices,
        trigger="interval",
        minutes=interval_minutes,
        id="price_poll",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Price scheduler started — polling every %d minutes.", interval_minutes)
    return scheduler
