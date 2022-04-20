"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


# I'm not sure what the use case is for interfacing
# with this extension, but I'll grudgingly allow
# it. Will give a fair warning though, none of this
# is documented (because it's not part of the public
# bot API) and this API is probably very messy and
# finnicky to work with.


from . import backend
from .categories import CATEGORIES
from .frontend import (
    NoActiveSession,
    TriviaMinigame,
    has_active_session,
)


async def setup(bot):
    await bot.add_cog(TriviaMinigame())
