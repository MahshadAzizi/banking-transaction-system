from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from src.application.dtos.transaction import TransferCommand, TransactionDTO
from src.application.ports.inbound.transfer_service import ITransferService
from src.application.ports.outbound.event_bus import IEventBus
from src.application.ports.outbound.lock_manager import ILockManager
from src.application.ports.outbound.unit_of_work import IUnitOfWork
from src.domain.entities.transaction import Transaction
from src.domain.exceptions.base import ResourceNotFoundError
from src.domain.value_objects.enums import Currency
from src.domain.value_objects.identifiers import (
    IdempotencyKey,
    AccountId,
    TransactionId,
)
from src.domain.value_objects.money import Money
from src.infrastructure.logging.setup import get_logger

logger = get_logger(__name__)


class TransferService(ITransferService):
    """
    Orchestrates the full money transfer flow.

    This class has zero imports from FastAPI, SQLAlchemy, Redis, or Kafka.
    All infrastructure is injected as Protocol interfaces.

    The full sequence for execute():
        1. Idempotency check   — Redis fast path, return immediately if hit
        2. Distributed lock    — Redis Redlock on both account IDs (sorted)
        3. UoW / BEGIN         — open DB transaction
        4. Load accounts       — SELECT FOR UPDATE on both rows
        5. Domain calls        — Transaction.initiate(), sender.debit(),
                                 receiver.credit(), tx.complete()
        6. Persist             — save accounts + transaction via UoW
        7. Commit              — balances + outbox events atomic COMMIT
        8. Publish events      — collect from aggregates, push to bus
        9. Cache result        — Redis SET with TTL for future retries

    Any exception between steps 3–7 triggers automatic rollback
    via UoW.__aexit__. The distributed lock releases on context exit.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        lock_manager: ILockManager,
        event_bus: IEventBus,
    ) -> None:
        self._uow = uow
        self._lock = lock_manager
        self._bus = event_bus

    async def initiate(self, command: TransferCommand) -> TransactionDTO:
        idempotency_key = IdempotencyKey(command.idempotency_key)

        # ── Step 1: idempotency check via UoW ─────────────────────────────
        async with self._uow as uow:
            existing = await uow.transactions.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            logger.info(
                "transfer_duplicate_detected",
                idempotency_key=command.idempotency_key,
                existing_transaction_id=str(existing.id),
            )
            return TransactionDTO.from_aggregate(existing)

        # ── Step 2: build domain value objects ────────────────────────────
        from_id = AccountId(command.from_account_id)
        to_id = AccountId(command.to_account_id)
        currency = Currency(command.currency)
        amount = Money(amount=Decimal(str(command.amount)), currency=currency)

        # ── Step 3: distributed lock ──────────────────────────────────────
        lock_keys = sorted([str(from_id), str(to_id)])
        logger.debug("acquiring_distributed_lock", keys=lock_keys)
        async with self._lock.acquire(*lock_keys):
            logger.debug("lock_acquired", keys=lock_keys)
            # ── Step 4: open DB transaction ───────────────────────────────
            async with self._uow as uow:
                # ── Step 5: load accounts with row-level DB lock ──────────
                sender = await uow.accounts.get_with_lock(from_id)
                if sender is None:
                    raise ResourceNotFoundError("Account", from_id)

                receiver = await uow.accounts.get_with_lock(to_id)
                if receiver is None:
                    raise ResourceNotFoundError("Account", to_id)

                # ── Step 6: create transaction record ─────────────────────
                tx = Transaction.initiate(
                    from_account_id=from_id,
                    to_account_id=to_id,
                    amount=amount,
                    idempotency_key=idempotency_key,
                )
                try:
                    # ── Step 7: advance state + apply balance changes ──────
                    tx.mark_processing()
                    sender.debit(amount, tx.id)  # raises InsufficientFundsError
                    receiver.credit(amount, tx.id)  # raises AccountFrozenError etc.
                    tx.complete()

                except Exception as exc:
                    logger.warning(
                        "transfer_failed",
                        transaction_id=str(tx.id),
                        failure_code=type(exc).__name__,
                        failure_reason=str(exc),
                        from_account=str(from_id),
                        to_account=str(to_id),
                        amount=str(amount.amount),
                    )
                    failure_code = type(exc).__name__.upper().replace("ERROR", "")
                    tx.fail(
                        failure_code=failure_code,
                        failure_reason=str(exc),
                    )

                    await uow.transactions.save(tx)
                    await uow.commit()
                    raise

                # ── Step 8: persist all changes ───────────────────────────
                await uow.accounts.update(sender)
                await uow.accounts.update(receiver)
                await uow.transactions.save(tx)

                # ── Step 9: atomic COMMIT ─────────────────────────────────
                await uow.commit()
        # ── Step 10: publish domain events ────────────────────────────────

        events = [
            *sender.collect_events(),
            *receiver.collect_events(),
            *tx.collect_events(),
        ]
        if events:
            await self._bus.publish_many(events)

        logger.info(
            "transfer_completed",
            transaction_id=str(tx.id),
            from_account=str(from_id),
            to_account=str(to_id),
            amount=str(amount.amount),
            currency=command.currency,
        )

        return TransactionDTO.from_aggregate(tx)

    async def get(self, transaction_id: UUID) -> TransactionDTO:
        async with self._uow as uow:
            tx = await uow.transactions.get(TransactionId(transaction_id))
            if tx is None:
                raise ResourceNotFoundError("Transaction", transaction_id)
            return TransactionDTO.from_aggregate(tx)
