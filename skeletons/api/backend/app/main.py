import logging
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from app.logging import configure_logging, set_trace_id

configure_logging()
logger = logging.getLogger("app")

app = FastAPI()
STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.middleware("http")
async def trace_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    raw_trace = request.headers.get("x-cloud-trace-context") or request.headers.get("x-request-id") or ""
    trace_id = raw_trace.split("/", 1)[0].strip() if raw_trace else uuid.uuid4().hex[:16]
    set_trace_id(trace_id)
    response = await call_next(request)
    response.headers["X-Request-Id"] = trace_id
    return response


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/{full_path:path}", response_model=None)
def spa(full_path: str) -> Response:
    if full_path:
        candidate = (STATIC_DIR / full_path).resolve()
        if candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    logger.info("ui bundle is not built")
    return JSONResponse({"status": "ok", "ui": "not-built"})
