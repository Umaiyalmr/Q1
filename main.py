import os
import time
import uuid
from statistics import mean

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGIN = "https://dash-2cjzj36.example.com"
EMAIL = os.environ["CHALLENGE_EMAIL"]

api = FastAPI()


@api.get("/stats")
def get_stats(values: str = Query(...)):
    try:
        parts = values.split(",")
        if any(not p.strip() for p in parts):
            raise ValueError
        nums = [int(p.strip()) for p in parts]
        if not nums:
            raise ValueError
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


# Wrap the entire FastAPI application in CORS middleware.
cors_app = CORSMiddleware(
    app=api,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


# Outer middleware adds headers even when CORS handles OPTIONS directly.
class RequiredHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        request_id = str(uuid.uuid4())

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-request-id", request_id.encode()),
                    (
                        b"x-process-time",
                        f"{max(0.0, time.perf_counter() - started):.6f}".encode(),
                    ),
                ])
                message = {**message, "headers": headers}

            await send(message)

        await self.app(scope, receive, send_with_headers)


app = RequiredHeadersMiddleware(cors_app)
