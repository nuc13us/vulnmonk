from fastapi import APIRouter

from .routes.auth import router as auth_router
from .routes.projects import router as projects_router
from .routes.integrations import router as integrations_router
from .routes.webhooks import router as webhooks_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(projects_router)
router.include_router(integrations_router)
router.include_router(webhooks_router)
