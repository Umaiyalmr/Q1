import os
import time
import uuid
from statistics import mean

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

ALLOWED_ORIGIN = "https://dash-2cjzj36.example.com"
EMAIL = os.environ["CHALLENGE_EMAIL"]

# Add CORS middleware for the one permitted origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Add required headers to every response, including preflight responses.
@app.middleware("http")
async def add_required_headers(request, call_next):
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = (
        f"{max(0.0, time.perf_counter() - start):.6f}"
    )
    return response


@app.get("/stats")
def get_stats(values: str = Query(...)):
    try:
        parts = values.split(",")
        if not parts or any(not p.strip() for p in parts):
            raise ValueError
        nums = [int(p.strip()) for p in parts]
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="values must be comma-separated integers",
        )

    return {
        "email": EMAIL,
        "count": len(nums),
        "sum": sum(nums),
        "min": min(nums),
        "max": max(nums),
        "mean": mean(nums),
    }
