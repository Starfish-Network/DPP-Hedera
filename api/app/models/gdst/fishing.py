from pydantic import validator
from api.app.models.gdst.base import GDSTEvent, VesselInfo


class FishingEvent(GDSTEvent):
    gdst_event_type: str = "Fishing"

    vessel: VesselInfo

    @validator("where")
    def fishing_requires_catch_area_or_coords(cls, v):
        if not v.catch_area and not v.event_read_point:
            raise ValueError(
                "Fishing event requires catch_area or geo coordinates"
            )
        return v

    @validator("iuu")
    def fishing_requires_authorization(cls, v):
        if not v or not v.fishing_authorization:
            raise ValueError(
                "Fishing event requires fishing_authorization"
            )
        return v

