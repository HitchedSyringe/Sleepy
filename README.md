<h1 align="center">Sleepy</h1>

<div align="center">

[![Bot Version](https://img.shields.io/github/v/release/HitSyr/Sleepy?color=F0D273&label=version)](https://github.com/HitSyr/Sleepy)
[![Supported Python Versions](https://img.shields.io/badge/python-3.8%2b-blue?logo=python)](https://python.org/)
[![Project License](https://img.shields.io/badge/license-MPL--2.0-orange)](LICENSE)
[![Discord Server](https://discord.com/api/guilds/495593721371295755/widget.png?style=shield)](https://discord.com/invite/xHgh2Xg)

</div>

A Discord bot with server moderation, fun commands, image manipulation, and much more, all designed with user-friendliness and simplicity in mind.

To invite my bot, either use the `invite` command in a server the bot is in, or [click here](https://discord.com/api/oauth2/authorize?client_id=507754861585235978&permissions=388166&scope=bot). For more information, feel free to check out the bot's [support server](https://discord.com/invite/xHgh2Xg)!

I would prefer that you don't run an instance of my bot. The source code here is provided for both transparency reasons and educational purposes for discord.py. Just use the instance that I'm hosting. Nevertheless, the instructions to set up the bot are located [here](#installation).

## 27th August, 2021 - The Future of Sleepy

This is a statement regarding the future of this project in light of Rapptz (Danny)'s recent decision to put an end to discord.py.

This announcement alone comes as a shock to everyone, including users, developers, and of course, myself, who all depend on this library in some way, shape, or form. I 100% respect Danny's decision to end development and wish him the best on his future endeavours. For those that do not know, discord.py is the backbone of what allows the bot to be able to interact with Discord. In essence, the ending of discord.py has now put the future of this project's development in jeopardy since we're now running on an unsupported library.

For starters, this bot will continue to be maintained until the Discord API version that discord.py 1.7 uses reaches its EOL. When this happens, I will formally step down as the sole developer and thereby end it. I know this is sad for everyone to hear, but unfortunately, I can't afford the time and effort to rewrite this bot to another language or to use another library. Furthermore, learning about the sensitive nature of what has occurred between Discord and library developers, I do not foresee myself making or involving myself in any projects which interact with Discord in any way, shape, or form moving forward. For those migrating from discord.py, I would advise waiting on doing so as I cannot say for certain that any other library developers will take similar steps as Danny did in light of what has occurred over the past 3 years.

I will leave this source code published and open for any future people who wish to carry the torch that I will leave behind in the future. For the ~3 years I have spent on this project, I thank everyone for using the bot up until this point. It genuinely means a lot to me. 🙂

For more information on why Danny decided to discontinue discord.py, please read his gist [here](https://gist.github.com/Rapptz/4a2f62751b9600a31a0d3c78100287f1).

## License

This project is licensed under the [Mozilla Public License, v. 2.0](https://mozilla.org/en-US/MPL/2.0/). See [LICENSE](LICENSE) for more information.

The license as of commit `6337f3cde11450b5ca637183009f91b0483b7fdb` also applies to commits prior, regardless of the license(s) stated.

## Versioning

The version number has a 3-digit format: `major.minor.micro`

* `major` updates are rare and only used for massive rewrites affecting huge parts of the bot.
* `minor` updates are any breaking or backwards incompatible change to the bot. This is usually a feature addition or the removal or renaming of classes, methods, attributes, and/or commands.
* `micro` updates are any backwards compatible changes. This is usually an important bug fix (or a bunch of smaller ones), adjustment, or extension to a current feature.

## Contributing

Contributions are 100% welcome! Feel free to open an issue or submit a pull request.

When adding commands, look at the other commands in the category and pick which category the command fits best. To test your changes, please refer to the [setup instructions](#installation).

## Dependencies

* [aiofiles](https://github.com/Tinche/aiofiles)
* [cachetools](https://github.com/tkem/cachetools) (optional)
* [discord.py 1.7.x](https://github.com/Rapptz/discord.py)
* [discord-ext-menus](https://github.com/Rapptz/discord-ext-menus)
* [discord-flags 2.1.0+](https://github.com/XuaTheGrate/Flag-Parsing)
  * ⚠️ NOTICE: This package has been deprecated and is subject to removal by its maintainer. This dependency will eventually be removed and replaced with the implementation in discord.py 2.0. Until then, using `requirements.txt` will install [my fork](https://github.com/HitSyr/Flag-Parsing) of the above linked repository to ensure nothing breaks in the meantime.
* [emoji](https://github.com/carpedm20/emoji)
* [googletrans 4.0.0rc1+](https://github.com/ssut/py-googletrans)
* [jishaku 2.2.0+](https://github.com/Gorialis/jishaku)
* [matplotlib](https://github.com/matplotlib/matplotlib)
* [opencv-python-headless](https://github.com/opencv/opencv-python)
* [Pillow 8.0.0+](https://github.com/python-pillow/Pillow)
* [psutil](https://github.com/giampaolo/psutil)
* [pyyaml](https://github.com/yaml/pyyaml)

### Required for typings

* [types-cachetools](https://github.com/python/typeshed/tree/master/stubs/cachetools) (only if `cachetools` is installed)
* [discord.py-stubs 1.7.x](https://github.com/bryanforbes/discord.py-stubs)

## Installation

1. **Make sure to get Python 3.8 or higher.**

    This is required to actually run the bot.

2. **Install the dependencies.**

    Use `pip install -U -r requirements.txt`.

    If you plan on using typings, use `pip install -U -r requirements-typings.txt` instead.

3. **Configure the bot.**

    The next step is to set the configuration variables found in the `config_template.yaml` file. If necessary, a raw copy/paste-able version can be found [here](config_template.yaml).
    * Set the variables as desired. Descriptions for each variable are provided in the file.
        * In order to run the bot, `discord_auth_token` must have a valid bot token. You can acquire one from Discord's [developer portal](https://discord.com/developers).
        * `id` and `token` under `discord_webhook` must also have a valid webhook ID and token, respectively. Read Discord's [support article](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks) on webhooks for more information.
    * When finished, rename `config_template.yaml` to `config.yaml`.
        * You may also rename this file to whatever you like, however, you must follow the special running instructions specified below.

4. **Run the bot.**

    When all of the above steps are complete, run the bot using `python -m sleepy`.
    > **NOTE**
    >
    > The above will attempt to load `config.yaml` by default.
    > For custom named configuration files, an optional third argument can be passed to the above in order to specify a configuration file to load. The file name must be surrounded in quotation marks if it contains any spaces.
    >
    > Example: `python -m sleepy myrenamedconfig.yaml` attempts to load the configuration file named `myrenamedconfig.yaml` instead of the default `config.yaml`.

## Important Notes

* The bot's extension loader has special behaviour that allows for easy handling of extensions at startup, without the hassle of having to hardcode the names of any extensions. For ease of understanding, the extension loading behaviour is as follows:
  * If `enable_autoload` is set to `true`, the loader will assume that **ANY** existing Python files or modules in the extensions directory are valid extensions and will attempt to load them on startup.
  * If `enable_autoload` is set to `false`, any valid extensions not listed under `extensions_list` in your config will be ignored on startup.
