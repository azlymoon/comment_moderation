import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.api.routes_moderation import router as moderation_router
from app.config import settings
from app.core import store
from app.db.session import get_session, init_engine, run_migrations

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
# Configure root logging level from env (default INFO). Uvicorn handles its own loggers.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger.setLevel(LOG_LEVEL)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(auth_router)
    app.include_router(moderation_router, prefix="/api/v1")
    app.include_router(admin_router)

    ui_dir = BASE_DIR / "scripts" / "ui"
    if ui_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")

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
                    logger.info("Generated demo API key %s for service %s", api_key.api_key, service.service_id)
                else:
                    logger.info(
                        "Demo API key already exists for service %s (prefix %s)",
                        service.service_id,
                        api_key.key_prefix,
                )
                logger.info("Demo admin user: %s", admin.username)
                # Extra output to help GUI test setup with demo credentials.
                logger.info("Demo service ID: %s", service.service_id)
                # Show full API key only if it was just created; otherwise show prefix.
                if api_key.api_key:
                    logger.info("Demo plain API key: %s", api_key.api_key)
                else:
                    logger.info("Existing API key prefix: %s (plain key not stored)", api_key.key_prefix)

    return app
