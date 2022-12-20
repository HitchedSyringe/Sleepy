"""
Copyright (c) 2018-present HitchedSyringe

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""


# I've only opted to document and expose the "base" minigame
# stuff (e.g. BaseSession, etc). Components for the minigames
# themselves are left undocumented and unexposed.


from __future__ import annotations as _annotations

from typing import TYPE_CHECKING as _TYPE_CHECKING

from .base_session import *
from .cog import *

if _TYPE_CHECKING:
    from sleepy.bot import Sleepy


async def setup(bot: Sleepy) -> None:
    await bot.add_cog(Minigames())
