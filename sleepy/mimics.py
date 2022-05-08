"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


# Custom Discord models that either fully or partially
# mimic the ones found in discord.py. These are likely
# only accessible through using custom converters and,
# like any normal Discord model, are not intended for
# manual creation and should be considered read-only.


__all__ = (
    "PartialAsset",
)


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
