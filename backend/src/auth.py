import os

from fastapi import Header, HTTPException, status


def verify_token(authorization: str | None = Header(None)) -> None:
    expected_token = os.environ.get("PUSH_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PUSH_TOKEN not configured on server",
        )

    if authorization != f"Bearer {expected_token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
