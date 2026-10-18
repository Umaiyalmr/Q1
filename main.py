
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers
from uuid import uuid4
from time import perf_counter
import json

api = FastAPI()

ALLOWED_ORIGIN = "https://dash-2cjz36.example.com"
EMAIL = "23f2005531@ds.study.iitm.ac.in"


@api.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    start = perf_counter()

    response = await call_next(request)

    elapsed = max(0.0, perf_counter() - start)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.6f}"

    return response


@api.get("/stats")
async def stats(values: str = Query(...)):
    try:
        numbers = [int(value.strip()) for value in values.split(",")]
        if not numbers:
            raise ValueError("No values supplied")
    except (ValueError, AttributeError):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="values must be comma-separated integers",
        )

    return {
        "email": EMAIL,
        "count": len(numbers),
        "sum": sum(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "mean": sum(numbers) / len(numbers),
    }


# Strict CORS: only the assigned origin receives ACAO.
# Wrap the fully configured FastAPI app so headers are applied consistently.
app = CORSMiddleware(
    app=api,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)
