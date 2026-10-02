import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DeviceCreate(BaseModel):
    DeviceFingerprint: str
    DeviceType: str = "Web Browser"
    LastUsedIP: str = "127.0.0.1"


class DeviceResponse(BaseModel):
    DeviceID: uuid.UUID
    UserID: uuid.UUID
    DeviceFingerprint: str
    DeviceType: str
    LastUsedIP: str
    UpdatedAt: datetime

    model_config = ConfigDict(from_attributes=True)
