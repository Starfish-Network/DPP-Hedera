"""Minimum-validation event model for the /events route.

`event_type` and `event_time` are required; everything else is permitted via
`extra="allow"`. A 256 KB serialized-size cap prevents runaway payloads —
generic events that big are almost certainly an attached blob that should
be a CID reference instead.
"""
from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_PAYLOAD_BYTES = 256 * 1024


class GenericEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_type: str = Field(..., min_length=1, description="Free-form event type identifier.")
    event_time: datetime = Field(..., description="ISO-8601 timestamp when the event occurred.")

    @model_validator(mode="after")
    def _enforce_size_cap(self) -> "GenericEvent":
        size = len(json.dumps(self.model_dump(mode="json")).encode())
        if size > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"payload too large ({size} bytes > {MAX_PAYLOAD_BYTES} cap). "
                f"Attach blobs as CID references via /events/{{hash}}/attach instead."
            )
        return self
