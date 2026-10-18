import os
import time
import uuid
from statistics import mean

from fastapi import FastAPI, Query, HTTPException
from starlette.types import ASGIApp, Scope, Receive, Send, Message

ALLOWED_ORIGIN = "https://dash-2cjzj36.example.com"
EMAIL = os.environ["CHALLENGE_EMAIL"]

api = FastAPI()


class StrictMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        request_id = str(uuid.uuid4())
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode()

        async def send_response(status: int, response_headers: list):
            body = b""
            await send({
                "type": "http.response.start",
                "status": status,
                "headers": response_headers + [
                    (b"x-request-id", request_id.encode()),
                    (b"x-process-time",
                     f"{max(0.0, time.perf_counter() - start):.6f}".encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})

        if scope["method"] == "OPTIONS" and scope["path"] == "/stats":
            if origin != ALLOWED_ORIGIN:
                await send_response(403, [])
                return

            await send_response(204, [
                (b"access-control-allow-origin", ALLOWED_ORIGIN.encode()),
                (b"access-control-allow-methods", b"GET, OPTIONS"),
                (b"access-control-allow-headers",
                 headers.get(b"access-control-request-headers", b"")),
                (b"vary", b"Origin"),
            ])
            return

        async def wrapped_send(message: Message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                if origin == ALLOWED_ORIGIN:
                    response_headers.append(
                        (b"access-control-allow-origin", ALLOWED_ORIGIN.encode())
                    )
                    response_headers.append((b"vary", b"Origin"))

                response_headers.extend([
                    (b"x-request-id", request_id.encode()),
                    (b"x-process-time",
                     f"{max(0.0, time.perf_counter() - start):.6f}".encode()),
                ])
                message = {**message, "headers": response_headers}

            await send(message)

        await self.app(scope, receive, wrapped_send)


@api.get("/stats")
def stats(values: str = Query(...)):
    try:
        nums = [int(x.strip()) for x in values.split(",")]
        if not nums or any(x == "" for x in values.split(",")):
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


app = StrictMiddleware(api)
