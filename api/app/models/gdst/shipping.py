from typing import Optional
from app.models.gdst.base import EventTiming, GDSTEvent, IUUInfo, LocationInfo, OwnershipInfo, ProductInfo


class ShippingReceivingEvent(GDSTEvent):
    gdst_event_type: str = "ShippingReceiving"

    who: OwnershipInfo
    what: ProductInfo
    where: LocationInfo
    when: EventTiming
    iuu: Optional[IUUInfo]
