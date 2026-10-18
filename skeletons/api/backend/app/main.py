import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response

from app.logging import configure_logging

configure_logging()
logger = logging.getLogger("app")

app = FastAPI()
STATIC_DIR = Path(__file__).resolve().parent / "static"


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
