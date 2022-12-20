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
