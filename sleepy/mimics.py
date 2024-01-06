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


# Custom Discord models that either fully or partially
# mimic the ones found in discord.py. These are likely
# only accessible through using custom converters and,
# like any normal Discord model, are not intended for
# manual creation and should be considered read-only.


# fmt: off
__all__ = (
    "PartialAsset",
)
# fmt: on


from typing import Any, Optional, Tuple

from discord.asset import AssetMixin


class PartialAsset(AssetMixin):
    """Represents a partial CDN asset, not necessarily
    from Discord's CDN.

    .. container:: operations

        .. describe:: str(x)

            Returns the URL of the CDN asset.

        .. describe:: len(x)

            Returns the length of the CDN asset's URL.

        .. describe:: x == y

            Checks if the asset is equal to another asset.

        .. describe:: x != y

            Checks if the asset is not equal to another asset.

        .. describe:: hash(x)

            Returns the hash of the asset.
    """

    __slots__: Tuple[str, ...] = ("_state", "_url")

    def __init__(self, state: Optional[Any], *, url: str) -> None:
        self._state: Optional[Any] = state
        self._url: str = url

    def __str__(self) -> str:
        return self._url

    def __len__(self) -> int:
        return len(self._url)

    def __repr__(self) -> str:
        return f"<PartialAsset url={self._url!r}>"

    def __eq__(self, other: AssetMixin) -> bool:
        return isinstance(other, AssetMixin) and self._url == other.url

    def __hash__(self) -> int:
        return hash(self._url)

    @property
    def url(self) -> str:
        """:class:`str`: Returns the underlying URL of the asset."""
        return self._url
