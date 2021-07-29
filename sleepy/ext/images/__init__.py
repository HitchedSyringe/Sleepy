"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


# I split this up into a semi-library to make
# this easier to maintain and allow others to
# interact with this extension from elsewhere
# without having to mill about with the actual
# command interface. However, I won't bother
# documenting any of this since this isn't
# considered part of the public bot API. I bid
# good luck to anyone willing to extend their
# resources and time toward reverse engineering
# this hot mess I have created for myself and
# whoever shall maintain this in the far future.


from . import backend, helpers
from .fonts import FONTS
from .frontend import Images, RGBColourConverter
from .templates import TEMPLATES


def setup(bot):
    bot.add_cog(Images())
