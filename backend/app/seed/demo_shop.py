"""Small demo shop for local development & automated tests.

Serves product pages on http://localhost:8080 whose state evolves over time
(price drops, out-of-stock, promotions...) so that the full Radar loop can be
demonstrated without any external website.

The pages expose ``data-radar-*`` attributes consumed by
``DemoShopExtractor`` and are intentionally simple HTML.
"""
from __future__ import annotations

import time
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = "localhost"
PORT = 8080

PRODUCTS = {
    "/p/rtx-5070": {"name": "RTX 5070 12GB", "sku": "RTX5070-12G", "ean": "3700993930001"},
    "/p/ssd-990-pro": {"name": "Samsung 990 Pro 2TB", "sku": "MZ-V9P2T0BW", "ean": "8592978480022"},
    "/p/monitor-27": {"name": "Écran 27\" 4K UHD", "sku": "S2722QC", "ean": "3760273660001"},
    "/p/keychron-k8": {"name": "Keychron K8 Pro", "sku": "K8P-B3", "ean": "6933893800005"},
    "/p/coffee-maker": {"name": "Machine café espresso", "sku": "ECAM-22", "ean": "3341738430004"},
    "/p/js-product": {"name": "Casque sans fil ANC", "sku": "ANC-700", "ean": "3700993900002"},
}

# Time-based phases so a running demo naturally produces changes.
_PRICE_CYCLE = 360          # seconds
_PROMO_CYCLE = 540          # seconds
_STOCK_CYCLE = 300          # seconds


def _phase(cycle: int, offset: int = 0) -> int:
    return int((time.time() + offset) // cycle) % 2


def _state(path: str) -> dict:
    base = PRODUCTS.get(path, {})
    name = base.get("name", "Produit de démonstration")
    out: dict = {"name": name, "price": 99.0, "old_price": None, "availability": "in_stock",
                 "stock": 10, "promo": False, "shipping": 4.99}

    if path == "/p/rtx-5070":
        out["price"] = 599.0 if _phase(_PRICE_CYCLE) else 649.0
        out["stock"] = 5
    elif path == "/p/ssd-990-pro":
        out["price"] = 239.9
        out["availability"] = "out_of_stock" if _phase(_STOCK_CYCLE) else "in_stock"
        out["stock"] = 0 if out["availability"] == "out_of_stock" else 20
    elif path == "/p/monitor-27":
        promo = bool(_phase(_PROMO_CYCLE))
        if promo:
            out["price"] = 499.0
            out["old_price"] = 599.0
            out["promo"] = True
        else:
            out["price"] = 599.0
            out["old_price"] = None
            out["promo"] = False
    elif path == "/p/keychron-k8":
        out["price"] = 129.0
        out["shipping"] = 0.0
    elif path == "/p/coffee-maker":
        out["price"] = 89.99
    elif path == "/p/js-product":
        out["price"] = 179.0
        out["availability"] = "in_stock"
    return out


def _page(path: str) -> str:
    s = _state(path)
    sku = PRODUCTS.get(path, {}).get("sku", "")
    ean = PRODUCTS.get(path, {}).get("ean", "")
    old = (
        f'<s data-radar="old-price">{s["old_price"]:.2f} €</s>'
        if s["old_price"] is not None else ""
    )
    overall = f'{old} <span data-radar="price" content="{s["price"]:.2f}">{s["price"]:.2f} €</span>'
    promo = (
        f'<span data-radar="promo" value="true">En promotion</span>'
        if s["promo"] else ""
    )
    stock = (
        f'<span data-radar="stock" data-quantity="{s["stock"]}">{s["stock"]} en stock</span>'
        if s["availability"] == "in_stock" else '<span data-radar="stock">—</span>'
    )
    availability = (
        '<span data-radar="availability" data-state="in_stock">En stock</span>'
        if s["availability"] == "in_stock"
        else '<span data-radar="availability" data-state="out_of_stock">Rupture de stock</span>'
    )
    img = "https://picsum.photos/seed/radar/400/300"
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>{escape(s['name'])}</title>
<meta property="og:title" content="{escape(s['name'])}">
<meta property="og:price:amount" content="{s['price']:.2f}">
<meta property="og:price:currency" content="EUR">
</head><body>
<h1 data-radar="name">{escape(s['name'])}</h1>
<img data-radar="image" src="{img}" alt="{escape(s['name'])}">
<p>{overall}</p>
{promo}
<p>{availability}</p>
<p>{stock}</p>
<p>Livraison : <span data-radar="shipping">{s['shipping']:.2f} €</span></p>
<p data-radar="sku">Réf : {sku}</p>
<p data-radar="ean">EAN : {ean}</p>
<button>Ajouter au panier</button>
</body></html>"""


def _search_page(path: str) -> str:
    params = parse_qs(urlparse(path).query)
    q = (params.get("q", [""])[0] or "").strip().lower()
    matches = [(p, m["name"]) for p, m in PRODUCTS.items() if not q or q in m["name"].lower()]
    items = "".join(
        f'<li><a data-radar="result" href="{p}">{escape(name)}</a></li>'
        for p, name in matches
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Recherche shop — {escape(q or 'tous')}</title></head>
<body><ul>{items}</ul></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.startswith("/search"):
            body = _search_page(self.path).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/p/"):
            body = _page(self.path.rstrip("/")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = b"Radar demo shop"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):  # quiet
        pass


def run(port: int = PORT) -> None:
    server = ThreadingHTTPServer((HOST, port), Handler)
    print(f"Radar demo shop running on http://{HOST}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()