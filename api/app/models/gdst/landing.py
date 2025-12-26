from pydantic import validator
from app.models.gdst.base import GDSTEvent

class LandingEvent(GDSTEvent):
    gdst_event_type: str = "Landing"

    @validator("iuu")
    def landing_requires_authorization(cls, v):
        if not v or not v.landing_authorization:
            raise ValueError(
                "Landing event requires landing_authorization"
            )
        return v

