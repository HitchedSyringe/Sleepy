"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


# I've only opted to document and expose the "base" minigame
# stuff (e.g. BaseSession, etc). Components for the minigames
# themselves are left undocumented and unexposed.


from __future__ import annotations as _annotations

from typing import TYPE_CHECKING as _TYPE_CHECKING

from .base_session import *
from .cog import *

if _TYPE_CHECKING:
    from discord.ext.commands import Bot


async def setup(bot: Bot) -> None:
    await bot.add_cog(Minigames())
