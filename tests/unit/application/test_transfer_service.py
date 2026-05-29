from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.dtos.transaction import TransactionDTO
from src.domain.exceptions.account import InsufficientFundsError
from src.domain.exceptions.base import ConcurrencyConflictError, ResourceNotFoundError
from src.domain.value_objects.enums import TransactionStatus
from src.domain.value_objects.identifiers import AccountId
from tests.conftest import make_account, make_transfer_command


class TestTransferHappyPath:
    async def test_successful_transfer_returns_completed_dto(
        self, transfer_service, account_repo
    ):
        sender = make_account(balance=Decimal("500"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        cmd = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver.id),
            amount=Decimal("100"),
        )
        result = await transfer_service.initiate(cmd)

        assert isinstance(result, TransactionDTO)
        assert result.status == TransactionStatus.COMPLETED.value
        assert result.amount == Decimal("100")

    async def test_balances_updated_correctly(self, transfer_service, account_repo):
        sender = make_account(balance=Decimal("500"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        cmd = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver.id),
            amount=Decimal("150"),
        )
        await transfer_service.initiate(cmd)

        updated_sender = await account_repo.get(AccountId(sender.id))
        updated_receiver = await account_repo.get(AccountId(receiver.id))

        assert updated_sender.balance.amount == Decimal("350.00")
        assert updated_receiver.balance.amount == Decimal("150.00")

    async def test_events_published_after_commit(
        self, transfer_service, account_repo, event_bus
    ):
        sender = make_account(balance=Decimal("500"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        cmd = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver.id),
        )
        await transfer_service.initiate(cmd)

        assert len(event_bus.published) > 0
        event_types = [type(e).__name__ for e in event_bus.published]
        assert "BalanceDebited" in event_types
        assert "BalanceCredited" in event_types


