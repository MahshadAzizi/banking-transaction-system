from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.mappers.account import AccountMapper
from src.adapters.outbound.persistence.models import AccountORM
from src.application.ports.outbound.account_repository import IAccountRepository
from src.domain.entities.account import Account
from src.domain.value_objects.identifiers import AccountId


class PostgresAccountRepository(IAccountRepository):
    """
    Postgres implementation of IAccountRepository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: list[Account] = []

    async def get(self, account_id: AccountId) -> Account | None:
        stmt = select(AccountORM).where(AccountORM.id == account_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        account = AccountMapper.to_domain(orm)
        self.seen.append(account)
        return account

    async def get_with_lock(self, account_id: AccountId) -> Account | None:
        stmt = select(AccountORM).where(AccountORM.id == account_id).with_for_update()
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        account = AccountMapper.to_domain(orm)
        self.seen.append(account)
        return account

    async def save(self, account: Account) -> None:
        orm = AccountMapper.to_orm(account)
        await self._session.merge(orm)

    async def exists(self, account_id: AccountId) -> bool:
        stmt = select(AccountORM.id).where(AccountORM.id == account_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
