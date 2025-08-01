from dataclasses import dataclass
from typing import Optional


@dataclass
class Listing:
    """Representation of a CSFloat market listing."""

    id: Optional[str]
    name: Optional[str]
    price: Optional[float]
    float_value: Optional[float]
    is_auction: Optional[bool]
