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


from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Literal, Optional, Tuple, Union
from urllib.parse import quote

import numpy as np
from discord import Colour, Embed, File
from discord.ext import commands
from jishaku.functools import executor_function
from matplotlib import pyplot as plt, use as matplotlib_use
from matplotlib.dates import AutoDateLocator, DateFormatter, datestr2num
from matplotlib.figure import Figure
from typing_extensions import Annotated

from sleepy.converters import _positional_bool_flag
from sleepy.http import HTTPRequestFailed
from sleepy.utils import human_number, measure_performance

if TYPE_CHECKING:
    from typing import TypedDict

    from matplotlib.axes import Axes

    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext

    class CovidHistoryData(TypedDict):
        country: str
        cases: Dict[str, int]
        deaths: Dict[str, int]
        recovered: Dict[str, int]
        vaccines: Optional[Dict[str, int]]


# We don't need any GUI elements since all plots are static.
matplotlib_use("agg")


# The COVID-19 historical plot's length & width in inches.
FIGSIZE_INCHES: Tuple[int, int] = (8, 6)


# disease.sh API takes comma-separated arguments to denote
# requesting data for multiple entities. The commands below
# are not designed to handle this functionality, therefore,
# this pseudo-converter scrubs end-user input to prevent
# the API from returning data for multiple sources.
def clean_input(value: str) -> str:
    if "," in value:
        raise commands.BadArgument(
            "Due to the way my data source processes arguments, "
            "commas are not allowed in your input."
        )

    return quote(value)


