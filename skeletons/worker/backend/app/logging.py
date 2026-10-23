import json
import logging
import os
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        service = (
            os.environ.get("K_SERVICE")
            or os.environ.get("CLOUD_RUN_JOB")
            or os.environ.get("SERVICE_NAME", "worker")
        )
        payload: dict[str, str] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "service": service,
            "environment": os.environ.get("APP_ENV", "local"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
