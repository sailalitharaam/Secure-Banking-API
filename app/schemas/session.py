import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    DeviceID: uuid.UUID
    IPAddress: str
    Location: str = "Unknown"


class SessionResponse(BaseModel):
    SessionID: uuid.UUID
    UserID: uuid.UUID
    DeviceID: uuid.UUID
    LoginTime: datetime
    IPAddress: str
    Location: str
    IsActive: bool

    model_config = ConfigDict(from_attributes=True)