class TestIdempotency:
    """
    Idempotency guarantee:
    The same idempotency_key always returns the same TransactionDTO.
    No matter how many times the client retries, the transfer executes once.
    """

    async def test_same_key_returns_same_transaction(
        self, transfer_service, account_repo
    ):
        sender = make_account(balance=Decimal("500"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        key = str(uuid4())
        cmd = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver.id),
            idempotency_key=key,
        )

        result_1 = await transfer_service.initiate(cmd)
        result_2 = await transfer_service.initiate(cmd)  # same command, same key

        assert result_1.id == result_2.id
        assert result_1.status == result_2.status

    async def test_duplicate_does_not_debit_sender_twice(
        self, transfer_service, account_repo
    ):
        sender = make_account(balance=Decimal("500"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        key = str(uuid4())
        cmd = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver.id),
            amount=Decimal("100"),
            idempotency_key=key,
        )

        await transfer_service.initiate(cmd)
        await transfer_service.initiate(cmd)  # retry
        await transfer_service.initiate(cmd)  # retry again

        # Balance debited exactly once despite three calls
        final_sender = await account_repo.get(AccountId(sender.id))
        assert final_sender.balance.amount == Decimal("400.00")

    async def test_different_keys_are_independent_transfers(
        self, transfer_service, account_repo
    ):
        sender = make_account(balance=Decimal("500"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        result_1 = await transfer_service.initiate(
            make_transfer_command(
                AccountId(sender.id),
                AccountId(receiver.id),
                amount=Decimal("100"),
                idempotency_key=str(uuid4()),
            )
        )
        result_2 = await transfer_service.initiate(
            make_transfer_command(
                AccountId(sender.id),
                AccountId(receiver.id),
                amount=Decimal("100"),
                idempotency_key=str(uuid4()),
            )
        )

        assert result_1.id != result_2.id
        final_sender = await account_repo.get(AccountId(sender.id))
        assert final_sender.balance.amount == Decimal("300.00")  # debited twice


class TestInsufficientFunds:
    async def test_transfer_fails_on_insufficient_funds(
        self, transfer_service, account_repo
    ):
        sender = make_account(balance=Decimal("50"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        cmd = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver.id),
            amount=Decimal("100"),
        )

        with pytest.raises(InsufficientFundsError):
            await transfer_service.initiate(cmd)

    async def test_failed_transfer_does_not_change_balances(
        self, transfer_service, account_repo
    ):
        sender = make_account(balance=Decimal("50"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        cmd = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver.id),
            amount=Decimal("100"),
        )

        with pytest.raises(InsufficientFundsError):
            await transfer_service.initiate(cmd)

        final_sender = await account_repo.get(AccountId(sender.id))
        final_receiver = await account_repo.get(AccountId(receiver.id))

        assert final_sender.balance.amount == Decimal("50.00")
        assert final_receiver.balance.amount == Decimal("0.00")

    async def test_account_not_found_raises(self, transfer_service, account_repo):
        account_repo.add(make_account())
        cmd = make_transfer_command(
            from_account_id=AccountId(uuid4()),  # non-existent
            to_account_id=AccountId(uuid4()),
        )
        with pytest.raises(ResourceNotFoundError):
            await transfer_service.initiate(cmd)


class TestConcurrency:
    """
    Double-spend prevention:
    Two concurrent transfers that together exceed the sender's balance
    must result in exactly one succeeding and one failing.

    This test uses InMemoryLockManager which raises ConcurrencyConflictError
    when the same account is locked by two concurrent operations.
    The real Redis + SELECT FOR UPDATE provides the same guarantee in production.
    """

    async def test_concurrent_transfers_no_double_spend(
        self, transfer_service, account_repo
    ):
        # Sender has EUR 400 — only enough for ONE transfer of EUR 300
        sender = make_account(balance=Decimal("400"))
        receiver_a = make_account(balance=Decimal("0"))
        receiver_b = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver_a)
        account_repo.add(receiver_b)

        cmd_a = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver_a.id),
            amount=Decimal("300"),
        )
        cmd_b = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver_b.id),
            amount=Decimal("300"),
        )

        results = await asyncio.gather(
            transfer_service.initiate(cmd_a),
            transfer_service.initiate(cmd_b),
            return_exceptions=True,
        )

        successes = [r for r in results if isinstance(r, TransactionDTO)]
        failures = [r for r in results if isinstance(r, Exception)]

        # Exactly one transfer must succeed
        assert len(successes) == 1
        assert len(failures) == 1

        # The failure must be a domain exception — not a silent data corruption
        assert isinstance(
            failures[0],
            (ConcurrencyConflictError, InsufficientFundsError),
        )

        # Total money in the system is conserved
        final_sender = await account_repo.get(AccountId(sender.id))
        final_a = await account_repo.get(AccountId(receiver_a.id))
        final_b = await account_repo.get(AccountId(receiver_b.id))
        total = (
            final_sender.balance.amount
            + final_a.balance.amount
            + final_b.balance.amount
        )
        assert total == Decimal("400.00")  # no money created or destroyed

    async def test_same_idempotency_key_concurrent_safe(
        self, transfer_service, account_repo
    ):
        """Two concurrent requests with the same idempotency key.
        Both should return the same result — only one transfer executes."""
        sender = make_account(balance=Decimal("500"))
        receiver = make_account(balance=Decimal("0"))
        account_repo.add(sender)
        account_repo.add(receiver)

        key = str(uuid4())
        cmd = make_transfer_command(
            from_account_id=AccountId(sender.id),
            to_account_id=AccountId(receiver.id),
            amount=Decimal("100"),
            idempotency_key=key,
        )

        results = await asyncio.gather(
            transfer_service.initiate(cmd),
            transfer_service.initiate(cmd),
            return_exceptions=True,
        )

        successful = [r for r in results if isinstance(r, TransactionDTO)]
        # At least one must succeed; both may succeed with same transaction ID
        assert len(successful) >= 1
        if len(successful) == 2:
            assert successful[0].id == successful[1].id

        # Balance debited exactly once
        final_sender = await account_repo.get(AccountId(sender.id))
        assert final_sender.balance.amount == Decimal("400.00")
