"""Run the background worker:  python -m app.worker"""

import logging
import signal
import time

from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.session import get_session_factory
from app.worker.runner import claim, recover_stale, run_job

log = logging.getLogger("app.worker")


def main() -> None:
    import app.worker.handlers  # noqa: F401  (registers handlers)

    configure_logging()
    settings = get_settings()
    factory = get_session_factory()
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True
        log.info("worker stopping after the current job")

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    log.info("worker started")
    last_recovery = 0.0
    backoff = settings.worker_poll_seconds
    while not stopping:
        try:
            if time.monotonic() - last_recovery > 60:
                with factory() as db:
                    if recovered := recover_stale(db):
                        log.info("recovered %s stale job(s)", recovered)
                last_recovery = time.monotonic()
            with factory() as db:
                job_id = claim(db)
        except OperationalError as exc:
            # Database restarting or unreachable: wait and try again instead of exiting.
            log.warning("database unavailable (%s); retrying in %.0fs", type(exc.orig).__name__, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue
        backoff = settings.worker_poll_seconds
        if job_id is None:
            time.sleep(settings.worker_poll_seconds)
            continue
        log.info("running job %s", job_id)
        run_job(factory, job_id)


if __name__ == "__main__":
    main()
