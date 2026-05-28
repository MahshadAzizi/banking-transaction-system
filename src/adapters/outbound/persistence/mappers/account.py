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
    def to_orm(account: Account) -> AccountORM:
        return AccountORM(
            id=account.id,
            owner_id=account.owner_id,
            account_number=account.account_number,
            balance=account.balance.amount,
            currency=account.currency.value,
            status=account.status.value,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )
