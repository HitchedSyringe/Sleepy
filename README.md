<h1 align="center">Sleepy</h1>

<div align="center">

[sleepy]: https://github.com/HitchedSyringe/Sleepy
[sleepy-s]: https://img.shields.io/github/v/release/HitchedSyringe/Sleepy?color=FDC86F&label=version
[python]: https://python.org
[python-s]: https://img.shields.io/badge/python-3.8%2b-blue?logo=python
[license]: https://github.com/HitchedSyringe/Sleepy/blob/master/LICENSE
<!-- Hard-coded because GitHub can't identify the license due to the inclusion of other licenses in the file. -->
[license-s]: https://img.shields.io/badge/license-MPL--2.0-orange
[discord]: https://discord.com/invite/xHgh2Xg
[discord-s]: https://discord.com/api/guilds/495593721371295755/widget.png?style=shield

[![sleepy-s][]][sleepy]
[![python-s][]][python]
[![license-s][]][license]
[![discord-s][]][discord]

</div>

A Discord bot with server moderation, fun commands, image manipulation, and much more, all designed with user-friendliness and simplicity in mind.

For more information, feel free to check out the bot's [support server][discord].

## NOTICE - 17th February 2023

Due to personal reasons, I will no longer be hosting an official public instance as of today. Therefore, effective immediately, the existing public instance will become private and leave every server it has been added to. That being said, the codebase and support server will continue to be maintained and remain public.

If you wish to have an instance of this bot running in your server, feel free to follow the [setup instructions](#installation). Note that if you choose to invite any third-party hosted instances of this bot, you assume all risks that come with doing so.

## License

This project is licensed under the [Mozilla Public License, v. 2.0](https://mozilla.org/en-US/MPL/2.0/). See [LICENSE][license] for more information.

The license as of commit `6337f3cde11450b5ca637183009f91b0483b7fdb` also applies to commits prior, regardless of the license(s) stated.

## Versioning

The version number has a 3-digit format: `main.major.micro`

* `main` updates are rare and only used for massive rewrites affecting huge parts of the bot.
* `major` updates are any breaking or backwards incompatible change to the bot. This is usually a feature addition, removal, or extension; or the removal or renaming of classes, methods, attributes, and/or commands.
* `micro` updates are any backwards compatible changes. This is usually an important bug fix (or a bunch of smaller ones) or minor adjustment to a current feature.

## Contributing

Contributions are 100% welcome! Feel free to open an issue or submit a pull request.

When adding commands, pick an existing category where the command would best fit based on the other commands contained within. For example, an image manipulation command should be placed in the `Images` category.

To test your changes, please refer to the [setup instructions](#installation).

## Dependencies

* [discord.py 2.0.0+](https://github.com/Rapptz/discord.py)
* [discord-ext-menus](https://github.com/Rapptz/discord-ext-menus)
* [emoji 1.6.0+](https://github.com/carpedm20/emoji)
* [googletrans 4.0.0rc1+](https://github.com/ssut/py-googletrans)
* [jishaku 2.4.0+](https://github.com/Gorialis/jishaku)
* [matplotlib](https://github.com/matplotlib/matplotlib)
* [opencv-python-headless](https://github.com/opencv/opencv-python)
* [Pillow 9.2.0+](https://github.com/python-pillow/Pillow)
* [psutil](https://github.com/giampaolo/psutil)
* [pyfiglet](https://github.com/pwaller/pyfiglet)
* [pyyaml](https://github.com/yaml/pyyaml)
* [scikit-image](https://github.com/scikit-image/scikit-image)
* [typing_extensions 4.x](https://github.com/python/typing_extensions)

## Optional Dependencies

Dependencies used in the bot for the purposes of convenience or speed. While not required to run the bot normally, these are recommended for the sake of the above.

* [cachetools](https://github.com/tkem/cachetools)
* [orjson](https://github.com/ijl/orjson)
* [uvloop](https://github.com/MagicStack/uvloop) (**not supported on Windows**)

## Installation

1. **Make sure to get Python 3.8 or higher.**

    This is required to actually run the bot.

2. **Install the dependencies.**

    Use `pip install -U -r requirements.txt`.

3. **Configure the bot.**

    The next step is to set the configuration variables found in the `config_template.yaml` file. If necessary, a raw copy/paste-able version can be found [here](https://raw.githubusercontent.com/HitchedSyringe/Sleepy/master/config_template.yaml).
    * Set the variables as desired. Descriptions for each variable are provided in the file.
        * In order to run the bot, `discord_auth_token` must have a valid bot token. You can acquire one from Discord's [developer portal](https://discord.com/developers).
        * `id` and `token` under `discord_webhook` must also have a valid webhook ID and token, respectively. Read Discord's [support article](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks) on webhooks for more information.
    * When finished, rename `config_template.yaml` to `config.yaml`.
        * You may also rename this file to whatever you like, however, you must follow the special running instructions specified below in the next step.

4. **Run the bot.**

    When all of the above steps are complete, run the bot using `python -m sleepy`.

    > **NOTE**
    >
    > The above command, as is, will attempt to load `config.yaml` by default. For custom named configuration files, an optional third argument can be passed in order to specify a configuration file to load.
    >
    > The file name must be surrounded by quotation marks if it contains any spaces. For example, `python -m sleepy myrenamedconfig.yaml` will attempt to load the configuration file named `myrenamedconfig.yaml` instead of the default `config.yaml`.

## Important Notes

* The bot's extension loader has special behaviour that allows for easy handling of extensions at startup, without the hassle of having to hardcode the names of any extensions. For ease of understanding, the extension loading behaviour is as follows:
  * If `enable_autoload` is set to `true`, the loader will assume that **ANY** existing Python files or modules in the extensions directory are valid extensions and will attempt to load them on startup.
  * If `enable_autoload` is set to `false`, any valid extensions not listed under `extensions_list` in your config will be ignored on startup.
* As of `v3.2.0`, the bot will utilize `uvloop` if it is installed.
* As of `v3.3.0`:
    * The bot includes a proper command-line interface. For usage information, use `python -m sleepy --help`.
    * The bot will utilize `orjson` for deserializing and serializing JSON in its HTTP requester.
