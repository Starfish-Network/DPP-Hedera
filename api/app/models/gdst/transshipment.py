from pydantic import validator
from api.app.models.gdst.base import GDSTEvent, VesselInfo

class TransshipmentEvent(GDSTEvent):
    gdst_event_type: str = "Transshipment"

    transshipment_vessel: VesselInfo

    @validator("iuu")
    def transshipment_requires_authorization(cls, v):
        if not v or not v.transshipment_authorization:
            raise ValueError(
                "Transshipment event requires transshipment_authorization"
            )
        return v
