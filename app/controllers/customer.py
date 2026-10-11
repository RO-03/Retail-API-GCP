from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
import app.models.item as models
from app.core.database import get_db

router = APIRouter(tags=["customer"])

# Templates are initialised in app/main.py and injected via the request object.
# The router itself references the shared Jinja2Templates instance set at startup.
templates: Jinja2Templates | None = None


def set_templates(t: Jinja2Templates):
    """Called once from app/main.py to inject the templates instance."""
    global templates
    templates = t


# ── Page view routes ──────────────────────────────────────────────────────────

@router.get("/")
def render_customer_page(request: Request):
    """Serves the Customer Storefront."""
    return templates.TemplateResponse(request=request, name="customer.html")


# ── Public API routes ─────────────────────────────────────────────────────────

@router.get("/items")
def view_items(db: Session = Depends(get_db)):
    """Customer: View all available items."""
    return db.query(models.Item).order_by(models.Item.id).all()


@router.post("/purchase/{item_id}")
def purchase_item(item_id: int, db: Session = Depends(get_db)):
    """Customer: High-concurrency atomic purchase."""
    # Raw SQL for atomic update to prevent race conditions during stress tests
    result = db.execute(
        text("UPDATE items SET stock = stock - 1 WHERE id = :id AND stock > 0 RETURNING id"),
        {"id": item_id}
    ).fetchone()

    if not result:
        raise HTTPException(status_code=409, detail="Item out of stock or does not exist")

    # Same transaction as the stock decrement: both are committed together or neither is.
    db.add(models.Order(item_id=item_id))
    db.commit()
    return {"message": "Purchase successful"}
