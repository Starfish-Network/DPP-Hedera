from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Union

class QuantityItem(BaseModel):
    epc: str = Field(..., example="urn:epc:class:lgtin:9506000.1233.a")
    quantity: float = Field(..., example=12.0)
    unit_of_measurement: str = Field(..., example="kg")

class BaseEvent(BaseModel):
    event_time: str = Field(..., example="2025-10-03T12:08:00.000Z")
    event_timezone_offset: str = Field(..., example="+01:00")

# Creating event
class CreatingEvent(BaseEvent):
    eventType: Literal["creating"] = "creating"
    biz_location: str = Field(..., example="9506001112229")
    quantity_list: List[QuantityItem] = Field(..., min_length=1)

# Shipping event
class ShippingEvent(BaseEvent):
    eventType: Literal["shipping"] = "shipping"
    ship_from: str
    ship_to: str
    items: List[QuantityItem] = Field(..., min_length=1)

# Receiving event
class ReceivingEvent(BaseEvent):
    eventType: Literal["receiving"] = "receiving"
    shipped_from: str
    received_at: str
    items: List[QuantityItem] = Field(..., min_length=1)

# Transforming event
class TransformingEvent(BaseEvent):
    eventType: Literal["transforming"] = "transforming"
    facility: str
    transformation_id: Optional[str] = None
    input_items: List[QuantityItem] = Field(..., min_length=1)
    output_items: List[QuantityItem] = Field(..., min_length=1)

# Packing event
class PackingEvent(BaseEvent):
    eventType: Literal["packing"] = "packing"
    facility: str
    container_id: str
    input_items: List[QuantityItem] = Field(..., min_length=1)

# Unpacking event
class UnpackingEvent(BaseEvent):
    eventType: Literal["unpacking"] = "unpacking"
    facility: str
    container_id: str
    output_items: List[QuantityItem] = Field(..., min_length=1)

StarfishEvent = Union[
    CreatingEvent,
    ShippingEvent,
    ReceivingEvent,
    TransformingEvent,
    PackingEvent,
    UnpackingEvent,
]

