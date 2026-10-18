
import time
import uuid
from statistics import mean

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-dzkopdin.apps.exam.local"

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2ok0HspNjgA+2rTLbeuY
cxiP/hG8C6Sh9iw3yiLAA4HCnpIITcbWCSelbvYGuC3EbNy4xFy+5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNWheKuzsPUNVldu6A9cNteNpXc
WyJjG2axVfmq7i6SukrJ1oWYG7XTtAVkPujSI4OTsQfO3h5NepzdfXpr28oNnzfW
ed+zcRl6BcnNNo/WvFJ4xyCLSf0BCOgDtGW6PdaChd119VDetJZVEgC5tkyVxSfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LLgniT7G1kL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

app = FastAPI()


@app.middleware("http")
async def add_required_headers(request: Request, call_next):
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    elapsed = max(0.0, time.perf_counter() - start)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.6f}"
    return response


@app.post("/verify")
async def verify_token(request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Invalid request body")

        token = body.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("Missing token")

        claims = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={
                "require": ["exp", "iss", "aud", "sub", "email"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )

        return {
            "valid": True,
            "email": claims["email"],
            "sub": claims["sub"],
            "aud": claims["aud"],
        }

    except (InvalidTokenError, ValueError, TypeError, KeyError):
        return JSONResponse(
            status_code=401,
            content={"valid": False},
        )
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"valid": False},
        )
