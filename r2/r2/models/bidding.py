# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2015 reddit
# Inc. All Rights Reserved.
###############################################################################

import datetime

from r2.lib.context import request
from sqlalchemy import (
    and_,
    Boolean,
    BigInteger,
    Column,
    DateTime,
    Date,
    delete,
    distinct,
    Float,
    func as safunc,
    Integer,
    select,
    String,
)
from sqlalchemy.dialects.postgresql.base import PGInet as Inet
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.account import NotFound
from r2.lib.utils import Enum, to_date, tup
from r2.models.orm.base import Base
from r2.models import Frontpage


class CustomerID(Base):
    __tablename__ = "authorize_account_id"

    account_id    = Column(BigInteger, primary_key=True, autoincrement=False)
    authorize_id  = Column(BigInteger)

    def __repr__(self):
        return f"<AuthNetID({self.authorize_id})>"

    @classmethod
    async def set(cls, db: AsyncSession, user, _id):
        account_id = user._id if hasattr(user, '_id') else int(user)
        stmt = select(cls).where(cls.account_id == account_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.authorize_id = _id
        else:
            db.add(cls(account_id=account_id, authorize_id=_id))
        await db.flush()

    @classmethod
    async def get_id(cls, db: AsyncSession, user):
        account_id = user._id if hasattr(user, '_id') else int(user)
        stmt = select(cls).where(cls.account_id == account_id)
        row = (await db.execute(stmt)).scalar_one_or_none()
        return row.authorize_id if row is not None else None


class PayID(Base):
    __tablename__ = "authorize_pay_id"

    account_id    = Column(BigInteger, primary_key=True, autoincrement=False)
    pay_id        = Column(BigInteger, primary_key=True, autoincrement=False)

    def __repr__(self):
        return f"<{self.__class__.__name__}({self.pay_id:d})>"

    @classmethod
    async def get_ids(cls, db: AsyncSession, key):
        account_id = key._id if hasattr(key, '_id') else int(key)
        stmt = select(cls).where(cls.account_id == account_id)
        rows = (await db.execute(stmt)).scalars().all()
        return [int(r.pay_id) for r in rows]

    @classmethod
    async def add(cls, db: AsyncSession, key, pay_id):
        account_id = key._id if hasattr(key, '_id') else int(key)
        stmt = select(cls).where(
            and_(cls.account_id == account_id, cls.pay_id == pay_id)
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing is None:
            db.add(cls(account_id=account_id, pay_id=pay_id))
            await db.flush()

    @classmethod
    async def delete(cls, db: AsyncSession, key, pay_id):
        account_id = key._id if hasattr(key, '_id') else int(key)
        await db.execute(
            delete(cls).where(
                and_(cls.account_id == account_id, cls.pay_id == pay_id)
            )
        )


class Bid(Base):
    __tablename__ = "bids"

    STATUS        = Enum("AUTH", "CHARGE", "REFUND", "VOID")

    transaction   = Column(BigInteger, primary_key=True, autoincrement=False)
    account_id    = Column(BigInteger, index=True, nullable=False)
    pay_id        = Column(BigInteger, index=True, nullable=False)
    thing_id      = Column(BigInteger, index=True, nullable=False)
    ip            = Column(Inet)
    date          = Column(DateTime(timezone=True), default=safunc.now(), nullable=False)
    bid           = Column(Float, nullable=False)
    charge        = Column(Float)
    status        = Column(Integer, nullable=False, default=STATUS.AUTH)
    campaign      = Column(Integer, default=0, primary_key=True)

    @classmethod
    async def _new(cls, db: AsyncSession, trans_id, user, pay_id, thing_id, bid, campaign=0):
        account_id = user._id if hasattr(user, '_id') else int(user)
        obj = cls(
            transaction=trans_id,
            account_id=account_id,
            pay_id=pay_id,
            thing_id=thing_id,
            ip=getattr(request, 'ip', '0.0.0.0'),
            bid=bid,
            campaign=campaign,
        )
        db.add(obj)
        await db.flush()
        return obj

    @classmethod
    async def one(cls, db: AsyncSession, *a, **kw):
        conditions = []
        if a:
            conditions.append(cls.transaction == a[0])
        for k, v in kw.items():
            conditions.append(getattr(cls, k) == v)
        stmt = select(cls).where(and_(*conditions))
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFound(f"Bid with {kw}")
        return row

    @classmethod
    async def lookup(cls, db: AsyncSession, **kw):
        conditions = [getattr(cls, k) == v for k, v in kw.items()]
        stmt = select(cls).where(and_(*conditions))
        return (await db.execute(stmt)).scalars().all()

    @classmethod
    async def query_by_transactions(cls, db: AsyncSession, transaction_ids):
        stmt = select(cls).where(cls.transaction.in_(transaction_ids))
        return (await db.execute(stmt)).scalars().all()

    async def set_status(self, db: AsyncSession, status):
        if self.status != status:
            self.status = status
            await db.flush()

    async def auth(self, db: AsyncSession):
        await self.set_status(db, self.STATUS.AUTH)

    def is_auth(self):
        return (self.status == self.STATUS.AUTH)

    async def void(self, db: AsyncSession):
        await self.set_status(db, self.STATUS.VOID)

    def is_void(self):
        return (self.status == self.STATUS.VOID)

    async def charged(self, db: AsyncSession):
        self.charge = self.bid
        await self.set_status(db, self.STATUS.CHARGE)
        await db.flush()

    def is_charged(self):
        return (self.status == self.STATUS.CHARGE)

    async def refund(self, db: AsyncSession, amount):
        current_charge = self.charge or self.bid
        self.charge = current_charge - amount
        await self.set_status(db, self.STATUS.REFUND)
        await db.flush()

    def is_refund(self):
        return (self.status == self.STATUS.REFUND)

    @property
    def charge_amount(self):
        return self.charge or self.bid


class PromotionWeights(Base):
    __tablename__ = "promotion_weight"

    thing_name = Column(String, primary_key=True, nullable=False, index=True)
    promo_idx  = Column(BigInteger, index=True, autoincrement=False, primary_key=True)
    sr_name    = Column(String, primary_key=True, nullable=True, index=True)
    date       = Column(Date(), primary_key=True, nullable=False, index=True)
    account_id = Column(BigInteger, index=True, autoincrement=False)
    bid        = Column(Float, nullable=False)
    weight     = Column(Float, nullable=False)
    finished   = Column(Boolean)
    # NOTE: bid, weight, finished columns are not used

    @classmethod
    def filter_sr_name(cls, sr_name):
        # LEGACY: use empty string to indicate Frontpage
        return '' if sr_name == Frontpage.name else sr_name

    @classmethod
    async def reschedule(cls, db: AsyncSession, link, campaign):
        await cls.delete(db, link, campaign)
        await cls.add(db, link, campaign)

    @classmethod
    async def add(cls, db: AsyncSession, link, campaign):
        start_date = to_date(campaign.start_date)
        end_date = to_date(campaign.end_date)
        ndays = (end_date - start_date).days
        dates = [start_date + datetime.timedelta(days=i) for i in range(ndays)]

        sr_names = campaign.target.subreddit_names
        sr_names = {cls.filter_sr_name(sr_name) for sr_name in sr_names}

        for sr_name in sr_names:
            for date in dates:
                obj = cls(
                    thing_name=link._fullname,
                    promo_idx=campaign._id,
                    sr_name=sr_name,
                    date=date,
                    account_id=link.author_id,
                    bid=0.,
                    weight=0.,
                    finished=False,
                )
                db.add(obj)
        await db.flush()

    @classmethod
    async def delete(cls, db: AsyncSession, link, campaign):
        await db.execute(
            delete(cls).where(
                and_(
                    cls.thing_name == link._fullname,
                    cls.promo_idx == campaign._id,
                )
            )
        )

    @classmethod
    def _build_filter(cls, stmt, start, end=None, link=None,
                      author_id=None, sr_names=None):
        start = to_date(start)

        if end:
            end = to_date(end)
            stmt = stmt.where(and_(cls.date >= start, cls.date < end))
        else:
            stmt = stmt.where(cls.date == start)

        if link:
            stmt = stmt.where(cls.thing_name == link._fullname)

        if author_id:
            stmt = stmt.where(cls.account_id == author_id)

        if sr_names:
            sr_names = [cls.filter_sr_name(sr_name) for sr_name in sr_names]
            stmt = stmt.where(cls.sr_name.in_(sr_names))

        return stmt

    @classmethod
    async def get_campaign_ids(cls, db: AsyncSession, start, end=None, link=None,
                               author_id=None, sr_names=None):
        stmt = select(distinct(cls.promo_idx))
        stmt = cls._build_filter(stmt, start, end, link, author_id, sr_names)
        rows = (await db.execute(stmt)).all()
        return {r[0] for r in rows}

    @classmethod
    async def get_link_names(cls, db: AsyncSession, start, end=None, link=None,
                             author_id=None, sr_names=None):
        stmt = select(distinct(cls.thing_name))
        stmt = cls._build_filter(stmt, start, end, link, author_id, sr_names)
        rows = (await db.execute(stmt)).all()
        return {r[0] for r in rows}
