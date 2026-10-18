
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextvars import ContextVar
from collections import defaultdict, deque
from threading import Lock
from uuid import uuid4
from time import monotonic
from math import ceil

app = FastAPI()

ALLOWED_ORIGIN = "https://app-m7lh9.example.com"
RATE_LIMIT = 9
WINDOW_SECONDS = 10

request_id_var = ContextVar("request_id", default=None)
rate_lock = Lock()
request_times = defaultdict(deque)


# Middleware 1: Request context
@app.middleware("http")
async def request_context(request: Request, call_next):
    incoming_id = request.headers.get("X-Request-ID")
    request_id = incoming_id if incoming_id else str(uuid4())

    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


# Middleware 2: Per-client rate limiting
@app.middleware("http")
async def per_client_rate_limit(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path != "/ping":
        return await call_next(request)

    client_id = request.headers.get("X-Client-Id", "anonymous")
    now = monotonic()

    with rate_lock:
        timestamps = request_times[client_id]

        while timestamps and now - timestamps[0] >= WINDOW_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= RATE_LIMIT:
            retry_after = max(
                1,
                ceil(WINDOW_SECONDS - (now - timestamps[0]))
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)

    return await call_next(request)


# Endpoint
@app.get("/ping")
async def ping():
    return {
        "email": "23f2005531@ds.study.iitm.ac.in",
        "request_id": request_id_var.get(),
    }


# Middleware 3: CORS must wrap the entire app, including error responses.
# Keep this at the bottom, after routes and middleware definitions.
app = CORSMiddleware(
    app=app,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id", "Content-Type"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
