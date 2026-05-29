from __future__ import annotations

from decimal import Decimal

from src.adapters.outbound.persistence.models import AccountORM
from src.domain.entities.account import Account
from src.domain.value_objects.enums import AccountStatus, Currency
from src.domain.value_objects.identifiers import AccountId, OwnerId
from src.domain.value_objects.money import Money


class AccountMapper:
    """
    Translates between AccountORM (infrastructure) and Account (domain).

    Three responsibilities, three methods:
      to_domain()   → ORM row → domain aggregate (always)
      to_new_orm()  → domain aggregate → new ORM row (INSERT only)
      update_orm()  → mutate existing ORM row in-place (UPDATE only)

    WHY split to_new_orm and update_orm instead of one to_orm():
      SQLAlchemy tracks ORM objects in its identity map (the session).
      Creating a NEW AccountORM(...) for an update causes one of:
        - Duplicate INSERT if the object isn't already in the session
        - DetachedInstanceError if it is
      The correct pattern for UPDATE is to MUTATE the tracked instance.
      to_new_orm() is only called on first save (INSERT).
      update_orm() is called on every subsequent save (UPDATE).
    """

    @staticmethod
    def to_domain(orm: AccountORM) -> Account:
        balance = Money(
            amount=Decimal(str(orm.balance)),
            currency=Currency(orm.currency),
        )
        return Account.reconstitute(
            id=AccountId(orm.id),
            owner_id=OwnerId(orm.owner_id),
            account_number=orm.account_number,
            balance=balance,
            status=AccountStatus(orm.status),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def to_new_orm(account: Account) -> AccountORM:
        """
        Build a new ORM row from a domain aggregate.
        Call this ONLY when inserting for the first time.
        For updates, call update_orm() instead.
        """
        return AccountORM(
            id=account.id,
            owner_id=account.owner_id,
            account_number=account.account_number,
            balance=account.balance.amount,
            currency=account.balance.currency.value,
            status=account.status.value,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

    @staticmethod
    def update_orm(orm: AccountORM, account: Account) -> None:
        """
        Mutate an existing tracked ORM instance with domain aggregate state.
        Call this for every UPDATE — never create a new ORM object for updates.

        Only mutable fields are updated here.
        id, owner_id, account_number, created_at are immutable after creation.

        WHY version must be updated:
        Optimistic locking requires the new version to be persisted.
        The repository then does:
          UPDATE accounts SET ... WHERE id=:id AND version=:expected_version
        If version is stale in the ORM row, the check always fails.
        """
        orm.balance = account.balance.amount
        orm.currency = account.balance.currency.value
        orm.status = account.status.value
        orm.updated_at = account.updated_at
