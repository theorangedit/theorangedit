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

from datetime import datetime

from r2.lib.context import c
from r2.lib.app_globals import g
from r2.lib.i18n import _, N_
from r2.lib.unicode import _force_unicode
from r2.lib.utils import Enum
from r2.models.orm.promo import PromoCampaign as _PromoCampaignORM
from r2.models.subreddit import Subreddit, Frontpage


PROMOTE_STATUS = Enum("unpaid", "unseen", "accepted", "rejected",
                      "pending", "promoted", "finished", "edited_live")

PROMOTE_COST_BASIS = Enum('fixed_cpm', 'cpm', 'cpc',)


class PriorityLevel(object):
    name = ''
    _text = N_('')
    _description = N_('')
    default = False
    inventory_override = False

    def __repr__(self):
        return f"<PriorityLevel {self.name}>"

    @property
    def text(self):
        return _(self._text) if self._text else ''

    @property
    def description(self):
        return _(self._description) if self._description else ''


class HighPriority(PriorityLevel):
    name = 'high'
    _text = N_('highest')


class MediumPriority(PriorityLevel):
    name = 'standard'
    _text = N_('standard')
    default = True


class RemnantPriority(PriorityLevel):
    name = 'remnant'
    _text = N_('remnant')
    _description = N_('lower priority, impressions are not guaranteed')
    inventory_override = True


class HousePriority(PriorityLevel):
    name = 'house'
    _text = N_('house')
    _description = N_('non-CPM, displays in all unsold impressions')
    inventory_override = True


class AuctionPriority(PriorityLevel):
    name = 'auction'
    _text = N_('auction')
    _description = N_('auction priority; all self-serve are auction priority')
    inventory_override = True


HIGH, MEDIUM, REMNANT, HOUSE, AUCTION = (HighPriority(), MediumPriority(),
                                         RemnantPriority(), HousePriority(),
                                         AuctionPriority(),)
PROMOTE_PRIORITIES = {p.name: p for p in (HIGH, MEDIUM, REMNANT,
                                           HOUSE, AUCTION,)}


def PROMOTE_DEFAULT_PRIORITY(context=None):
    from r2.config import feature
    if (context and (not feature.is_enabled('ads_auction') or
                     context.user_is_sponsor)):
        return MEDIUM
    else:
        return AUCTION


class Location(object):
    DELIMITER = '-'
    def __init__(self, country, region=None, metro=None):
        self.country = country or None
        self.region = region or None
        self.metro = metro or None

    def __repr__(self):
        return f'<{self.__class__.__name__} ({self.country}/{self.region}/{self.metro})>'

    def to_code(self):
        fields = [self.country, self.region, self.metro]
        return self.DELIMITER.join(i or '' for i in fields)

    @classmethod
    def from_code(cls, code):
        country, region, metro = [i or None for i in code.split(cls.DELIMITER)]
        return cls(country, region, metro)

    def contains(self, other):
        if not self.country:
            return True
        elif not other or not other.country:
            return False
        else:
            if self.country != other.country:
                return False
            else:
                if not self.metro:
                    return True
                elif not other.metro:
                    return False
                else:
                    return self.metro == other.metro

    def __eq__(self, other):
        if not isinstance(other, Location):
            return False
        return (self.country == other.country and
                self.region == other.region and
                self.metro == other.metro)

    def __ne__(self, other):
        return not self.__eq__(other)


def calc_impressions(total_budget_pennies, cpm_pennies):
    return int(total_budget_pennies / cpm_pennies * 1000)


NO_TRANSACTION = 0

_SR_NAMES_DELIM = '|'


class Collection(object):
    def __init__(self, name, sr_names, over_18=False, description=None,
            is_spotlight=False):
        self.name = name
        self.over_18 = over_18
        self.sr_names = sr_names
        self.description = description
        self.is_spotlight = is_spotlight

    @classmethod
    async def by_name(cls, name):
        return await CollectionStorage.get_collection(name)

    @classmethod
    async def get_all(cls):
        """
        Return collections in this order:
        1. SFW/NSFW
        2. Spotlighted
        3. Alphabetical
        """
        all_collections = await CollectionStorage.get_all()
        return sorted(all_collections, key=lambda col:
            (col.over_18, -col.is_spotlight, col.name.lower()))

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"


