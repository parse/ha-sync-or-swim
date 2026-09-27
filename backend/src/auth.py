import hmac
import os
from time import perf_counter

from fastapi import Header, HTTPException, Request, status
from request_timing import elapsed_ms, log_timing


def bearer_token_matches(authorization: str | None, expected_token: str) -> bool:
    """Compare in constant time so response timing does not leak the token."""
    return hmac.compare_digest(
        (authorization or "").encode(), f"Bearer {expected_token}".encode()
    )


def verify_token(request: Request, authorization: str | None = Header(None)) -> None:
    started = perf_counter()
    expected_token = os.environ.get("PUSH_TOKEN")
    if not expected_token:
        log_timing(
            "request_authentication",
            installation_id=request.path_params.get("installation_id", "unknown"),
            duration_ms=elapsed_ms(started),
            result="server_misconfigured",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PUSH_TOKEN not configured on server",
        )

    if not bearer_token_matches(authorization, expected_token):
        log_timing(
            "request_authentication",
            installation_id=request.path_params.get("installation_id", "unknown"),
            duration_ms=elapsed_ms(started),
            result="unauthorized",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    log_timing(
        "request_authentication",
        installation_id=request.path_params.get("installation_id", "unknown"),
        duration_ms=elapsed_ms(started),
        result="success",
    )


def verify_web_ui_token(authorization: str | None = Header(None)) -> None:
    expected_token = os.environ.get("WEB_UI_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WEB_UI_TOKEN not configured on server",
        )

    if not bearer_token_matches(authorization, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