class Covid(
    commands.Cog,
    name="COVID-19",
    command_attrs={
        "cooldown": commands.CooldownMapping.from_cooldown(
            1, 5, commands.BucketType.member
        ),
    },
):
    """Commands related to the COVID-19 pandemic."""

    ICON: str = "\N{MICROBE}"

    # Defined up here in case I ever need to change
    # the API base for whatever reason.
    BASE: str = "https://disease.sh/v3/covid-19"

    async def cog_command_error(self, ctx: SleepyContext, error: Exception) -> None:
        if isinstance(error, (commands.BadArgument, commands.MaxConcurrencyReached)):
            await ctx.send(error)  # type: ignore
            ctx._already_handled_error = True

    @executor_function
    @measure_performance
    def plot_historical_data(
        self,
        country: str,
        cases: Dict[str, int],
        deaths: Dict[str, int],
        recovered: Dict[str, int],
        vaccines: Optional[Dict[str, int]] = None,
        *,
        logarithmic: bool,
    ) -> io.BytesIO:
        # For reference, dates are in MM/DD/YYYY format, where MM and DD
        # do not always have a leading zero, e.g. dates can be 1/1/2023.
        timeline = datestr2num(np.fromiter(cases.keys(), dtype="U10"))

        c_counts = np.fromiter(cases.values(), dtype=int)
        d_counts = np.fromiter(deaths.values(), dtype=int)
        r_counts = np.fromiter(recovered.values(), dtype=int)
        # Equation for estimating the number of active cases:
        # active = cases - deaths - recoveries
        a_counts = c_counts - d_counts - r_counts

        dark_embed = str(Colour.dark_embed())

        # Have to use object-oriented interface since pyplot isn't threadsafe.
        fig = Figure(figsize=FIGSIZE_INCHES, facecolor=dark_embed)

        sp_kw = {"facecolor": dark_embed, "axisbelow": True}
        # Calculating margins is faster than saving with bbox_inches="tight".
        # For reference, the values below are in inches.
        # fmt: off
        gs_kw = {
            "left":   0.575 / FIGSIZE_INCHES[0],
            "right":  1 - 0.175 / FIGSIZE_INCHES[0],
            "top":    1 - 0.55 / FIGSIZE_INCHES[1],
            "bottom": 1.285 / FIGSIZE_INCHES[1],
        }
        # fmt: on

        if vaccines is None:
            axes: Axes = fig.subplots(subplot_kw=sp_kw, gridspec_kw=gs_kw)  # type: ignore
            axes.set_title("COVID-19 Cases & Outcomes", color="lightgrey", loc="left")
            axes.spines[["top", "bottom"]].set_color("white")

            # Hardcoded since there's no way to determine these dynamically.
            # These are ultimately arbitrary values based on looks alone.
            # fmt: off
            suptitle_y   = 1.117
            footnotes_y  = -0.225
            copyrights_y = -0.29
            legend_y     = -0.15
            # fmt: on
        else:
            gs_kw["hspace"] = 0
            axes, v_axes = fig.subplots(
                2, sharex=True, subplot_kw=sp_kw, gridspec_kw=gs_kw
            )

            axes.set_title(
                "COVID-19 Cases & Outcomes, and Vaccinations",
                color="lightgrey",
                loc="left",
            )
            axes.spines.top.set_color("white")

            self._apply_axes_style(v_axes, logarithmic=logarithmic)
            v_axes.spines.top.set_color("grey")
            v_axes.spines.bottom.set_color("white")

            v_axes.plot(
                datestr2num(np.fromiter(vaccines.keys(), dtype="U10")),
                np.fromiter(vaccines.values(), dtype=np.int64),
                "--",
                color="#FFDC82",
                label="Vaccinations",
                dashes=(6, 2),
            )

            # fmt: off
            suptitle_y   = 1.235
            footnotes_y  = -1.45
            copyrights_y = -1.58
            legend_y     = -1.3
            # fmt: on

        self._apply_axes_style(axes, logarithmic=logarithmic)
        axes.spines.top.set_linewidth(1.5)

        axes.plot(timeline, a_counts, ":", color="aqua", label="Active*")
        axes.plot(timeline, r_counts, "-.", color="#65B558", label="Recoveries**")
        axes.plot(timeline, d_counts, "--", color="#ED7734", label="Deaths")
        axes.plot(timeline, c_counts, "-", color="#1F94E2", label="Cases")

        axes.fill_between(timeline, c_counts, r_counts, color="#0D87D8", alpha=0.5)  # type: ignore
        axes.fill_between(timeline, r_counts, d_counts, color="#52A046", alpha=0.5)  # type: ignore
        axes.fill_between(timeline, d_counts, color="#FF5E00", alpha=0.5)

        fig.suptitle(
            country,
            x=0,
            y=suptitle_y,
            transform=axes.transAxes,
            ha="left",
            color="white",
            fontsize="xx-large",
            fontweight="bold",
        )

        footnotes = (
            "*Estimated from data on cases, deaths, and recoveries."
            "\n**As of 21st July, 2021, maintenance of recovery data has ceased."
            "\n***As of 10th March, 2023, maintenance of all historical data has ceased."
        )
        fig.text(
            0,
            footnotes_y,
            footnotes,
            transform=axes.transAxes,
            fontsize=8,
            color="lightgrey",
        )

        copyrights = (
            "\N{COPYRIGHT SIGN} Sleepy 2020-present"
            "\nSource(s): John Hopkins University"
            " and the Regulatory Affairs Professional Society (RAPS)."
        )
        fig.text(
            0.5,
            copyrights_y,
            copyrights,
            transform=axes.transAxes,
            fontsize=8,
            color="darkgrey",
            ha="center",
        )

        fig.legend(
            labelcolor="white",
            facecolor="0.125",
            edgecolor="none",
            ncol=5,
            loc="lower left",
            bbox_transform=axes.transAxes,
            bbox_to_anchor=(-0.015, legend_y, 1.03, 0),
            mode="expand",
        )

        buffer = io.BytesIO()

        fig.savefig(buffer, format="png")
        plt.close(fig)

        buffer.seek(0)

        return buffer

    @staticmethod
    def _apply_axes_style(axes: Axes, *, logarithmic: bool) -> None:
        axes.spines[["right", "left"]].set_visible(False)

        axes.yaxis.grid(color="dimgrey", alpha=0.25)

        axes.tick_params(colors="white", labelsize="medium")

        axes.xaxis.set_major_locator(AutoDateLocator(minticks=3, maxticks=8))
        axes.xaxis.set_major_formatter(DateFormatter("%b %Y"))

        if logarithmic:
            # We use symlog here so zeroes are plotted, since log(0) = -inf,
            # which matplotlib doesn't plot. This is more straight forward
            # than having to keep track of an arbitrary offset.
            axes.set_yscale("symlog", linthresh=1)  # type: ignore

        axes.yaxis.set_tick_params(which="both", left=False)
        axes.yaxis.set_major_formatter(lambda x, _: human_number(x))

    async def _get_world_history_data(
        self, ctx: SleepyContext, *, lastdays: Union[Literal["all"], int] = "all"
    ) -> CovidHistoryData:
        hist_url = f"{self.BASE}/historical/all"
        vaxx_url = f"{self.BASE}/vaccine/coverage"

        data = await ctx.get(hist_url, cache__=True, lastdays=lastdays)
        data["vaccines"] = await ctx.get(vaxx_url, cache__=True, lastdays=lastdays)
        data["country"] = "World"

        return data

    async def _get_country_history_data(
        self,
        ctx: SleepyContext,
        country: str,
        *,
        lastdays: Union[Literal["all"], int] = "all",
    ) -> Optional[CovidHistoryData]:
        hist_url = f"{self.BASE}/historical/{country}"

        try:
            hist = await ctx.get(hist_url, cache__=True, lastdays=lastdays)
        except HTTPRequestFailed:
            # Either worldometers has data on a country that jhucsse
            # historical doesn't, or the "country" is actually considered
            # a province on jhucsse's end. Either way, there's nothing we
            # can really do without overcomplicating things.
            return None

        data = hist["timeline"]
        # This needs to be done because some country spellings that are
        # valid when fetching general history aren't valid when fetching
        # vaccine history (e.g. "United States" is invalid whereas "USA"
        # is valid in this case).
        data["country"] = valid_country = hist["country"]
        vaxx_url = f"{self.BASE}/vaccine/coverage/countries/{valid_country}"

        try:
            vaxx = await ctx.get(vaxx_url, cache__=True, lastdays=lastdays)
        except HTTPRequestFailed:
            pass
        else:
            data["vaccines"] = vaxx["timeline"]

        return data

    # The alternative to type ignoring the logarithmic parameter is
    # to wrap it twice in Annotated, which is much more convoluted.
    # Same reasoning goes for `covid19 country`.
    @commands.group(
        invoke_without_command=True,
        aliases=("covid", "coronavirus", "corona"),
        usage="[-log]",
    )
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def covid19(
        self,
        ctx: SleepyContext,
        logarithmic: Annotated[bool, Optional[_positional_bool_flag("-log")]] = False,  # type: ignore
    ) -> None:
        """Shows detailed global COVID-19 statistics.

        By default, this graphs the historical data linearly.
        To graph the data logarithmically, pass `-log`.

        (Bot Needs: Embed Links and Attach Files)
        """
        async with ctx.typing():
            latest = await ctx.get(f"{self.BASE}/all", cache__=True)
            hist = await self._get_world_history_data(ctx)

            buffer, delta = await self.plot_historical_data(
                **hist, logarithmic=logarithmic
            )

        embed = Embed(
            title="COVID-19 Statistics",
            colour=Colour.dark_embed(),
            timestamp=datetime.fromtimestamp(latest["updated"] / 1000, timezone.utc),
        )
        embed.set_footer(text=f"Powered by disease.sh \N{BULLET} Took {delta:.2f} ms.")
        embed.set_image(url="attachment://covid19_graph.png")
        embed.set_author(name="World", icon_url="http://tny.im/nDe")

        new_cases = latest["todayCases"]
        new_dead = latest["todayDeaths"]
        new_recover = latest["todayRecovered"]

        embed.add_field(
            name="Cases",
            value=f"{latest['cases']:,d} {f'({new_cases:+,d})' if new_cases != 0 else ''}",
        )
        embed.add_field(name="Tests", value=f"{latest['tests']:,d}")
        embed.add_field(
            name="Deaths",
            value=f"{latest['deaths']:,d} {f'({new_dead:+,d})' if new_dead != 0 else ''}",
        )
        embed.add_field(
            name="Cases Per Million", value=f"{latest['casesPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Tests Per Million", value=f"{latest['testsPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Deaths Per Million", value=f"{latest['deathsPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Recovered",
            value=f"{latest['recovered']:,d} {f'({new_recover:+,d})' if new_recover != 0 else ''}",
        )
        embed.add_field(name="Active Cases", value=f"{latest['active']:,d}")
        embed.add_field(name="Critical Cases", value=f"{latest['critical']:,d}")
        embed.add_field(
            name="Recovered Per Million", value=f"{latest['recoveredPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Active Per Million", value=f"{latest['activePerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Critical Per Million", value=f"{latest['criticalPerOneMillion']:,.2f}"
        )
        embed.add_field(name="Population", value=f"{latest['population']:,d}")
        embed.add_field(name="Affected Countries", value=latest['affectedCountries'])

        await ctx.send(embed=embed, file=File(buffer, "covid19_graph.png"))

    @covid19.command(name="country", usage="[-log] <country>")
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def covid19_country(
        self,
        ctx: SleepyContext,
        logarithmic: Annotated[bool, Optional[_positional_bool_flag("-log")]] = False,  # type: ignore
        *,
        country: Annotated[str, clean_input],
    ) -> None:
        """Shows detailed COVID-19 statistics for a country.

        By default, this graphs the historical data linearly.
        To graph the data logarithmically, pass `-log` before
        the country argument.

        (Bot Needs: Embed Links and Attach Files)

        **EXAMPLES:**
        ```bnf
        <1> covid19 country USA
        <2> covid19 country -log USA
        ```
        """
        async with ctx.typing():
            try:
                latest = await ctx.get(f"{self.BASE}/countries/{country}", cache__=True)
            except HTTPRequestFailed as exc:
                if exc.status == 404:
                    await ctx.send(exc.data["message"])
                    return

                raise

            hist = await self._get_country_history_data(ctx, country)

            if hist is None:
                buffer = None
            else:
                buffer, delta = await self.plot_historical_data(
                    **hist, logarithmic=logarithmic
                )

        embed = Embed(
            title="COVID-19 Statistics",
            colour=Colour.dark_embed(),
            timestamp=datetime.fromtimestamp(latest["updated"] / 1000, timezone.utc),
        )
        embed.set_author(name=latest["country"], icon_url=latest["countryInfo"]["flag"])

        new_cases = latest["todayCases"]
        new_dead = latest["todayDeaths"]
        new_recover = latest["todayRecovered"]

        embed.add_field(
            name="Cases",
            value=f"{latest['cases']:,d} {f'({new_cases:+,d})' if new_cases != 0 else ''}",
        )
        embed.add_field(name="Tests", value=f"{latest['tests']:,d}")
        embed.add_field(
            name="Deaths",
            value=f"{latest['deaths']:,d} {f'({new_dead:+,d})' if new_dead != 0 else ''}",
        )
        embed.add_field(
            name="Cases Per Million", value=f"{latest['casesPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Tests Per Million", value=f"{latest['testsPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Deaths Per Million", value=f"{latest['deathsPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Recovered",
            value=f"{latest['recovered']:,d} {f'({new_recover:+,d})' if new_recover != 0 else ''}",
        )
        embed.add_field(name="Active Cases", value=f"{latest['active']:,d}")
        embed.add_field(name="Critical Cases", value=f"{latest['critical']:,d}")
        embed.add_field(
            name="Recovered Per Million", value=f"{latest['recoveredPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Active Per Million", value=f"{latest['activePerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Critical Per Million", value=f"{latest['criticalPerOneMillion']:,.2f}"
        )
        embed.add_field(name="Population", value=f"{latest['population']:,d}")
        embed.add_field(name="Continent", value=latest['continent'] or "N/A")

        if buffer is not None:
            # delta isn't unbound if the buffer isn't None.
            embed.set_footer(
                text=f"Powered by disease.sh \N{BULLET} Took {delta:.2f} ms."  # type: ignore
            )
            embed.set_image(url="attachment://covid19_graph.png")
            await ctx.send(embed=embed, file=File(buffer, filename="covid19_graph.png"))
        else:
            embed.set_footer(text="Powered by disease.sh")
            embed.description = "Historical data is unavailable for this location."
            await ctx.send(embed=embed)

    @covid19.command(name="unitedstates", aliases=("us", "usa"))
    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(2, 5, commands.BucketType.member)
    async def covid19_unitedstates(
        self, ctx: SleepyContext, *, state: Annotated[str, clean_input]
    ) -> None:
        """Shows detailed COVID-19 statistics for a U.S. entity.

        This includes statistics from states, territories, repatriated
        citizens, veteran affairs, federal prisons, the U.S. military,
        and the Navajo Nation.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        covid19 unitedstates New York
        ```
        """
        try:
            latest = await ctx.get(f"{self.BASE}/states/{state}", cache__=True)
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send(exc.data["message"])
                return

            raise

        embed = Embed(
            title="COVID-19 Statistics",
            colour=Colour.dark_embed(),
            timestamp=datetime.fromtimestamp(latest["updated"] / 1000, timezone.utc),
        )
        embed.set_footer(text="Powered by disease.sh")
        embed.set_author(name=latest["state"])

        new_cases = latest["todayCases"]
        new_dead = latest["todayDeaths"]

        embed.add_field(
            name="Cases",
            value=f"{latest['cases']:,d} {f'({new_cases:+,d})' if new_cases != 0 else ''}",
        )
        embed.add_field(name="Tests", value=f"{latest['tests']:,d}")
        embed.add_field(
            name="Deaths",
            value=f"{latest['deaths']:,d} {f'({new_dead:+,d})' if new_dead != 0 else ''}",
        )
        embed.add_field(
            name="Cases Per Million", value=f"{latest['casesPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Tests Per Million", value=f"{latest['testsPerOneMillion']:,.2f}"
        )
        embed.add_field(
            name="Deaths Per Million", value=f"{latest['deathsPerOneMillion']:,.2f}"
        )
        embed.add_field(name="Recovered", value=f"{latest['recovered']:,d}")
        embed.add_field(name="Active Cases", value=f"{latest['active']:,d}")

        await ctx.send(embed=embed)


async def setup(bot: Sleepy) -> None:
    await bot.add_cog(Covid())
