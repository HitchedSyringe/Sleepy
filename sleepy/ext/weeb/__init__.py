"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


# Will also provide this as a semi-library, but
# I'm still not going to document this hot mess
# I've made for myself (and potentially others).


from . import backend
from .cascades import CASCADES
from .frontend import Weeb
from .templates import TEMPLATES


def setup(bot):
    bot.add_cog(Weeb())
