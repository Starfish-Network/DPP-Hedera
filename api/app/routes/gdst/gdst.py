from fastapi import APIRouter
from app.routes.gdst import compliance
from app.routes.gdst import events

router = APIRouter(prefix="/gdst", tags=["GDST"])

router.include_router(compliance.router)
router.include_router(events.router)