def _orm_to_collection(row) -> Collection:
    sr_names = row.sr_names.split(_SR_NAMES_DELIM) if row.sr_names else []
    return Collection(row.name, sr_names, over_18=row.over_18,
                      description=row.description, is_spotlight=row.is_spotlight)


class CollectionStorage:
    @classmethod
    async def set(cls, name, description, srs, over_18=False, is_spotlight=False):
        import r2.services.promo as _svc
        sr_names = [sr.name for sr in srs]
        row = await _svc.upsert_collection(
            c.db, name, description, sr_names, over_18, is_spotlight)
        return _orm_to_collection(row)

    @classmethod
    async def set_over_18(cls, name, over_18):
        import r2.services.promo as _svc
        await _svc.update_collection_field(c.db, name, over_18=over_18)

    @classmethod
    async def set_is_spotlight(cls, name, is_spotlight):
        import r2.services.promo as _svc
        await _svc.update_collection_field(c.db, name, is_spotlight=is_spotlight)

    @classmethod
    async def get_collection(cls, name):
        if not name:
            return None
        import r2.services.promo as _svc
        row = await _svc.get_collection(c.db, name)
        return _orm_to_collection(row) if row else None

    @classmethod
    async def get_all(cls):
        import r2.services.promo as _svc
        rows = await _svc.get_all_collections(c.db)
        return [_orm_to_collection(row) for row in rows]

    @classmethod
    async def delete(cls, name):
        import r2.services.promo as _svc
        await _svc.delete_collection(c.db, name)


class Target(object):
    """Wrapper around either a Collection or a Subreddit name"""
    def __init__(self, target):
        if isinstance(target, Collection):
            self.collection = target
            self.is_collection = True
        elif isinstance(target, str):
            self.subreddit_name = target
            self.is_collection = False
        else:
            raise ValueError("target must be a Collection or Subreddit name")

        self._subreddits = None

    @property
    def over_18(self):
        if self.is_collection:
            return self.collection.over_18
        else:
            subreddits = self.subreddits_slow
            return subreddits and subreddits[0].over_18

    @property
    def subreddit_names(self):
        if self.is_collection:
            return self.collection.sr_names
        else:
            return [self.subreddit_name]

    @property
    def subreddits_slow(self):
        if self._subreddits is not None:
            return self._subreddits
        sr_names = self.subreddit_names
        srs = Subreddit._by_name(sr_names).values()
        self._subreddits = srs
        return srs

    def __eq__(self, other):
        if self.is_collection != other.is_collection:
            return False
        return set(self.subreddit_names) == set(other.subreddit_names)

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def pretty_name(self):
        if self.is_collection:
            return _("collection: %(name)s") % {'name': self.collection.name}
        elif self.subreddit_name == Frontpage.name:
            return _("frontpage")
        else:
            return f"/r/{self.subreddit_name}"

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.pretty_name}>"


# ---------------------------------------------------------------------------
# PromoCampaign — ORM-backed, augmented with business logic properties
# ---------------------------------------------------------------------------

SR_NAMES_DELIM = '|'   # kept as class-level constant for external callers


def _pc_id(self):
    """Alias _id → id for legacy callers."""
    return self.id

def _pc_fullname(self):
    return f"campaign_{self.id}"

def _pc_commit(self):
    return c.db.flush()

def _pc_ndays(self):
    return (self.end_date - self.start_date).days

def _pc_impressions(self):
    if self.cost_basis == PROMOTE_COST_BASIS.fixed_cpm:
        return calc_impressions(self.total_budget_pennies, self.bid_pennies)
    return 0

def _pc_is_auction(self):
    return self.cost_basis is not PROMOTE_COST_BASIS.fixed_cpm

def _pc_priority_get(self):
    return PROMOTE_PRIORITIES[self.priority_name]

def _pc_priority_set(self, priority):
    if priority not in PROMOTE_PRIORITIES.values():
        raise ValueError(f"{priority.name} is not a valid priority")
    self.priority_name = priority.name

def _pc_location_get(self):
    if self.location_code is not None:
        return Location.from_code(self.location_code)
    return None

