import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.account import Account
from app.models.device import Device
from app.models.fraud_alert import AlertDecision, FraudAlert
from app.models.transaction import Transaction, TransactionStatus
from app.streaming.events import FraudAlertEvent, TransactionCreatedEvent
from app.streaming.publisher import event_publisher
from app.services.mitigation_service import MitigationService
from ml_pipeline.service import ml_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Worker) %(message)s")
logger = logging.getLogger("fraud_worker")


async def process_transaction_event(event_data: Dict[str, Any], db: Optional[AsyncSession] = None) -> Optional[FraudAlert]:
    """Consume transaction event, run feature engineering + ML risk scoring, and persist fraud alert."""
    if db is not None:
        return await _execute_event_processing(event_data, db)
    async with async_session_factory() as session:
        return await _execute_event_processing(event_data, session)


async def _execute_event_processing(event_data: Dict[str, Any], db: AsyncSession) -> Optional[FraudAlert]:
    tx_id_str = event_data.get("transaction_id")
    account_id_str = event_data.get("account_id")
    user_id_str = event_data.get("user_id")
    amount = float(event_data.get("amount", 0.0))
    device_fp = event_data.get("device_fingerprint")

    if not tx_id_str or not account_id_str:
        logger.warning("Invalid event payload missing identifiers: %s", event_data)
        return None

    tx_id = uuid.UUID(tx_id_str)
    account_id = uuid.UUID(account_id_str)
    user_id = uuid.UUID(user_id_str) if user_id_str else None

    logger.info("Processing transaction event %s for amount $%.2f", tx_id, amount)
    # 1. Fetch user transaction history for amount_z_score calculation
    history_stmt = (
        select(Transaction.Amount)
        .where(Transaction.AccountID == account_id)
        .order_by(Transaction.Timestamp.desc())
        .limit(30)
    )
    history_result = await db.execute(history_stmt)
    past_amounts = [float(a) for a in history_result.scalars().all()]

    # 2. Check if device fingerprint is known
    is_known_device = True
    if user_id and device_fp:
        dev_stmt = select(Device).where(
            Device.UserID == user_id, Device.DeviceFingerprint == device_fp
        )
        dev_record = (await db.execute(dev_stmt)).scalar_one_or_none()
        is_known_device = dev_record is not None

    # 3. ML Risk Scoring Service Execution
    scoring_result = ml_service.score_transaction(
        amount=amount,
        user_history_amounts=past_amounts,
        is_known_device=is_known_device,
    )

    risk_score = scoring_result["risk_score"]
    alert_level = scoring_result["alert_level"]
    decision = scoring_result["decision"]
    explanations = scoring_result["explanations"]

    logger.info(
        "ML Result -> RiskScore: %.2f | Level: %s | Decision: %s",
        risk_score,
        alert_level.value,
        decision.value,
    )

    # 4. Automated Mitigation response:
    await MitigationService.apply_mitigation(
        db=db,
        transaction_id=tx_id,
        account_id=account_id,
        amount=amount,
        decision=decision,
        alert_level=alert_level,
        risk_score=risk_score,
        explanations=explanations,
    )

    # Persist FraudAlert record
    alert = FraudAlert(
        TransactionID=tx_id,
        RiskScore=risk_score,
        AlertLevel=alert_level,
        Decision=decision,
        Explanations=explanations,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    # 5. Emit FraudAlertEvent to alerts topic
    alert_event = FraudAlertEvent(
        alert_id=str(alert.AlertID),
        transaction_id=str(tx_id),
        risk_score=risk_score,
        alert_level=alert_level.value,
        decision=decision.value,
        explanations=explanations,
    )
    await event_publisher.publish_event(
        topic_or_queue=settings.KAFKA_ALERTS_TOPIC,
        message=alert_event.model_dump(),
    )
    return alert


async def run_kafka_consumer() -> None:
    """Run Kafka streaming consumer loop."""
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        settings.KAFKA_TRANSACTION_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    logger.info("Kafka consumer started listening on topic '%s'...", settings.KAFKA_TRANSACTION_TOPIC)
    try:
        async for msg in consumer:
            await process_transaction_event(msg.value)
    finally:
        await consumer.stop()


async def main() -> None:
    """Worker entrypoint."""
    logger.info("Starting Streaming Fraud Detection Worker...")
    try:
        await run_kafka_consumer()
    except Exception as e:
        logger.warning("Kafka consumer could not connect (%s). Worker running in standby loop.", e)
        while True:
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
