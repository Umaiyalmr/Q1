
import json
import logging
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from threading import Lock

from fastapi import FastAPI, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

EMAIL = os.environ.get("CHALLENGE_EMAIL", "your-email@example.com")
START_TIME = time.monotonic()
MAX_LOG_ENTRIES = 1000

app = FastAPI()

# A live Prometheus counter, incremented for every incoming HTTP request.
REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total number of HTTP requests received",
)

# Retain recent structured logs in memory for /logs/tail.
recent_logs = deque(maxlen=MAX_LOG_ENTRIES)
logs_lock = Lock()


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return record.getMessage()


logger = logging.getLogger("service")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)


def write_log(level: str, timestamp: str, path: str, request_id: str):
    entry = {
        "level": level,
        "ts": timestamp,
        "path": path,
        "request_id": request_id,
    }

    with logs_lock:
        recent_logs.append(entry)

    logger.info(json.dumps(entry, separators=(",", ":")))


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    REQUEST_COUNTER.inc()

    request_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        response = await call_next(request)
    except Exception:
        write_log("error", timestamp, request.url.path, request_id)
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{max(0.0, time.perf_counter() - (time.perf_counter()):.6f}"

    # Record every request, including /work and monitoring endpoints.
    write_log(
        "info" if response.status_code < 500 else "error",
        timestamp,
        request.url.path,
        request_id,
    )

    return response


@app.get("/work")
def do_work(k: int = Query(..., ge=0, le=100000)):
    # Perform K units of actual CPU work rather than returning a hard-coded result.
    result = 0
    for i in range(k):
        result += i

    return {
        "email": EMAIL,
        "done": k,
    }


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/healthz")
def health():
    return {
        "status": "ok",
        "uptime_s": max(0.0, time.monotonic() - START_TIME),
    }


@app.get("/logs/tail")
def logs_tail(limit: int = Query(100, alias="limit", ge=1, le=1000)):
    with logs_lock:
        entries = list(recent_logs)[-limit:]

    return entries
