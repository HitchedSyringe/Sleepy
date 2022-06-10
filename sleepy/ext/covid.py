"""
Copyright (c) 2018-present HitchedSyringe

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import quote

from discord import Embed, File
from discord.ext import commands
from jishaku.functools import executor_function
from matplotlib import pyplot as plt
from matplotlib.dates import AutoDateLocator, DateFormatter, datestr2num
from matplotlib.figure import Figure
from typing_extensions import Annotated

from sleepy.converters import _pseudo_bool_flag
from sleepy.http import HTTPRequestFailed
from sleepy.utils import human_number, measure_performance

if TYPE_CHECKING:
    from sleepy.bot import Sleepy
    from sleepy.context import Context as SleepyContext


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

    return value


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

    @staticmethod
    @executor_function
    @measure_performance
    def plot_historical_data(
        cases: Dict[str, Any],
        deaths: Dict[str, Any],
        recovered: Dict[str, Any],
        vaccines: Optional[Dict[str, Any]] = None,
        *,
        logarithmic: bool = False,
    ) -> io.BytesIO:
        timeline = datestr2num(tuple(cases))

        c_counts = cases.values()
        d_counts = deaths.values()
        r_counts = recovered.values()
        # For reference, the equation to estimate
        # the number of active cases:
        # active = cases - deaths - recoveries
        a_counts = [c - d - r for c, d, r in zip(c_counts, d_counts, r_counts)]

        # Have to use to figure object directly since pyplot
        # uses tkinter internally, which doesn't play nice
        # when async gets involed.
        fig = Figure(facecolor="#2F3136")

        fig.text(
            0.13,
            -0.01,
            "*Estimated based on given numbers of cases, deaths, and recoveries.",
            fontsize=7,
            color="#99AAB5",
        )

        fig.text(
            0.895,
            -0.01,
            "\N{COPYRIGHT SIGN} Sleepy 2020-2022",
            fontsize=7,
            color="#99AAB5",
            ha="right",
        )

        axes = fig.subplots()

        axes.set_axisbelow(True)
        axes.xaxis.grid(color="#4F545C", linestyle="--", alpha=0.75)

        axes.spines["top"].set_visible(False)

        for name in ("left", "right", "bottom"):
            axes.spines[name].set_color("#565C65")

        axes.set_facecolor("#2F3136")
        axes.set_xlabel("Timeline", color="white")
        axes.set_ylabel("Amount", color="white")
        axes.tick_params(colors="white", labelsize="small")

        axes.plot(timeline, a_counts, ":", color="aqua", label="Active*")
        axes.plot(timeline, r_counts, "-.", color="#65B558", label="Recovered")
        axes.plot(timeline, d_counts, "--", color="#ED7734", label="Deaths")
        axes.plot(timeline, c_counts, "-", color="#1F94E2", label="Cases")

        axes.fill_between(timeline, c_counts, r_counts, color="#0D87D8", alpha=0.5)
        axes.fill_between(timeline, r_counts, d_counts, color="#52A046", alpha=0.5)
        axes.fill_between(timeline, d_counts, color="#FF5E00", alpha=0.5)

        axes.xaxis.set_major_locator(AutoDateLocator(maxticks=8))
        axes.xaxis.set_major_formatter(DateFormatter("%b %Y"))

        def human_number_formatter(x: float, _) -> str:
            return human_number(x)

        handles = None

        if logarithmic:
            axes.set_title("COVID-19 Historical Statistics (Logarithmic)", color="white")
            axes.set_yscale("symlog")

            axes.yaxis.set_major_formatter(human_number_formatter)

            if vaccines is not None:
                axes.plot(
                    datestr2num(tuple(vaccines)),
                    vaccines.values(),
                    "--",
                    color="#FFDC82",
                    label="Vaccine Doses",
                    dashes=(6, 2),
                )
        else:
            axes.set_title("COVID-19 Historical Statistics (Linear)", color="white")
            axes.yaxis.set_major_formatter(human_number_formatter)

            if vaccines is not None:
                # The cases data would get squashed if the vaccine
                # Plotting the vaccine data linearly as-is without
                # scaling it relative to the other data squashes
                # the since the doses counts are far greater than
                # the cases counts. Also, the data starts in Dec
                # 2020. To work around this, use twinx to make the
                # y axes independent, then plot the data.
                v_axes = axes.twinx()

                v_axes.set_frame_on(False)
                v_axes.set_ylabel(
                    "Vaccine Doses", color="#FFDC82", rotation=270, va="bottom"
                )

                v_axes.tick_params(axis="y", colors="#FFDC82", labelsize="small")
                v_axes.yaxis.set_major_formatter(human_number_formatter)

                handles, _ = axes.get_legend_handles_labels()

                handles += v_axes.plot(
                    datestr2num(tuple(vaccines)),
                    vaccines.values(),
                    "--",
                    color="#FFDC82",
                    label="Vaccine Doses",
                    dashes=(6, 2),
                )

                # Unfortunately, shadowing the original axes object,
                # while normally a bad idea, is necessary since the
                # legend must be drawn using v_axes, otherwise it is
                # drawn under v_axes, which also comes with problems
                # when using loc="best" (the default).
                axes = v_axes

        axes.legend(
            handles=handles,
            labelcolor="white",
            facecolor="0.1",
            edgecolor="none",
            fancybox=False,
        )

        buffer = io.BytesIO()

        fig.savefig(buffer, format="png", bbox_inches="tight")
        plt.close(fig)

        buffer.seek(0)

        return buffer

    # The alternative to type ignoring the logarithmic parameter is
    # to wrap it twice in Annotated, which is much more convoluted.
    # Same reasoning goes for `covid19 country`.
    @commands.group(
        invoke_without_command=True,
        aliases=("covid", "coronavirus", "corona"),
        usage="[--logarithmic|--log]",
    )
    @commands.bot_has_permissions(embed_links=True, attach_files=True)
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def covid19(
        self,
        ctx: SleepyContext,
        logarithmic: Annotated[
            bool, Optional[_pseudo_bool_flag("--log", "--logarithmic")]  # type: ignore
        ] = False,
    ) -> None:
        """Shows detailed global COVID-19 statistics.

        By default, this graphs the historical data
        linearly. To graph the data logarithmically,
        pass either `--log` or `--logarithmic`.

        (Bot Needs: Embed Links and Attach Files)
        """
        async with ctx.typing():
            latest = await ctx.get(f"{self.BASE}/all", cache__=True)

            hist = await ctx.get(f"{self.BASE}/historical/all?lastdays=all", cache__=True)

            hist["vaccines"] = await ctx.get(
                f"{self.BASE}/vaccine/coverage?lastdays=all", cache__=True
            )

            buffer, delta = await self.plot_historical_data(
                **hist, logarithmic=logarithmic
            )

        embed = Embed(
            title="Global COVID-19 Statistics",
            colour=0x2F3136,
            timestamp=datetime.fromtimestamp(latest["updated"] / 1000, timezone.utc),
        )
        embed.set_footer(text=f"Powered by disease.sh \N{BULLET} Took {delta:.2f} ms.")
        embed.set_image(url="attachment://covid19_graph.png")
        embed.set_thumbnail(url="http://tny.im/nDe")

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

    @covid19.command(name="country", usage="[--logarithmic|--log] <country>")
    @commands.max_concurrency(5, commands.BucketType.guild)
    async def covid19_country(
        self,
        ctx: SleepyContext,
        logarithmic: Annotated[
            bool, Optional[_pseudo_bool_flag("--log", "--logarithmic")]  # type: ignore
        ] = False,
        *,
        country: Annotated[str, clean_input],
    ) -> None:
        """Shows detailed COVID-19 statistics for a country.

        By default, this graphs the historical data linearly.
        To graph the data logarithmically, pass either `--log`
        or `--logarithmic` before the country argument.

        (Bot Needs: Embed Links and Attach Files)

        **EXAMPLES:**
        ```bnf
        <1> covid19 country USA
        <2> covid19 country --logarithmic USA
        ```
        """
        async with ctx.typing():
            try:
                latest = await ctx.get(
                    f"{self.BASE}/countries/{quote(country)}", cache__=True
                )
            except HTTPRequestFailed as exc:
                if exc.status == 404:
                    await ctx.send(exc.data["message"])
                    return

                raise

            country = latest["country"]

            try:
                hist = await ctx.get(
                    f"{self.BASE}/historical/{country}?lastdays=all", cache__=True
                )
            except HTTPRequestFailed:
                # Either worldometers has data on a country that jhucsse
                # historical doesn't, or the "country" is actually considered
                # a province on jhucsse's end. Either way, there's nothing we
                # can really do without overcomplicating things.
                buffer = None
            else:
                hist = hist["timeline"]

                # I absolutely hate this level of nesting, but unfortunately,
                # there isn't a better or cleaner way of doing this.
                try:
                    v_hist = await ctx.get(
                        f"{self.BASE}/vaccine/coverage/countries/{country}?lastdays=all",
                        cache__=True,
                    )
                except HTTPRequestFailed:
                    pass
                else:
                    hist["vaccines"] = v_hist["timeline"]

                buffer, delta = await self.plot_historical_data(
                    **hist, logarithmic=logarithmic
                )

        embed = Embed(
            title=f"{country} COVID-19 Statistics",
            colour=0x2F3136,
            timestamp=datetime.fromtimestamp(latest["updated"] / 1000, timezone.utc),
        )
        embed.set_thumbnail(url=latest["countryInfo"]["flag"])

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

        This includes statistics from states, territories,
        repatriated citizens, veteran affairs, federal
        prisons, the U.S. military, and the Navajo Nation.

        (Bot Needs: Embed Links)

        **EXAMPLE:**
        ```
        covid19 unitedstates New York
        ```
        """
        try:
            latest = await ctx.get(f"{self.BASE}/states/{quote(state)}", cache__=True)
        except HTTPRequestFailed as exc:
            if exc.status == 404:
                await ctx.send(exc.data["message"])
                return

            raise

        embed = Embed(
            title="COVID-19 Statistics",
            colour=0x2F3136,
            timestamp=datetime.fromtimestamp(latest["updated"] / 1000, timezone.utc),
        )
        embed.set_footer(text="Powered by disease.sh")

        name = latest["state"]
        name_url = name.lower().replace(" ", "-")

        embed.set_author(
            name=name,
            icon_url=f"https://cdn.civil.services/us-states/flags/{name_url}-large.png",
        )
        embed.set_thumbnail(
            url=f"https://cdn.civil.services/us-states/seals/{name_url}-large.png"
        )

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
