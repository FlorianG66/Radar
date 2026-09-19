"""Queue abstraction: Redis/RQ when available, in-process thread queue
otherwise (pure local development without a Redis server)."""
from __future__ import annotations

import logging
import queue as _queue
from threading import Thread

from app.core.config import get_settings
from app.core.redis import notification_queue, redis_client, scrape_queue
from app.workers.tasks import process_event_notifications, process_scrape

logger = logging.getLogger("radar.jobs")

_local_jobs: "_queue.Queue[tuple[str, int]]" = _queue.Queue()

MAIN_QUEUE_NAMES = ("scrapes", "notifications")


def _enqueue(rq_queue, *args, **kwargs):
    if rq_queue is None:
        return False
    rq_queue.enqueue(*args, **kwargs)
    return True


def enqueue_scrape(product_id: int) -> bool:
    settings = get_settings()
    if redis_client.available():
        try:
            return _enqueue(
                scrape_queue,
                process_scrape,
                product_id,
                job_timeout=int(settings.SCRAPE_TIMEOUT_SECONDS) * 2 + 60,
                result_ttl=7 * 86400,
                retry=_rq_retry(),
            )
        except Exception:
            logger.exception("failed to enqueue %s", product_id)
            return False
    _local_jobs.put(("scrape", product_id))
    return True


def enqueue_notification(event_id: int) -> bool:
    if redis_client.available():
        try:
            return _enqueue(notification_queue, process_event_notifications, event_id, job_timeout=120, result_ttl=86400)
        except Exception:
            logger.exception("failed to enqueue notification %s", event_id)
            return False
    _local_jobs.put(("notify", event_id))
    return True


def _rq_retry():
    from rq import Retry

    return Retry(max=2, interval=[60, 300])


def _local_worker_loop() -> None:
    while True:
        kind, payload = _local_jobs.get()
        try:
            if kind == "scrape":
                process_scrape(payload)
            else:
                process_event_notifications(payload)
        except Exception:
            logger.exception("local job failed kind=%s payload=%s", kind, payload)


_local_thread: Thread | None = None


def start_local_processor() -> Thread:
    """Start the in-process worker used when Redis is unavailable."""
    global _local_thread
    if _local_thread and _local_thread.is_alive():
        return _local_thread
    _local_thread = Thread(target=_local_worker_loop, name="radar-local-worker", daemon=True)
    _local_thread.start()
    return _local_thread