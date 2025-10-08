import logging

from fastapi import FastAPI

from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.api.routes_moderation import router as moderation_router
from app.config import settings
from app.core import store
from app.db.session import get_session, init_engine, run_migrations

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(auth_router)
    app.include_router(moderation_router, prefix="/api/v1")
    app.include_router(admin_router)

    @app.on_event("startup")
    async def startup() -> None:
        init_engine()
        await run_migrations()
        if settings.generate_demo_data:
            async with get_session() as session:
                admin, service, api_key = await store.ensure_demo_data(
                    session,
                    admin_username=settings.admin_demo_username,
                    admin_password=settings.admin_demo_password,
                    admin_email=settings.admin_demo_email,
                    service_name=settings.service_demo_name,
                    service_contact=settings.service_demo_contact,
                )
                if api_key.api_key:
                    logger.info(
                        "Generated demo API key %s for service %s",
                        api_key.api_key,
                        service.service_id,
                    )
                else:
                    logger.info(
                        "Demo API key already exists for service %s (prefix %s)",
                        service.service_id,
                        api_key.key_prefix,
                    )
                logger.info("Demo admin user: %s", admin.username)

    return app
