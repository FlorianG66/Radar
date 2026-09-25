"""Local development: run API + scheduler + worker + demo shop in ONE process.

Avoids needing Docker/Redis for day-to-day development:
    python -m scripts.dev_local

The production path (docker compose) runs each component separately with
Postgres + Redis.
"""
from __future__ import annotations

import threading


def main() -> None:
    from app.core import jobs
    from app.core.logging import setup_logging
    from app.seed import demo_shop
    from app.workers import scheduler

    setup_logging()

    threading.Thread(target=demo_shop.run, daemon=True, name="demo-shop").start()
    jobs.start_local_processor()
    threading.Thread(target=scheduler.run_forever, daemon=True, name="scheduler").start()

    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()