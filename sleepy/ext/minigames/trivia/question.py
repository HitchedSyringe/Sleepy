"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


# fmt: off
__all__ = (
    "TriviaQuestion",
)
# fmt: on


from typing import List, NamedTuple, Optional


class TriviaQuestion(NamedTuple):
    category: str
    text: str
    answers: List[str]
    image_url: Optional[str] = None
    author: Optional[str] = None