def _pc_location_set(self, location):
    self.location_code = location.to_code() if location else None

def _pc_target_get(self):
    if hasattr(self, '_target'):
        return self._target
    sr_names = self.target_sr_names.split(SR_NAMES_DELIM) if self.target_sr_names else []
    if self.target_name == 'subreddit':
        target = Target(sr_names[0] if sr_names else '')
    else:
        collection = Collection(self.target_name, sr_names)
        target = Target(collection)
    self._target = target
    return target

def _pc_target_set(self, target):
    sr_names = target.subreddit_names
    self.target_sr_names = SR_NAMES_DELIM.join(sr_names)
    self.target_name = (target.collection.name if target.is_collection
                        else 'subreddit')
    self._target = target

_MOBILE_DELIM = ','

def _pc_mobile_getter(self, attr):
    val = getattr(self, attr)
    return val.split(_MOBILE_DELIM) if val else None

def _pc_mobile_setter(self, attr, names):
    setattr(self, attr, _MOBILE_DELIM.join(names) if names else None)

def _pc_mobile_os_get(self):    return _pc_mobile_getter(self, 'mobile_os_names')
def _pc_mobile_os_set(self, v): _pc_mobile_setter(self, 'mobile_os_names', v)

def _pc_ios_devices_get(self):    return _pc_mobile_getter(self, 'ios_device_names')
def _pc_ios_devices_set(self, v): _pc_mobile_setter(self, 'ios_device_names', v)

def _pc_android_devices_get(self):    return _pc_mobile_getter(self, 'android_device_names')
def _pc_android_devices_set(self, v): _pc_mobile_setter(self, 'android_device_names', v)

def _pc_ios_version_range_get(self):    return _pc_mobile_getter(self, 'ios_version_names')
def _pc_ios_version_range_set(self, v): _pc_mobile_setter(self, 'ios_version_names', v)

def _pc_android_version_range_get(self):    return _pc_mobile_getter(self, 'android_version_names')
def _pc_android_version_range_set(self, v): _pc_mobile_setter(self, 'android_version_names', v)

def _pc_location_str(self):
    if not self.location:
        return ''
    loc = self.location
    if loc.region:
        country = loc.country
        region = loc.region
        if loc.metro:
            metro_str = (g.locations[country]['regions'][region]
                         ['metros'][loc.metro]['name'])
            return '/'.join([country, region, metro_str])
        else:
            region_name = g.locations[country]['regions'][region]['name']
            return f'{region_name}, {country}'
    else:
        return g.locations[loc.country]['name']

def _pc_is_paid(self):
    return self.trans_id != NO_TRANSACTION or self.priority == HOUSE

def _pc_is_freebie(self):
    return self.trans_id < 0

def _pc_is_live_now(self):
    today = datetime.now(g.tz).date()
    return self.start_date < today < self.end_date

def _pc_is_house(self):
    return self.priority == HOUSE

def _pc_total_budget_dollars(self):
    return self.total_budget_pennies / 100.

def _pc_bid_dollars(self):
    return self.bid_pennies / 100.

@classmethod
def _pc_location_code_from_location(cls, location):
    return location.to_code() if location else None

@classmethod
def _pc_unpack_target(cls, target):
    sr_names = target.subreddit_names
    target_sr_names = SR_NAMES_DELIM.join(sr_names)
    target_name = (target.collection.name if target.is_collection
                   else 'subreddit')
    return target_sr_names, target_name

@classmethod
async def _pc_create(cls, link, target, start_date, end_date,
                     frequency_cap, priority, location,
                     platform, mobile_os, ios_devices, ios_version_range,
                     android_devices, android_version_range,
                     total_budget_pennies, cost_basis, bid_pennies):
    import r2.services.promo as _svc
    target_sr_names, target_name = cls.unpack_target(target)
    return await _svc.create_campaign(
        c.db,
        link_id=link._id,
        owner_id=link.author_id,
        start_date=start_date,
        end_date=end_date,
        total_budget_pennies=total_budget_pennies,
        cost_basis=cost_basis,
        bid_pennies=bid_pennies,
        frequency_cap=frequency_cap,
        priority_name=priority.name,
        location_code=location.to_code() if location else None,
        target_sr_names=target_sr_names,
        target_name=target_name,
        platform=platform,
        mobile_os_names=_MOBILE_DELIM.join(mobile_os) if mobile_os else None,
        ios_device_names=_MOBILE_DELIM.join(ios_devices) if ios_devices else None,
        ios_version_names=_MOBILE_DELIM.join(ios_version_range) if ios_version_range else None,
        android_device_names=_MOBILE_DELIM.join(android_devices) if android_devices else None,
        android_version_names=_MOBILE_DELIM.join(android_version_range) if android_version_range else None,
    )

