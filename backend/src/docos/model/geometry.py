"""Page-space geometry primitives used to preserve layout fidelity."""

from __future__ import annotations

from pydantic import BaseModel


class Point(BaseModel):
    x: float
    y: float


class BBox(BaseModel):
    """Axis-aligned bounding box in page-space coordinates (points, top-left origin)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0
