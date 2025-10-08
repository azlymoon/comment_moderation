from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import dependencies, models, store
from app.services import evaluate_text

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.post("/text", response_model=models.ModerationResponse)
async def create_text_moderation(
    payload: models.ModerationRequestIn,
    service=Depends(dependencies.get_service),
    session: AsyncSession = Depends(dependencies.get_db_session),
) -> models.ModerationResponse:
    if payload.service_id != str(service.service_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service identifier mismatch",
        )
    db_request = await store.save_moderation_request(session, service, payload)
    result = evaluate_text(payload.content_text)
    db_result = await store.save_moderation_result(session, db_request, result)
    api_request = store.map_request_to_api(db_request)
    api_result = store.map_result_to_api(db_result)
    return models.ModerationResponse(request=api_request, result=api_result)
