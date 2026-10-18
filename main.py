
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

# --------------------------------------------------
# Configuration
# --------------------------------------------------

ALLOWED_ORIGIN = "https://dash-2cjz36.example.com"

# Replace with your exact logged-in email address.
EMAIL = "23f2005531@ds.study.iitm.ac.in"

api = FastAPI(title="Statistics API")


# --------------------------------------------------
# Middleware 1: Request ID and processing time
# --------------------------------------------------

@api.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        # Ensure the request context headers are present even on errors.
        from starlette.responses import JSONResponse

        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    elapsed = max(0.0, time.perf_counter() - start_time)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.6f}"

    return response


# --------------------------------------------------
# Endpoint: GET /stats?values=1,2,3
# --------------------------------------------------

@api.get("/stats")
async def get_stats(values: str = Query(...)):
    try:
        numbers = [int(value.strip()) for value in values.split(",")]

        if not numbers:
            raise ValueError("No values provided")

    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail="values must be comma-separated integers",
        )

    total = sum(numbers)

    return {
        "email": EMAIL,
        "count": len(numbers),
        "sum": total,
        "min": min(numbers),
        "max": max(numbers),
        "mean": total / len(numbers),
    }


# --------------------------------------------------
# Strict CORS: only the assigned origin is allowed
# This wrapper must be last.
# --------------------------------------------------

app = CORSMiddleware(
    app=api,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)
