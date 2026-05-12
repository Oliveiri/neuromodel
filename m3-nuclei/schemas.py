from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing import List, Optional


class SampleMeta(BaseModel):
    tileId: str
    imageRef: str
    mpp: float
    level: Optional[int] = None
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None


class BatchManifest(BaseModel):
    requestId: Optional[str] = None
    samples: List[SampleMeta] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_uniqueness(self):
        tile_ids = [s.tileId for s in self.samples]
        if len(tile_ids) != len(set(tile_ids)):
            raise ValueError("tileId must be unique within a batch request")
        refs = [s.imageRef for s in self.samples]
        if len(refs) != len(set(refs)):
            raise ValueError("imageRef must be unique within a batch request")
        return self
