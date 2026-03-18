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

# Legacy Python 2 relative imports removed. Individual model modules still
# exist in this package but are imported directly where needed. The new
# SQLAlchemy ORM models live in r2.models.orm.

# Re-export the most commonly imported names so that
#   from r2.models import Account, Link, Subreddit, All, ...
# continues to work as it did in the legacy Pylons stack.

from r2.models.account import (  # noqa: F401
    Account,
    FakeAccount,
    DeletedUser,
    NotFound,
)

from r2.models.subreddit import (  # noqa: F401
    Subreddit,
    FakeSubreddit,
    DefaultSR,
    Frontpage,
    All,
    AllSR,
    AllFiltered,
    AllMinus,
    Friends,
    Mod,
    ModFiltered,
    ModMinus,
    Random,
    RandomNSFW,
    RandomSubscription,
    DomainSR,
    MultiReddit,
    LabeledMulti,
)

from r2.models.link import Link, Comment, Message  # noqa: F401

from r2.models.token import (  # noqa: F401
    OAuth2AccessToken,
    OAuth2Client,
    OAuth2RefreshToken,
    OAuth2Scope,
    PasswordResetToken,
    EmailVerificationToken,
)

from r2.models.vote import Vote  # noqa: F401

from r2.models.award import Award, Trophy  # noqa: F401

from r2.models.flair import (  # noqa: F401
    Flair,
    FlairTemplate,
    FlairTemplateBySubredditIndex,
    NotFound as FlairNotFound,
    USER_FLAIR,
    LINK_FLAIR,
    MAX_FLAIR_TEMPLATES,
)

# Auth helpers that controllers expect on r2.models
from r2.lib.auth import valid_feed, valid_admin_cookie, valid_otp_cookie  # noqa: F401
