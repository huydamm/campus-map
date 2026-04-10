from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class Location(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    type: str
    latitude: float
    longitude: float
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Report(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    location_id: UUID = Field(foreign_key="location.id")
    noise_level: int
    occupancy_estimate: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
