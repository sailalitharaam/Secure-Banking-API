import uuid
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.account import Account
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User, UserRole
from app.schemas.transaction import TransferRequest, TransactionResponse
from app.streaming.events import TransactionCreatedEvent
from app.streaming.publisher import event_publisher


class TransactionService:
    @staticmethod
    async def transfer_funds(
        db: AsyncSession,
        current_user: User,
        payload: TransferRequest,
        client_ip: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> TransactionResponse:
        """Execute an atomic fund transfer using row-level locking (with_for_update()) to prevent race conditions."""
        if payload.SenderAccountID == payload.ReceiverAccountID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sender and receiver accounts must be different.",
            )

        if payload.Amount <= Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer amount must be strictly greater than zero.",
            )

        # Order account IDs deterministically to prevent database deadlocks
        first_id, second_id = (
            (payload.SenderAccountID, payload.ReceiverAccountID)
            if payload.SenderAccountID < payload.ReceiverAccountID
            else (payload.ReceiverAccountID, payload.SenderAccountID)
        )

        # Acquire pessimistic row-level locks on both accounts
        stmt_first = select(Account).where(Account.AccountID == first_id).with_for_update()
        stmt_second = select(Account).where(Account.AccountID == second_id).with_for_update()

        acc_first = (await db.execute(stmt_first)).scalar_one_or_none()
        acc_second = (await db.execute(stmt_second)).scalar_one_or_none()

        sender = acc_first if first_id == payload.SenderAccountID else acc_second
        receiver = acc_second if first_id == payload.SenderAccountID else acc_first

        if not sender:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sender account {payload.SenderAccountID} not found.",
            )
        if not receiver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Receiver account {payload.ReceiverAccountID} not found.",
            )

        # Enforce account ownership: only account owner or Bank Admin can transfer out
        if current_user.Role != UserRole.BANK_ADMIN and sender.UserID != current_user.UserID:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You do not own the source account.",
            )

        # Check sufficient funds
        if sender.Balance < payload.Amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient funds. Current balance: {sender.Balance}, requested: {payload.Amount}.",
            )

        # Perform atomic transfer
        sender.Balance -= payload.Amount
        receiver.Balance += payload.Amount

        # Create immutable transaction record
        tx = Transaction(
            AccountID=sender.AccountID,
            Amount=payload.Amount,
            TransactionType=TransactionType.TRANSFER,
            SenderAccount=str(sender.AccountID),
            ReceiverAccount=str(receiver.AccountID),
            Status=TransactionStatus.PENDING,  # Marked PENDING until AI risk scoring confirms or auto-approves
        )
        db.add(tx)
        await db.commit()
        await db.refresh(tx)

        # Publish event to streaming pipeline (Kafka/RabbitMQ) for asynchronous real-time ML risk scoring
        event = TransactionCreatedEvent(
            transaction_id=str(tx.TransactionID),
            account_id=str(tx.AccountID),
            user_id=str(current_user.UserID),
            amount=float(tx.Amount),
            sender_account=tx.SenderAccount,
            receiver_account=tx.ReceiverAccount,
            device_fingerprint=device_fingerprint,
            ip_address=client_ip,
        )
        await event_publisher.publish_event(
            topic_or_queue=settings.KAFKA_TRANSACTION_TOPIC,
            message=event.model_dump(),
        )

        return TransactionResponse.model_validate(tx)
