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
# manual creation should be considered read-only.


__all__ = (
    "PartialAsset",
)


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

    __slots__ = ("_state", "_url")

    def __init__(self, state, *, url):
        self._state = state
        self._url = url

    def __str__(self):
        return self._url

    def __len__(self):
        return len(self._url)

    def __repr__(self):
        return f"<PartialAsset url={self._url!r}>"

    def __eq__(self, other):
        return isinstance(other, AssetMixin) and self._url == other.url

    def __hash__(self):
        return hash(self._url)

    @property
    def url(self):
        """:class:`str`: Returns the underlying URL of the asset."""
        return self._url
