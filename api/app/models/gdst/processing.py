from typing import Optional
from api.app.models.gdst.base import EventTiming, GDSTEvent, IUUInfo, LocationInfo, OwnershipInfo, ProductInfo


class ProcessingEvent(GDSTEvent):
    gdst_event_type: str = "Processing"

    who: OwnershipInfo
    what: ProductInfo
    where: LocationInfo
    when: EventTiming
    iuu: Optional[IUUInfo]
