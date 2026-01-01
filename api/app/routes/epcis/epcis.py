from fastapi import APIRouter
from app.routes.epcis import events
from app.routes.epcis import compliance
from api.app.routes import trace

router = APIRouter(prefix="/epcis", tags=["EPCIS"])

router.include_router(compliance.router)
router.include_router(events.router)