@classmethod
async def _pc_by_link(cls, link_id):
    import r2.services.promo as _svc
    return await _svc.get_campaigns_by_link(c.db, link_id)

@classmethod
async def _pc_by_user(cls, account_id):
    import r2.services.promo as _svc
    return await _svc.get_campaigns_by_owner(c.db, account_id)

async def _pc_delete(self):
    import r2.services.promo as _svc
    await _svc.delete_campaign(c.db, self.id)
    self.is_deleted = True

# Patch onto ORM class
_PromoCampaignORM._id = property(_pc_id)
_PromoCampaignORM._fullname = property(_pc_fullname)
_PromoCampaignORM._commit = _pc_commit
_PromoCampaignORM.ndays = property(_pc_ndays)
_PromoCampaignORM.impressions = property(_pc_impressions)
_PromoCampaignORM.is_auction = property(_pc_is_auction)
_PromoCampaignORM.priority = property(_pc_priority_get, _pc_priority_set)
_PromoCampaignORM.location = property(_pc_location_get, _pc_location_set)
_PromoCampaignORM.target = property(_pc_target_get, _pc_target_set)
_PromoCampaignORM.mobile_os = property(_pc_mobile_os_get, _pc_mobile_os_set)
_PromoCampaignORM.ios_devices = property(_pc_ios_devices_get, _pc_ios_devices_set)
_PromoCampaignORM.android_devices = property(_pc_android_devices_get, _pc_android_devices_set)
_PromoCampaignORM.ios_version_range = property(_pc_ios_version_range_get, _pc_ios_version_range_set)
_PromoCampaignORM.android_version_range = property(_pc_android_version_range_get, _pc_android_version_range_set)
_PromoCampaignORM.location_str = property(_pc_location_str)
_PromoCampaignORM.is_paid = property(_pc_is_paid)
_PromoCampaignORM.is_freebie = _pc_is_freebie
_PromoCampaignORM.is_live_now = _pc_is_live_now
_PromoCampaignORM.is_house = property(_pc_is_house)
_PromoCampaignORM.total_budget_dollars = property(_pc_total_budget_dollars)
_PromoCampaignORM.bid_dollars = property(_pc_bid_dollars)
_PromoCampaignORM.location_code_from_location = _pc_location_code_from_location
_PromoCampaignORM.unpack_target = _pc_unpack_target
_PromoCampaignORM.create = _pc_create
_PromoCampaignORM._by_link = _pc_by_link
_PromoCampaignORM._by_user = _pc_by_user
_PromoCampaignORM.delete = _pc_delete

PromoCampaign = _PromoCampaignORM


# ---------------------------------------------------------------------------
# PromotionLog — async, PostgreSQL-backed
# ---------------------------------------------------------------------------

class PromotionLog:
    @classmethod
    async def add(cls, link, text):
        import r2.services.promo as _svc
        name = c.user.name if c.user_is_loggedin else "<AUTOMATED>"
        now = datetime.now(g.tz).strftime("%Y-%m-%d %H:%M:%S")
        formatted = _force_unicode(f"[{name}: {now}] {text}")
        await _svc.add_log_entry(c.db, link._fullname, formatted)
        return formatted

    @classmethod
    async def get(cls, link):
        import r2.services.promo as _svc
        entries = await _svc.get_log_entries(c.db, link._fullname)
        return [entry.text for entry in entries]


# ---------------------------------------------------------------------------
# PromotionPrices — async, PostgreSQL-backed
# ---------------------------------------------------------------------------

