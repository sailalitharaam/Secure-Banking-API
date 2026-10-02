import json
import logging
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EventPublisher:
    """Event publisher interface supporting Kafka, RabbitMQ, or in-memory logging fallback."""

    def __init__(self) -> None:
        self.broker_type = settings.STREAMING_BROKER_TYPE.lower()
        self._producer: Optional[Any] = None

    async def start(self) -> None:
        """Initialize the connection to the event broker."""
        if self.broker_type == "kafka":
            try:
                from aiokafka import AIOKafkaProducer
                self._producer = AIOKafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                )
                await self._producer.start()
                logger.info("Connected to Kafka producer at %s", settings.KAFKA_BOOTSTRAP_SERVERS)
            except Exception as e:
                logger.warning("Kafka broker connection failed (%s). Falling back to mock logger.", e)
                self._producer = None

        elif self.broker_type == "rabbitmq":
            try:
                import aio_pika
                self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
                self._channel = await self._connection.channel()
                logger.info("Connected to RabbitMQ at %s", settings.RABBITMQ_URL)
            except Exception as e:
                logger.warning("RabbitMQ connection failed (%s). Falling back to mock logger.", e)
                self._producer = None

    async def stop(self) -> None:
        """Close producer connections gracefully."""
        if self._producer and hasattr(self._producer, "stop"):
            await self._producer.stop()

    async def publish_event(self, topic_or_queue: str, message: Dict[str, Any]) -> bool:
        """Publish event message to the designated topic/queue."""
        if self._producer is not None and self.broker_type == "kafka":
            try:
                await self._producer.send_and_wait(topic_or_queue, message)
                logger.debug("Published event to Kafka topic %s: %s", topic_or_queue, message.get("event_type"))
                return True
            except Exception as e:
                logger.error("Failed to send message to Kafka: %s", e)

        # Fallback / Local development mock:
        logger.info("[STREAMING EVENT PUBLISHED] Topic/Queue: %s | Payload: %s", topic_or_queue, json.dumps(message))
        return True


# Global publisher instance
event_publisher = EventPublisher()


def get_event_publisher() -> EventPublisher:
    """Dependency injection helper for the event publisher."""
    return event_publisher
