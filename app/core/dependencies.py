from fastapi import Depends, Header
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import store
from app.db.session import get_session

API_KEY_HEADER_NAME = "X-API-Key"
ADMIN_TOKEN_HEADER = "X-Admin-Token"

api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=True)


async def get_db_session() -> AsyncSession:
    async with get_session() as session:
        yield session


async def get_service(
    api_key: str = Depends(api_key_header),
    session: AsyncSession = Depends(get_db_session),
):
    service = await store.validate_api_key(session, api_key)
    return service


async def require_admin(
    token: str = Header(..., alias=ADMIN_TOKEN_HEADER),
    session: AsyncSession = Depends(get_db_session),
):
    return await store.authenticate_admin(session, token)
