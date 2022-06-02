"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations as _annotations

from typing import TYPE_CHECKING as _TYPE_CHECKING

from . import backend as backend
from .cascades import *
from .frontend import *
from .templates import *

if _TYPE_CHECKING:
    from discord.ext.commands import Bot


async def setup(bot: Bot) -> None:
    await bot.add_cog(Weeb())
