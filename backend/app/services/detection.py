"""Change detection engine.

Compares the latest snapshot of a product with previous state(s) and emits
``ChangeEvent`` records. Runs inside the scraping worker but is kept as a
pure module so it can be unit-tested exhaustively.

An important rule inherited from the pipeline: a *failed* scrape produces no
snapshot, therefore it can never generate a price/availability change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Evt:
    event_type: str
    importance: str
    old_state: dict[str, Any]
    new_state: dict[str, Any]

    @property
    def title(self) -> str:
        from app.models import CHANGE_EVENT_TITLES

        return CHANGE_EVENT_TITLES.get(self.event_type, self.event_type.replace("_", " "))


@dataclass
class SnapshotView:
    """Minimal immutable view of a snapshot for the detector."""

    price: float | None = None
    currency: str | None = None
    previous_price: float | None = None
    availability: str | None = None
    in_promotion: bool = False
    product_name: str | None = None
    product_sku: str | None = None
    ean: str | None = None

    @classmethod
    def from_orm(cls, snap: Any) -> "SnapshotView":
        return cls(
            price=float(snap.price) if snap.price is not None else None,
            currency=snap.currency,
            previous_price=float(snap.previous_price) if snap.previous_price is not None else None,
            availability=snap.availability,
            in_promotion=bool(snap.in_promotion),
            product_name=snap.product_name,
            product_sku=snap.product_sku,
            ean=snap.ean,
        )


AVAILABILITY_MAP = {
    ("in_stock", "out_of_stock"): ("out_of_stock", "medium"),
    ("in_stock", "preorder"): ("out_of_stock", "medium"),
    ("out_of_stock", "in_stock"): ("in_stock", "low"),
    ("preorder", "in_stock"): ("in_stock", "low"),
    ("preorder", "out_of_stock"): ("out_of_stock", "low"),
    ("out_of_stock", "preorder"): ("out_of_stock", "low"),
}


def detect(
    previous: SnapshotView | None,
    current: SnapshotView,
    older_history: list[SnapshotView] | None = None,
) -> list[Evt]:
    """Return the list of changes between consecutive snapshots.

    ``older_history`` is an optional list of snapshots *older than the
    previous one* (newest first), used to detect "return to a previous price".
    """
    events: list[Evt] = []

    # ---------- price ----------
    prev_price = previous.price if previous else None
    cur_price = current.price
    if prev_price is not None and cur_price is not None and prev_price != cur_price:
        if cur_price < prev_price:
            events.append(Evt("price_drop", "high", {"price": prev_price, "currency": previous.currency},
                              {"price": cur_price, "currency": current.currency}))
        else:
            # "return to an old price": current equals a price seen earlier (not the last one)
            back = False
            if older_history:
                back = any(o.price == cur_price for o in older_history if o.price is not None)
            if back:
                events.append(Evt("price_back", "medium",
                                  {"price": prev_price, "currency": previous.currency},
                                  {"price": cur_price, "currency": current.currency}))
            else:
                events.append(Evt("price_rise", "medium",
                                  {"price": prev_price, "currency": previous.currency},
                                  {"price": cur_price, "currency": current.currency}))
    elif prev_price is None and cur_price is not None:
        # First ever priced snapshot — not an event.
        pass

    # ---------- availability ----------
    prev_av = previous.availability if previous else None
    cur_av = current.availability
    if prev_av != cur_av and cur_av and prev_av:
        event_type, importance = AVAILABILITY_MAP.get((prev_av, cur_av), (None, None))
        if event_type:
            events.append(Evt(event_type, importance, {"availability": prev_av}, {"availability": cur_av}))

    # ---------- promotion ----------
    prev_promo = (previous.in_promotion, previous.previous_price) if previous else (False, None)
    cur_promo = (current.in_promotion, current.previous_price)
    if prev_promo != cur_promo:
        if cur_promo[0] and not prev_promo[0]:
            events.append(Evt("promotion_start", "high",
                              {"in_promotion": False, "old_price": prev_promo[1]},
                              {"in_promotion": True, "old_price": cur_promo[1]}))
        elif prev_promo[0] and not cur_promo[0]:
            events.append(Evt("promotion_end", "medium",
                              {"in_promotion": True, "old_price": prev_promo[1]},
                              {"in_promotion": False}))
        else:
            events.append(Evt("promotion_change", "low",
                              {"old_price": prev_promo[1]},
                              {"old_price": cur_promo[1]}))

    # ---------- product info ----------
    if previous and previous.product_name and current.product_name:
        if previous.product_name != current.product_name:
            events.append(Evt("product_info", "low",
                              {"name": previous.product_name}, {"name": current.product_name}))
    if previous and previous.product_sku and current.product_sku:
        if previous.product_sku != current.product_sku:
            events.append(Evt("product_info", "low",
                              {"sku": previous.product_sku}, {"sku": current.product_sku}))
    if previous and previous.ean and current.ean:
        if previous.ean != current.ean:
            events.append(Evt("product_info", "low",
                              {"ean": previous.ean}, {"ean": current.ean}))

    return events


def best_importance(events: list[Evt]) -> str:
    order = {"high": 3, "medium": 2, "low": 1}
    return max((e.importance for e in events), key=order.get, default="low")