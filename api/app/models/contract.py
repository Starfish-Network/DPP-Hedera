from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List

class EventType(str, Enum):
    CREATE = "creating"
    SHIP = "shipping"
    RECEIVE = "receiving"
    TRANSFORM = "transforming"
    PACK = "packing"
    UNPACK = "unpacking"

class QuantityItem(BaseModel):
    epc: str
    quantity: Optional[float] = None
    unit_of_measurement: Optional[str] = None

class ComplianceEvent(BaseModel):
    eventType: EventType = Field(..., description="Event type")
    event_time: str = Field(..., description="ISO8601 timestamp")
    event_timezone_offset: Optional[str] = None

    # Creating
    biz_location: Optional[str] = None
    quantity_list: Optional[List[QuantityItem]] = None

    # Shipping / Receiving — snake_case to match the on-disk FSMA samples and
    # the field names checked by `fsma_min_rules`. Pydantic was previously
    # camelCase here, which silently dropped the snake_case keys on parse and
    # made every shipping/receiving event fail the compliance predicate.
    ship_from: Optional[str] = None
    ship_to: Optional[str] = None
    shipped_from: Optional[str] = None
    received_at: Optional[str] = None
    items: Optional[List[QuantityItem]] = None

    # Transforming
    facility: Optional[str] = None
    transformation_id: Optional[str] = None
    input_items: Optional[List[QuantityItem]] = None
    output_items: Optional[List[QuantityItem]] = None

    # Packing / Unpacking
    container_id: Optional[str] = None