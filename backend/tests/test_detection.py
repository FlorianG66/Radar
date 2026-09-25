"""Change detection engine units."""
from app.services.detection import Evt, SnapshotView, detect, best_importance


def s(**kw):
    base = dict(price=None, previous_price=None, availability=None, in_promotion=False,
                product_name=None, product_sku=None, ean=None)
    base.update(kw)
    return SnapshotView(**base)


class TestPrice:
    def test_drop(self):
        events = detect(s(price=649.0), s(price=599.0))
        assert [e.event_type for e in events] == ["price_drop"]
        assert events[0].importance == "high"

    def test_rise(self):
        events = detect(s(price=599.0), s(price=649.0))
        assert events[0].event_type == "price_rise"
        assert events[0].importance == "medium"

    def test_no_change(self):
        assert detect(s(price=649.0), s(price=649.0)) == []

    def test_back_to_previous_price(self):
        # previous=649, current=599, olderHistory contained 599 before
        older = [s(price=599.0), s(price=649.0)]
        events = detect(s(price=649.0), s(price=599.0), older)
        assert [e.event_type for e in events] == ["price_back"]

    def test_first_snapshot_no_event(self):
        assert detect(None, s(price=649.0)) == []

    def test_price_gap_small_no_movement_ignored(self):
        events = detect(s(price=649.0, currency="EUR"), s(price=649.0, currency="EUR"))
        assert events == []


class TestAvailability:
    def test_to_out_of_stock(self):
        events = detect(s(availability="in_stock"), s(availability="out_of_stock"))
        assert events[0].event_type == "out_of_stock"
        assert events[0].importance == "medium"

    def test_back_in_stock(self):
        events = detect(s(availability="out_of_stock"), s(availability="in_stock"))
        assert events[0].event_type == "in_stock"
        assert events[0].importance == "low"

    def test_same(self):
        assert detect(s(availability="in_stock"), s(availability="in_stock")) == []

    def test_first_availability_seen(self):
        assert detect(None, s(availability="in_stock")) == []


class TestPromotion:
    def test_start(self):
        events = detect(s(price=649.0, in_promotion=False), s(price=599.0, in_promotion=True, previous_price=649.0))
        assert any(e.event_type == "promotion_start" for e in events)
        assert events[0].importance == "high"

    def test_end(self):
        events = detect(s(price=499.0, in_promotion=True, previous_price=599.0),
                        s(price=599.0, in_promotion=False))
        assert any(e.event_type == "promotion_end" for e in events)

    def test_change(self):
        events = detect(s(price=499.0, in_promotion=True, previous_price=599.0),
                        s(price=479.0, in_promotion=True, previous_price=599.0))
        assert any(e.event_type == "promotion_change" for e in events)
        assert all(e.importance == "low" for e in events if e.event_type == "promotion_change")


class TestProductInfo:
    def test_name_change(self):
        events = detect(s(product_name="Ancien"), s(product_name="Nouveau"))
        assert events[0].event_type == "product_info"
        assert events[0].old_state == {"name": "Ancien"}

    def test_ean_change(self):
        events = detect(s(ean="1111111111111"), s(ean="3333333333333"))
        assert events[0].event_type == "product_info"

    def test_unknown_products_no_event(self):
        assert detect(s(product_name=None, ean=None, product_sku=None),
                      s(product_name=None, ean=None, product_sku=None)) == []


class TestImportance:
    def test_highest_wins(self):
        evts = [Evt("promotion_change", "low", {}, {}), Evt("price_drop", "high", {}, {})]
        assert best_importance(evts) == "high"


class TestFailedScrapeProducesNothing:
    def test_none_previous(self):
        assert detect(None, s(availability="out_of_stock")) == []