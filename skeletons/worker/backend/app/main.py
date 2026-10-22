import logging

from app.logging import configure_logging

configure_logging()
logger = logging.getLogger("worker")


def run_once() -> str:
    logger.info("worker_tick")
    return "ok"


if __name__ == "__main__":
    print(run_once())
