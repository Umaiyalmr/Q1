
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from math import ceil
import base64
import json

app = FastAPI(title="Orders API")

TOTAL_ORDERS = 58
RATE_LIMIT = 15
WINDOW_SECONDS = 10

lock = Lock()
catalog = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]
idempotency_store = {}
next_order_id = TOTAL_ORDERS + 1
request_times = defaultdict(deque)


class OrderRequest(BaseModel):
    item: str = "default"
    quantity: int = 1


def check_rate_limit(client_id: str):
    now = monotonic()

    with lock:
        timestamps = request_times[client_id]

        while timestamps and now - timestamps[0] >= WINDOW_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= RATE_LIMIT:
            retry_after = max(
                1,
                ceil(WINDOW_SECONDS - (now - timestamps[0]))
            )
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)


@app.middleware("http")
async def client_rate_limit(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path == "/orders":
        client_id = request.headers.get("X-Client-Id", "anonymous")

        try:
            check_rate_limit(client_id)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )

    return await call_next(request)


@app.post("/orders", status_code=201)
def create_order(
    order: OrderRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    global next_order_id

    with lock:
        if idempotency_key in idempotency_store:
            return idempotency_store[idempotency_key]

        result = {
            "id": next_order_id,
            "item": order.item,
            "quantity": order.quantity,
        }

        next_order_id += 1
        idempotency_store[idempotency_key] = result
        return result


def encode_cursor(last_id: int) -> str:
    raw = json.dumps({"last_id": last_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        payload = json.loads(raw)
        last_id = payload["last_id"]

        if (
            isinstance(last_id, bool)
            or not isinstance(last_id, int)
            or not 0 <= last_id <= TOTAL_ORDERS
        ):
            raise ValueError("Invalid cursor")

        return last_id
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@app.get("/orders")
def list_orders(
    limit: int = Query(default=10, ge=1),
    cursor: str | None = Query(default=None),
):
    last_id = decode_cursor(cursor) if cursor else 0
    end = min(last_id + limit, TOTAL_ORDERS)

    items = catalog[last_id:end]
    next_cursor = encode_cursor(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# IMPORTANT: Wrap the completed FastAPI app only after defining
# all routes and middleware. This makes CORS outermost.
app = CORSMiddleware(
    app=app,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)
