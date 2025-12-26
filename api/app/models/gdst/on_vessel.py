from typing import Optional
from app.models.gdst.base import EventTiming, GDSTEvent, IUUInfo, LocationInfo, OwnershipInfo, ProductInfo, VesselInfo


class OnVesselProcessingEvent(GDSTEvent):
    gdst_event_type: str = "OnVesselProcessing"

    vessel: VesselInfo
    who: OwnershipInfo
    what: ProductInfo
    where: LocationInfo
    when: EventTiming
    iuu: Optional[IUUInfo]
