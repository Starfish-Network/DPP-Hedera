from typing import List, Optional
from api.app.models.gdst.base import EventTiming, GDSTEvent, IUUInfo, LocationInfo, OwnershipInfo, ProductInfo


class AggregationEvent(GDSTEvent):
    gdst_event_type: str = "AggregationDisaggregation"

    parent_items: Optional[List[str]]
    child_items: Optional[List[str]]

    who: OwnershipInfo
    what: ProductInfo
    where: LocationInfo
    when: EventTiming
    iuu: Optional[IUUInfo]
