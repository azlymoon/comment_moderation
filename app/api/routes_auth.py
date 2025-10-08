from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import models, store
from app.core.dependencies import get_db_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=models.AdminToken)
async def login(
    credentials: models.AdminLoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> models.AdminToken:
    return await store.create_admin_session(session, credentials)
