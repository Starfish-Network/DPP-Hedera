from typing import Annotated
from pydantic import StringConstraints

ISO3166Alpha2 = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z]{2}$", min_length=2, max_length=2)
]

FAOFishingArea = Annotated[
    str,
    StringConstraints(pattern=r"^FAO\d{2,3}$")
]

FAOASFISCode = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z]{3}$")
]

UNECE_UOM = Annotated[
    str,
    StringConstraints(pattern=r"^(KGM|TNE|LBR|EA)$")
]

GTIN = Annotated[
    str,
    StringConstraints(pattern=r"^(\d{8}|\d{12}|\d{13}|\d{14})$")
]

EventID = Annotated[
    str,
    StringConstraints(min_length=6, max_length=64)
]