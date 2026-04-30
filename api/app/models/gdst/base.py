from typing import Optional, Annotated
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, validator
from app.models.gdst.constraints import GTIN, UNECE_UOM, EventID, FAOASFISCode, FAOFishingArea, ISO3166Alpha2

class VesselInfo(BaseModel):
    vessel_name: Optional[str] = None
    vessel_registration: Optional[str] = None
    vessel_id: Optional[str] = Field(default=None, description="IMO number or national vessel ID")
    public_registry_url: Optional[str] = None
    vessel_flag: Optional[ISO3166Alpha2] = None


class OwnershipInfo(BaseModel):
    product_owner: Optional[str] = None
    information_provider: Optional[str] = None

class ProductInfo(BaseModel):
    species: FAOASFISCode
    product_form: Optional[str] = None
    item_sku_upc_gtin: Optional[GTIN] = None
    linking_kde: Optional[str] = Field(default=None, description="Batch, lot, or serial number")
    quantity: Annotated[float, Field(gt=0)]
    unit_of_measure: UNECE_UOM

class GeoLocation(BaseModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]

class LocationInfo(BaseModel):
    event_read_point: Optional[GeoLocation] = None
    source_location: Optional[str] = None
    destination_location: Optional[str] = None
    catch_area: Optional[FAOFishingArea] = None
    product_origin: Optional[str] = None

class EventTiming(BaseModel):
    event_id: EventID
    event_datetime: datetime
    timezone: Optional[str] = None

    capture_date: Optional[datetime] = None
    landing_date: Optional[datetime] = None
    production_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None

    @validator("expiration_date")
    def expiration_after_production(cls, v, values):
        prod = values.get("production_date")
        if v and prod and v <= prod:
            raise ValueError("expiration_date must be after production_date")
        return v

class IUUInfo(BaseModel):
    chain_of_custody_certification: Optional[str] = None

    fishing_authorization: Optional[str] = None
    landing_authorization: Optional[str] = None
    transshipment_authorization: Optional[str] = None
    harvest_certification: Optional[str] = None

    production_method: Optional[str] = None
    gear_type: Optional[str] = None

    human_welfare_policy_exists: Optional[bool] = None
    human_welfare_policy_standards: Optional[str] = None

    @validator("human_welfare_policy_standards")
    def standards_require_policy(cls, v, values):
        if v and not values.get("human_welfare_policy_exists"):
            raise ValueError(
                "human_welfare_policy_standards provided but policy existence is false or missing"
            )
        return v


class GDSTEvent(BaseModel):
    # `extra="allow"` lets subclass-specific KDEs (vessel, transshipment_vessel,
    # parent_items / child_items, etc.) flow through the base when the route
    # accepts `evt: GDSTEvent`. Without this, FastAPI's default `extra="ignore"`
    # silently drops them, breaking gdst_min_rules' OR-clauses (e.g. "vessel.vessel_id
    # OR vessel.vessel_name" never matches when `vessel` itself was stripped).
    # The proper fix is a Literal-typed discriminated union over the subclasses
    # (route uses `Annotated[Union[FishingEvent, ...], Field(discriminator="gdst_event_type")]`),
    # but that requires Literal types on every subclass — deferred. See spec
    # 002-demo-ui T018 follow-up.
    model_config = ConfigDict(extra="allow")

    gdst_event_type: str
    who: OwnershipInfo
    what: ProductInfo
    where: LocationInfo
    when: EventTiming
    iuu: Optional[IUUInfo] = None

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