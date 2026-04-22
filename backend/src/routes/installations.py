from auth import verify_token
from db.models import Installation
from db.session import get_db
from fastapi import APIRouter, Depends
from schemas.models import InstallationResponseSchema
from sqlalchemy import desc
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/", response_model=list[InstallationResponseSchema])
async def get_installations(db: Session = Depends(get_db), _=Depends(verify_token)):
    all_installations = (
        db.query(Installation).order_by(desc(Installation.last_seen)).all()
    )

    return [
        InstallationResponseSchema(
            id=i.id, last_seen=i.last_seen, created_at=i.created_at
        )
        for i in all_installations
    ]
