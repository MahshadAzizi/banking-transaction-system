from __future__ import annotations

from typing import NewType
from uuid import UUID, uuid4

AccountId = NewType("AccountId", UUID)
TransactionId = NewType("TransactionId", UUID)
OwnerId = NewType("OwnerId", UUID)
IdempotencyKey = NewType("IdempotencyKey", str)


def new_account_id() -> AccountId:
    return AccountId(uuid4())


def new_transaction_id() -> TransactionId:
    return TransactionId(uuid4())


def new_owner_id() -> OwnerId:
    return OwnerId(uuid4())
