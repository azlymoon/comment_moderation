from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import models as api_models
from app.db import models


async def validate_api_key(session: AsyncSession, api_key: str) -> models.WebService:
    prefix = api_key[:8]
    result = await session.execute(
        select(models.APIKey).where(
            models.APIKey.key_prefix == prefix,
            models.APIKey.is_active.is_(True),
        )
    )
    api_keys = result.scalars().all()
    for key in api_keys:
        if key.verify(api_key):
            if key.expires_at and key.expires_at < datetime.utcnow():
                break
            key.last_used = datetime.utcnow()
            await session.commit()
            await session.refresh(key)
            service = await session.get(models.WebService, key.service_id)
            if service is None or not service.is_active:
                break
            return service
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


async def authenticate_admin(
    session: AsyncSession,
    token: str,
    required_roles: Optional[Iterable[str]] = None,
) -> models.AdminUser:
    db_session = await session.get(models.AdminSession, token)
    if db_session is None or not db_session.is_valid():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )
    user = await session.get(models.AdminUser, db_session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    if required_roles and user.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return map_admin_to_api(user)


async def save_moderation_request(
    session: AsyncSession,
    service: models.WebService,
    payload: api_models.ModerationRequestIn,
) -> models.ModerationRequest:
    request = models.ModerationRequest(
        service_id=service.service_id,
        content_text=payload.content_text,
        status=api_models.RequestStatus.PROCESSING.value,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def save_moderation_result(
    session: AsyncSession,
    request: models.ModerationRequest,
    result: api_models.ModerationResult,
) -> models.ModerationResult:
    db_result = models.ModerationResult(
        request_id=request.request_id,
        decision=result.decision.value,
        confidence_score=result.confidence_score,
        model_version=result.model_version,
        processed_at=result.processed_at,
        label_scores=json.dumps(result.label_scores or {}),
    )
    session.add(db_result)
    request.status = api_models.RequestStatus.COMPLETED.value
    await session.commit()
    await session.refresh(db_result)
    await session.refresh(request)
    return db_result


async def update_moderation_result(
    session: AsyncSession,
    request_id: uuid.UUID,
    update: api_models.ModerationUpdate,
) -> tuple[models.ModerationRequest, models.ModerationResult]:
    request = await session.get(models.ModerationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db_result = await session.execute(
        select(models.ModerationResult).where(models.ModerationResult.request_id == request_id)
    )
    result_obj = db_result.scalar_one_or_none()
    if result_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not available yet",
        )
    result_obj.decision = update.decision.value
    if update.confidence_score is not None:
        result_obj.confidence_score = update.confidence_score
    if update.model_version is not None:
        result_obj.model_version = update.model_version
    await session.commit()
    await session.refresh(result_obj)
    await session.refresh(request)
    return request, result_obj


async def list_requests(session: AsyncSession) -> list[api_models.ModerationRequest]:
    result = await session.execute(select(models.ModerationRequest))
    requests = result.scalars().all()
    return [map_request_to_api(request) for request in requests]


async def get_request_with_result(
    session: AsyncSession, request_id: uuid.UUID
) -> tuple[api_models.ModerationRequest, api_models.ModerationResult]:
    request = await session.get(models.ModerationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    result = await session.execute(
        select(models.ModerationResult).where(models.ModerationResult.request_id == request_id)
    )
    result_obj = result.scalar_one_or_none()
    if result_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not available yet",
        )
    return map_request_to_api(request), map_result_to_api(result_obj)


async def upsert_category(
    session: AsyncSession, category: api_models.ViolationCategory
) -> api_models.ViolationCategory:
    category_id = uuid.UUID(category.category_id) if category.category_id else uuid.uuid4()
    db_category = await session.get(models.ViolationCategory, category_id)
    if db_category is None:
        db_category = models.ViolationCategory(
            category_id=category_id,
            type=category.type.value,
            name=category.name,
            description=category.description,
            auto_reject_threshold=category.auto_reject_threshold,
            human_review_threshold=category.human_review_threshold,
            is_enabled=category.is_enabled,
        )
        session.add(db_category)
    else:
        db_category.type = category.type.value
        db_category.name = category.name
        db_category.description = category.description
        db_category.auto_reject_threshold = category.auto_reject_threshold
        db_category.human_review_threshold = category.human_review_threshold
        db_category.is_enabled = category.is_enabled
    await session.commit()
    await session.refresh(db_category)
    return map_category_to_api(db_category)


async def list_categories(session: AsyncSession) -> list[api_models.ViolationCategory]:
    result = await session.execute(select(models.ViolationCategory))
    categories = result.scalars().all()
    return [map_category_to_api(cat) for cat in categories]


async def create_rule(
    session: AsyncSession, rule: api_models.ModerationRule
) -> api_models.ModerationRule:
    category_id = uuid.UUID(rule.category_id)
    db_category = await session.get(models.ViolationCategory, category_id)
    if db_category is None or not db_category.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown or disabled category",
        )
    db_rule = models.ModerationRule(
        category_id=category_id,
        action=rule.action.value,
        priority=rule.priority,
        conditions=";".join(rule.conditions),
        is_active=True,
    )
    session.add(db_rule)
    await session.commit()
    await session.refresh(db_rule)
    return map_rule_to_api(db_rule)


async def compute_statistics(
    session: AsyncSession,
    service_id: uuid.UUID,
) -> api_models.StatisticsResponse:
    result = await session.execute(
        select(models.ModerationRequest).where(models.ModerationRequest.service_id == service_id)
    )
    requests = result.scalars().all()
    total = len(requests)
    pending = sum(1 for req in requests if req.status == api_models.RequestStatus.PENDING.value)
    text_requests = sum(1 for req in requests if req.content_type == api_models.ContentType.TEXT.value)

    stats = api_models.Statistics(
        service_id=str(service_id),
        date_period=datetime.utcnow(),
        total_requests=total,
        text_requests=text_requests,
    )

    results_query = await session.execute(
        select(models.ModerationResult).join(models.ModerationRequest).where(
            models.ModerationRequest.service_id == service_id
        )
    )
    results = results_query.scalars().all()
    decision_counts = {
        api_models.ModerationDecision.APPROVED: 0,
        api_models.ModerationDecision.REJECTED: 0,
        api_models.ModerationDecision.HUMAN_REVIEW: 0,
    }
    for res in results:
        decision = api_models.ModerationDecision(res.decision)
        decision_counts[decision] += 1
    stats.approved_count = decision_counts[api_models.ModerationDecision.APPROVED]
    stats.rejected_count = decision_counts[api_models.ModerationDecision.REJECTED]
    stats.human_review_count = decision_counts[api_models.ModerationDecision.HUMAN_REVIEW]

    return api_models.StatisticsResponse(totals=stats, pending_requests=pending)


async def list_services(session: AsyncSession) -> list[api_models.WebService]:
    result = await session.execute(select(models.WebService))
    services = result.scalars().all()
    return [map_service_to_api(service) for service in services]


async def create_service(
    session: AsyncSession, payload: api_models.WebServiceCreate
) -> api_models.WebService:
    service = models.WebService(
        name=payload.name,
        description=payload.description,
        contact_email=payload.contact_email,
        is_active=payload.is_active,
    )
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return map_service_to_api(service)


async def issue_api_key(
    session: AsyncSession, service_id: uuid.UUID, expires_at: Optional[datetime] = None
) -> api_models.APIKeyIssueResponse:
    service = await session.get(models.WebService, service_id)
    if service is None or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    plain_key = models.APIKey.generate_plain_key()
    key_hash, prefix = models.APIKey.hash_key(plain_key)
    api_key = models.APIKey(
        service_id=service_id,
        key_hash=key_hash,
        key_prefix=prefix,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    key_response = map_api_key_to_api(api_key)
    return api_models.APIKeyIssueResponse(api_key=plain_key, **key_response.dict())


async def list_api_keys(session: AsyncSession, service_id: uuid.UUID) -> list[api_models.APIKeyResponse]:
    result = await session.execute(
        select(models.APIKey).where(models.APIKey.service_id == service_id)
    )
    keys = result.scalars().all()
    return [map_api_key_to_api(key) for key in keys]


async def set_api_key_status(
    session: AsyncSession, key_id: uuid.UUID, is_active: bool
) -> api_models.APIKeyResponse:
    api_key = await session.get(models.APIKey, key_id)
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    api_key.is_active = is_active
    await session.commit()
    await session.refresh(api_key)
    return map_api_key_to_api(api_key)


async def create_admin_user(
    session: AsyncSession, payload: api_models.AdminUserCreate
) -> api_models.AdminUser:
    existing = await session.execute(
        select(models.AdminUser).where(models.AdminUser.username == payload.username)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    password_hash = models.AdminUser.hash_password(payload.password)
    user = models.AdminUser(
        username=payload.username,
        email=payload.email,
        password_hash=password_hash,
        role=payload.role.value,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return map_admin_to_api(user)


async def list_admin_users(session: AsyncSession) -> list[api_models.AdminUser]:
    result = await session.execute(select(models.AdminUser))
    users = result.scalars().all()
    return [map_admin_to_api(user) for user in users]


async def create_admin_session(
    session: AsyncSession, credentials: api_models.AdminLoginRequest
) -> api_models.AdminToken:
    result = await session.execute(
        select(models.AdminUser).where(models.AdminUser.username == credentials.username)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.verify_password(credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")

    session_obj = models.AdminSession(user_id=user.user_id)
    session.add(session_obj)
    user.last_login = datetime.utcnow()
    await session.commit()
    await session.refresh(session_obj)
    return api_models.AdminToken(token=session_obj.token, expires_at=session_obj.expires_at)


async def ensure_demo_data(
    session: AsyncSession,
    *,
    admin_username: str,
    admin_password: str,
    admin_email: str,
    service_name: str,
    service_contact: str,
) -> tuple[api_models.AdminUser, api_models.WebService, api_models.APIKeyIssueResponse]:
    admin_result = await session.execute(
        select(models.AdminUser).where(models.AdminUser.username == admin_username)
    )
    admin = admin_result.scalar_one_or_none()
    if admin is None:
        admin = models.AdminUser(
            username=admin_username,
            email=admin_email,
            password_hash=models.AdminUser.hash_password(admin_password),
            role=api_models.UserRole.SUPER_ADMIN.value,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

    service_result = await session.execute(
        select(models.WebService).where(models.WebService.name == service_name)
    )
    service = service_result.scalar_one_or_none()
    if service is None:
        service = models.WebService(
            name=service_name,
            contact_email=service_contact,
            description="Demo service for moderation",
        )
        session.add(service)
        await session.commit()
        await session.refresh(service)

    key_result = await session.execute(
        select(models.APIKey).where(models.APIKey.service_id == service.service_id)
    )
    api_key = key_result.scalar_one_or_none()
    key_response = None
    if api_key is None:
        key_response = await issue_api_key(session, service.service_id)
    else:
        key_payload = map_api_key_to_api(api_key)
        key_response = api_models.APIKeyIssueResponse(api_key="", **key_payload.dict())

    category_result = await session.execute(
        select(models.ViolationCategory).where(models.ViolationCategory.type == api_models.CategoryType.TOXICITY.value)
    )
    category = category_result.scalar_one_or_none()
    if category is None:
        category = models.ViolationCategory(
            type=api_models.CategoryType.TOXICITY.value,
            name="Toxic language",
            description="Auto-generated category for toxic language detection",
        )
        session.add(category)
        await session.commit()
        await session.refresh(category)

    rule_result = await session.execute(select(models.ModerationRule).where(models.ModerationRule.category_id == category.category_id))
    rule = rule_result.scalar_one_or_none()
    if rule is None:
        rule = models.ModerationRule(
            category_id=category.category_id,
            action=api_models.RuleAction.FLAG_FOR_REVIEW.value,
            priority=10,
            conditions="contains:toxic",
        )
        session.add(rule)
        await session.commit()

    return map_admin_to_api(admin), map_service_to_api(service), key_response


def map_category_to_api(category: models.ViolationCategory) -> api_models.ViolationCategory:
    return api_models.ViolationCategory(
        category_id=str(category.category_id),
        type=api_models.CategoryType(category.type),
        name=category.name,
        description=category.description,
        auto_reject_threshold=category.auto_reject_threshold,
        human_review_threshold=category.human_review_threshold,
        is_enabled=category.is_enabled,
    )


def map_rule_to_api(rule: models.ModerationRule) -> api_models.ModerationRule:
    conditions = rule.conditions.split(";") if rule.conditions else []
    return api_models.ModerationRule(
        rule_id=str(rule.rule_id),
        category_id=str(rule.category_id),
        action=api_models.RuleAction(rule.action),
        priority=rule.priority,
        conditions=conditions,
    )


def map_request_to_api(request: models.ModerationRequest) -> api_models.ModerationRequest:
    return api_models.ModerationRequest(
        request_id=str(request.request_id),
        service_id=str(request.service_id),
        timestamp=request.timestamp,
        content_type=api_models.ContentType(request.content_type),
        content_text=request.content_text,
        status=api_models.RequestStatus(request.status),
    )


def map_result_to_api(result: models.ModerationResult) -> api_models.ModerationResult:
    label_scores = json.loads(result.label_scores or "{}")
    return api_models.ModerationResult(
        result_id=str(result.result_id),
        request_id=str(result.request_id),
        decision=api_models.ModerationDecision(result.decision),
        confidence_score=result.confidence_score,
        processed_at=result.processed_at,
        model_version=result.model_version,
        label_scores=label_scores,
    )


def map_service_to_api(service: models.WebService) -> api_models.WebService:
    return api_models.WebService(
        service_id=str(service.service_id),
        name=service.name,
        description=service.description,
        contact_email=service.contact_email,
        registration_date=service.registration_date,
        is_active=service.is_active,
    )


def map_api_key_to_api(key: models.APIKey) -> api_models.APIKeyResponse:
    return api_models.APIKeyResponse(
        key_id=str(key.key_id),
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        expires_at=key.expires_at,
        is_active=key.is_active,
        last_used=key.last_used,
    )


def map_admin_to_api(user: models.AdminUser) -> api_models.AdminUser:
    return api_models.AdminUser(
        user_id=str(user.user_id),
        username=user.username,
        email=user.email,
        role=api_models.UserRole(user.role),
        is_active=user.is_active,
        last_login=user.last_login,
    )
