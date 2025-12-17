from typing import Optional, List, Annotated
from datetime import datetime
from pydantic import BaseModel, Field, confloat, validator
from api.app.models.gdst.constraints import GTIN, UNECE_UOM, EventID, FAOASFISCode, FAOFishingArea, ISO3166Alpha2

class VesselInfo(BaseModel):
    vessel_name: Optional[str]
    vessel_registration: Optional[str]
    vessel_id: Optional[str] = Field(
        description="IMO number or national vessel ID"
    )
    public_registry_url: Optional[str]
    vessel_flag: Optional[ISO3166Alpha2]


class OwnershipInfo(BaseModel):
    product_owner: Optional[str]
    information_provider: Optional[str]

class ProductInfo(BaseModel):
    species: FAOASFISCode
    product_form: Optional[str]
    item_sku_upc_gtin: Optional[GTIN]
    linking_kde: Optional[str] = Field(
        description="Batch, lot, or serial number"
    )
    quantity: Annotated[float, Field(gt=0)]
    unit_of_measure: UNECE_UOM

class GeoLocation(BaseModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]

class LocationInfo(BaseModel):
    event_read_point: Optional[GeoLocation]
    source_location: Optional[str]
    destination_location: Optional[str]
    catch_area: Optional[FAOFishingArea]
    product_origin: Optional[str]

class EventTiming(BaseModel):
    event_id: EventID
    event_datetime: datetime
    timezone: Optional[str]

    capture_date: Optional[datetime]
    landing_date: Optional[datetime]
    production_date: Optional[datetime]
    expiration_date: Optional[datetime]

    @validator("expiration_date")
    def expiration_after_production(cls, v, values):
        prod = values.get("production_date")
        if v and prod and v <= prod:
            raise ValueError("expiration_date must be after production_date")
        return v

class IUUInfo(BaseModel):
    chain_of_custody_certification: Optional[str]

    fishing_authorization: Optional[str]
    landing_authorization: Optional[str]
    transshipment_authorization: Optional[str]
    harvest_certification: Optional[str]

    production_method: Optional[str]
    gear_type: Optional[str]

    human_welfare_policy_exists: Optional[bool]
    human_welfare_policy_standards: Optional[str]

    @validator("human_welfare_policy_standards")
    def standards_require_policy(cls, v, values):
        if v and not values.get("human_welfare_policy_exists"):
            raise ValueError(
                "human_welfare_policy_standards provided but policy existence is false or missing"
            )
        return v


class GDSTEvent(BaseModel):
    gdst_event_type: str
    who: OwnershipInfo
    what: ProductInfo
    where: LocationInfo
    when: EventTiming
    iuu: Optional[IUUInfo]

    @validator("gdst_event_type")
    def valid_gdst_event_type(cls, v):
        allowed = {
            "Fishing",
            "OnVesselProcessing",
            "Transshipment",
            "Landing",
            "AggregationDisaggregation",
            "ShippingReceiving",
            "Processing"
        }
        if v not in allowed:
            raise ValueError(f"Invalid GDST event type: {v}")
        return v