from fastapi import HTTPException
from schemas.models import validate_installation_id


def valid_installation_id(installation_id: str) -> str:
    """Validate the installation_id path parameter, rejecting bad IDs with 400."""
    try:
        return validate_installation_id(installation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
