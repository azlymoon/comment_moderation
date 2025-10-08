import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import dependencies, models, store

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/requests", response_model=list[models.ModerationRequest])
async def list_requests(
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> list[models.ModerationRequest]:
    return await store.list_requests(session)


@router.get("/requests/{request_id}", response_model=models.ModerationResponse)
async def get_request(
    request_id: str,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.ModerationResponse:
    request_uuid = uuid.UUID(request_id)
    request, result = await store.get_request_with_result(session, request_uuid)
    return models.ModerationResponse(request=request, result=result)


@router.patch("/requests/{request_id}", response_model=models.ModerationResponse)
async def update_request(
    request_id: str,
    update: models.ModerationUpdate,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.ModerationResponse:
    request_uuid = uuid.UUID(request_id)
    db_request, db_result = await store.update_moderation_result(session, request_uuid, update)
    return models.ModerationResponse(
        request=store.map_request_to_api(db_request), result=store.map_result_to_api(db_result)
    )


@router.get("/categories", response_model=list[models.ViolationCategory])
async def list_categories(
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> list[models.ViolationCategory]:
    return await store.list_categories(session)


@router.post("/categories", response_model=models.ViolationCategory)
async def create_category(
    category: models.ViolationCategory,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.ViolationCategory:
    return await store.upsert_category(session, category)


@router.post("/rules", response_model=models.ModerationRule)
async def create_rule(
    rule: models.ModerationRule,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.ModerationRule:
    return await store.create_rule(session, rule)


@router.get("/statistics/{service_id}", response_model=models.StatisticsResponse)
async def get_statistics(
    service_id: str,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.StatisticsResponse:
    service_uuid = uuid.UUID(service_id)
    return await store.compute_statistics(session, service_uuid)


@router.get("/services", response_model=list[models.WebService])
async def list_services(
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> list[models.WebService]:
    return await store.list_services(session)


@router.post("/services", response_model=models.WebService, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: models.WebServiceCreate,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.WebService:
    return await store.create_service(session, payload)


@router.post("/services/{service_id}/api-keys", response_model=models.APIKeyIssueResponse)
async def issue_api_key(
    service_id: str,
    expires_at: Optional[datetime] = None,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.APIKeyIssueResponse:
    return await store.issue_api_key(session, uuid.UUID(service_id), expires_at)


@router.get("/services/{service_id}/api-keys", response_model=list[models.APIKeyResponse])
async def list_service_keys(
    service_id: str,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> list[models.APIKeyResponse]:
    return await store.list_api_keys(session, uuid.UUID(service_id))


@router.patch("/api-keys/{key_id}", response_model=models.APIKeyResponse)
async def toggle_api_key(
    key_id: str,
    is_active: bool,
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.APIKeyResponse:
    return await store.set_api_key_status(session, uuid.UUID(key_id), is_active)


@router.get("/users", response_model=list[models.AdminUser])
async def list_admin_users(
    _: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> list[models.AdminUser]:
    return await store.list_admin_users(session)


@router.post("/users", response_model=models.AdminUser, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    payload: models.AdminUserCreate,
    current_user: models.AdminUser = Depends(dependencies.require_admin),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.AdminUser:
    if current_user.role != models.UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only SUPER_ADMIN can create users"
        )
    return await store.create_admin_user(session, payload)