class PromotionPrices:
    """
    Check all potentially specially priced conditions:
    * metro level targeting
    * country level targeting (not if metro targeting used)
    * collection targeting
    * frontpage targeting
    * subreddit targeting

    The price is the maximum price for all matching conditions.
    """

    COLLECTION_DEFAULT = property(lambda self: g.cpm_selfserve_collection.pennies)
    SUBREDDIT_DEFAULT = property(lambda self: g.cpm_selfserve.pennies)
    COUNTRY_DEFAULT = property(lambda self: g.cpm_selfserve_geotarget_country.pennies)
    METRO_DEFAULT = property(lambda self: g.cpm_selfserve_geotarget_metro.pennies)

    @classmethod
    def _rowkey_and_column_from_target(cls, target):
        if isinstance(target, Target):
            if target.is_collection:
                return "COLLECTION", target.collection.name
            else:
                return "SUBREDDIT", target.subreddit_name
        raise ValueError("target must be Target")

    @classmethod
    def _rowkey_and_column_from_location(cls, location):
        if not isinstance(location, Location):
            raise ValueError("location must be Location")
        if location.metro:
            return "METRO", ''.join(map(str, (location.country, location.metro)))
        else:
            return "COUNTRY", location.country

    @classmethod
    async def set_target_price(cls, target, cpm):
        import r2.services.promo as _svc
        price_type, name = cls._rowkey_and_column_from_target(target)
        await _svc.set_price(c.db, price_type, name, cpm)

    @classmethod
    async def set_location_price(cls, location, cpm):
        import r2.services.promo as _svc
        price_type, name = cls._rowkey_and_column_from_location(location)
        await _svc.set_price(c.db, price_type, name, cpm)

    @classmethod
    async def lookup_target_price(cls, target, default):
        import r2.services.promo as _svc
        price_type, name = cls._rowkey_and_column_from_target(target)
        price = await _svc.get_price(c.db, price_type, name)
        return price if price is not None else default

    @classmethod
    async def lookup_location_price(cls, location, default):
        import r2.services.promo as _svc
        price_type, name = cls._rowkey_and_column_from_location(location)
        price = await _svc.get_price(c.db, price_type, name)
        return price if price is not None else default

    @classmethod
    async def get_price(cls, user, target, location):
        if user.selfserve_cpm_override_pennies:
            return user.selfserve_cpm_override_pennies

        prices = []

        if location and location.metro:
            prices.append(await cls.lookup_location_price(
                location, g.cpm_selfserve_geotarget_metro.pennies))
        elif location:
            prices.append(await cls.lookup_location_price(
                location, g.cpm_selfserve_geotarget_country.pennies))

        if not target.is_collection and target.subreddit_name == Frontpage.name:
            prices.append(g.cpm_selfserve_collection.pennies)
        elif target.is_collection:
            prices.append(await cls.lookup_target_price(
                target, g.cpm_selfserve_collection.pennies))
        else:
            prices.append(await cls.lookup_target_price(
                target, g.cpm_selfserve.pennies))

        return max(prices)

    @classmethod
    async def get_price_dict(cls, user):
        import r2.services.promo as _svc

        if user.selfserve_cpm_override_pennies:
            override = user.selfserve_cpm_override_pennies
            return {
                "COLLECTION": {}, "SUBREDDIT": {}, "COUNTRY": {}, "METRO": {},
                "COLLECTION_DEFAULT": override,
                "SUBREDDIT_DEFAULT": override,
                "COUNTRY_DEFAULT": override,
                "METRO_DEFAULT": override,
            }

        collections = await _svc.get_prices_by_type(c.db, "COLLECTION")
        subreddits = await _svc.get_prices_by_type(c.db, "SUBREDDIT")
        countries = await _svc.get_prices_by_type(c.db, "COUNTRY")
        metros = await _svc.get_prices_by_type(c.db, "METRO")

        return {
            "COLLECTION": collections,
            "SUBREDDIT": subreddits,
            "COUNTRY": countries,
            "METRO": metros,
            "COLLECTION_DEFAULT": g.cpm_selfserve_collection.pennies,
            "SUBREDDIT_DEFAULT": g.cpm_selfserve.pennies,
            "COUNTRY_DEFAULT": g.cpm_selfserve_geotarget_country.pennies,
            "METRO_DEFAULT": g.cpm_selfserve_geotarget_metro.pennies,
        }
