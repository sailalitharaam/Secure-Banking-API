import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.session import Session


class DeviceService:
    @staticmethod
    async def record_device_and_session(
        db: AsyncSession,
        user_id: uuid.UUID,
        device_fingerprint: str,
        device_type: str,
        ip_address: str,
        location: str = "Unknown",
    ) -> Session:
        """Find or create a Device for this user, and log a new active Session."""
        # Check if device fingerprint is already known for this user
        stmt = (
            select(Device)
            .where(Device.UserID == user_id, Device.DeviceFingerprint == device_fingerprint)
        )
        result = await db.execute(stmt)
        device = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if device is None:
            device = Device(
                UserID=user_id,
                DeviceFingerprint=device_fingerprint,
                DeviceType=device_type or "Unknown",
                LastUsedIP=ip_address,
                UpdatedAt=now,
            )
            db.add(device)
            await db.flush()
        else:
            device.LastUsedIP = ip_address
            device.UpdatedAt = now
            await db.flush()

        # Create new Session entry
        session_obj = Session(
            UserID=user_id,
            DeviceID=device.DeviceID,
            LoginTime=now,
            IPAddress=ip_address,
            Location=location,
            IsActive=True,
        )
        db.add(session_obj)
        await db.flush()

        return session_obj
