"""RQ worker entrypoint: `python -m app.workers.worker`"""
from __future__ import annotations

import logging

from app.core.redis import notification_queue, redis_client, scrape_queue

logger = logging.getLogger("radar.rq")


def main() -> None:
    from rq import Worker

    from app.core.logging import setup_logging

    setup_logging()
    queues = [scrape_queue, notification_queue]
    worker = Worker(queues, connection=redis_client, name="radar-worker")
    logger.info("rq worker started on queues: %s", [q.name for q in queues])
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()