from pydantic import BaseModel, Field
from typing import List, Optional, Union

class QuantityItem(BaseModel):
    epc: str = Field(..., example="urn:epc:class:lgtin:9506000.1233.a")
    quantity: float = Field(..., example=12.0)
    unit_of_measurement: str = Field(..., example="kg")

class BaseEvent(BaseModel):
    event_time: str = Field(..., example="2025-10-03T12:08:00.000Z")
    event_timezone_offset: str = Field(..., example="+01:00")

# Creating event
class CreatingEvent(BaseEvent):
    eventType: str = Field("creating", Literal=True)
    biz_location: str = Field(..., example="9506001112229")
    quantity_list: List[QuantityItem]

# Shipping event
class ShippingEvent(BaseEvent):
    eventType: str = Field("shipping", Literal=True)
    ship_from: str
    ship_to: str
    items: List[QuantityItem]

# Receiving event
class ReceivingEvent(BaseEvent):
    eventType: str = Field("receiving", Literal=True)
    shipped_from: str
    received_at: str
    items: List[QuantityItem]

# Transforming event
class TransformingEvent(BaseEvent):
    eventType: str = Field("transforming", Literal=True)
    facility: str
    transformation_id: Optional[str] = None
    input_items: List[QuantityItem]
    output_items: List[QuantityItem]

# Packing event
class PackingEvent(BaseEvent):
    eventType: str = Field("packing", Literal=True)
    facility: str
    container_id: str
    input_items: List[QuantityItem]

# Unpacking event
class UnpackingEvent(BaseEvent):
    eventType: str = Field("unpacking", Literal=True)
    facility: str
    container_id: str
    output_items: List[QuantityItem]

StarfishEvent = Union[
    CreatingEvent,
    ShippingEvent,
    ReceivingEvent,
    TransformingEvent,
    PackingEvent,
    UnpackingEvent,
]

