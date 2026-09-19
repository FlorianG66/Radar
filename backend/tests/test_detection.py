from __future__ import annotations

from app.services.detection import SnapshotView, detect


def test_no_change_produces_no_event() -> None:
    prev = SnapshotView(price=10.0, currency="EUR", availability="in_stock", in_promotion=False)
    cur = SnapshotView(price=10.0, currency="EUR", availability="in_stock", in_promotion=False)
    assert detect(prev, cur) == []


def test_price_drop_is_high_importance() -> None:
    prev = SnapshotView(price=12.0, currency="EUR")
    cur = SnapshotView(price=9.5, currency="EUR")
    events = detect(prev, cur)
    assert len(events) == 1
    evt = events[0]
    assert evt.event_type == "price_drop"
    assert evt.importance == "high"
    assert evt.old_state == {"price": 12.0, "currency": "EUR"}
    assert evt.new_state == {"price": 9.5, "currency": "EUR"}


def test_price_rise_is_medium_importance() -> None:
    prev = SnapshotView(price=9.5, currency="EUR")
    cur = SnapshotView(price=12.0, currency="EUR")
    events = detect(prev, cur)
    assert [e.event_type for e in events] == ["price_rise"]
    assert events[0].importance == "medium"


def test_return_to_old_price_is_price_back() -> None:
    older = [SnapshotView(price=8.0, currency="EUR")]
    prev = SnapshotView(price=7.0, currency="EUR")
    cur = SnapshotView(price=8.0, currency="EUR")
    events = detect(prev, cur, older_history=older)
    assert [e.event_type for e in events] == ["price_back"]


def test_promotion_start() -> None:
    prev = SnapshotView(price=12.0, in_promotion=False, previous_price=None)
    cur = SnapshotView(price=9.0, in_promotion=True, previous_price=12.0)
    events = detect(prev, cur)
    types = [e.event_type for e in events]
    assert "promotion_start" in types and "price_drop" in types
    promo = next(e for e in events if e.event_type == "promotion_start")
    assert promo.importance == "high"


def test_out_of_stock_event() -> None:
    prev = SnapshotView(availability="in_stock")
    cur = SnapshotView(availability="out_of_stock")
    events = detect(prev, cur)
    assert [e.event_type for e in events] == ["out_of_stock"]
    assert events[0].importance == "medium"


def test_first_priced_snapshot_is_not_an_event() -> None:
    cur = SnapshotView(price=42.0, currency="EUR")
    assert detect(None, cur) == []