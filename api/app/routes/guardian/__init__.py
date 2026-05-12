from fastapi import APIRouter
from app.routes.guardian import dryrun, identity, policy

router = APIRouter(prefix="/guardian", tags=["Guardian"])

router.include_router(identity.router)
router.include_router(policy.router)
router.include_router(dryrun.router)
