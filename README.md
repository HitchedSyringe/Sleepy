
# Sleepy

[![img.shields.io](https://img.shields.io/badge/Version-v2.0.0-dbc476?style=for-the-badge&labelColor=f0d273)](https://img.shields.io)
[![forthebadge](https://forthebadge.com/images/badges/made-with-python.svg)](https://forthebadge.com)
[![forthebadge](https://forthebadge.com/images/badges/built-with-love.svg)](https://forthebadge.com)

A (mostly) user-friendly Discord bot with server moderation, fun commands, image manipulation and much, much more. This bot is currently only maintained by an individual, so features and fixes may take some time to release.

To invite my bot, either use the `invite` command in a server the bot is in, or [click here](https://discord.com/api/oauth2/authorize?client_id=507754861585235978&permissions=470150246&scope=bot). For more information, feel free to check out the bot's [support server](https://discord.gg/xHgh2Xg)!

## License

© Copyright 2018-2020 HitchedSyringe, All Rights Reserved.

Redistributing, using or owning a copy of this software without explicit permissions
is against these licensing terms, your license(s) to this software can be revoked at
any time without explicit notice beforehand and at the time of revocation.
Your license is non-transferrable, the terms of this license only permit you to do the
following; Create pull requests and make modifications to this repository.

## Versioning

The version number has a 3-digit format: `major.minor.micro`

* `major` updates are rare and only used for massive rewrites affecting huge parts of the bot.
* `minor` updates are any breaking or backwards incompatible change to the bot. This is usually the removal or renaming of classes, methods, attributes, or commands.
* `micro` updates are any backwards compatible changes. This is usually an important bug fix (or a bunch of smaller ones), adjustment, or feature addition.

## Contributing

When adding commands, look at the other commands in the cog and pick which cog the command fits best.

*You may run a **private instance** to test your changes. Please refer to the setup instructions below.*

## Requirements

* [Python 3.7.0+](https://www.python.org)
* [aiofiles](https://github.com/Tinche/aiofiles)
* [cachetools](https://github.com/tkem/cachetools/)
* [discord.py 1.4.0+](https://www.github.com/Rapptz/discord.py)
* [discord-ext-menus](https://www.github.com/Rapptz/discord-ext-menus)
* [discord-flags 2.1.0+](https://github.com/XuaTheGrate/Flag-Parsing)
* [emoji](https://github.com/carpedm20/emoji/)
* [googletrans](https://github.com/ssut/py-googletrans)
* [matplotlib](https://github.com/matplotlib/matplotlib)
* [psutil](https://github.com/giampaolo/psutil)
* [pyyaml](https://github.com/yaml/pyyaml)

## Installation

1. **Make sure to get Python 3.7 or higher**

    This is required to actually run the bot.

2. **Install the dependencies**

    Use `pip install -U -r requirements.txt`.

3. **Setup configuration**

    The next step is to set the configuration variables found in the `config_template.ini` file. If necessary, a raw copy/paste-able version can be found [here](https://raw.githubusercontent.com/HitSyr/Sleepy/master/config_template.ini).
    * Set the variables as desired. Descriptions for each variable are provided in the file.
        * In order to run the bot, `discord_bot_token` (under `Secrets`) must have a valid bot token. You can acquire one from Discord's [developer portal](https://www.discord.com/developers).
        * `webhook_url` (under `Secrets`) must also have a valid webhook URL. Read Discord's [support article](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks) on webhooks for more information.
    * When finished, rename `config_template.ini` to `config.ini`.
        * You may also rename this file to whatever you like, however, you must follow the special running instructions specified below.

4. **Running**

    When all of the above steps are complete, run the bot using `python -m SleepyBot`.
    > **NOTE**
    >
    > The above will attempt to load `config.ini` by default.
    > For custom named configuration files, an optional third argument can be passed to the above in order to specify a configuration file to load. Quotation marks must be used if the file name has spaces.
    >
    > Example: `python -m SleepyBot myrenamedconfig.ini` attempts to load the configuration file named `myrenamedconfig.ini` instead of the default `config.ini`.

## Important Notes

* The bot's extension loader has special behaviour that allows for easy handling of extensions at startup, without the hassle having to hardcode the names of any extensions. For ease of understanding, the extension loading behaviour is as follows:
  * When `autoload_enabled` is set to `true`, the loader assumes that **ANY** `.py` files in the extensions directory are valid extensions and will attempt to load them on startup. Extensions are ignored **IF AND ONLY IF** their filenames begin with a double underscore (i.e. `__structures.py`).
  * When `autoload_enabled` is set to `false`, extensions are ignored if they are not listed in `exts` (under `Extension Config`).
  * Any successfully loaded extensions are included in the bot's `all_exts` attribute.
