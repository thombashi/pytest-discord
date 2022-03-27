import os
from typing import Optional

from _pytest.config import Config
from typepy import Bool, Integer, StrictLevel
from typepy.error import TypeConversionError

from ._const import Default, Option


class DiscordOptRetriever:
    def __init__(self, config: Config):
        self.__config = config

    def retrieve_webhook_url(self) -> Optional[str]:
        return self.__retrieve_discord_opt(Option.DISCORD_WEBHOOK)

    def retrieve_verbosity_level(self) -> int:
        config = self.__config
        discord_opt = Option.DISCORD_VERBOSE
        verbosity_level = None

        if hasattr(config.option, discord_opt.inioption_str):
            verbosity_level = getattr(config.option, discord_opt.inioption_str)

        if verbosity_level is not None and verbosity_level < 0:
            verbosity_level = None

        if verbosity_level is None:
            verbosity_level = self._to_int(os.environ.get(discord_opt.envvar_str))

        if verbosity_level is None:
            verbosity_level = self._to_int(config.getini(discord_opt.inioption_str))

        if verbosity_level is None:
            verbosity_level = config.option.verbose

        return verbosity_level

    def retrieve_username(self) -> str:
        username = self.__retrieve_discord_opt(Option.DISCORD_USERNAME)

        if not username:
            return Default.USERNAME

        return username

    def retrieve_success_icon(self) -> Optional[str]:
        return self.__retrieve_discord_opt(Option.DISCORD_SUCCESS_ICON)

    def retrieve_skip_icon(self) -> Optional[str]:
        return self.__retrieve_discord_opt(Option.DISCORD_SKIP_ICON)

    def retrieve_fail_icon(self) -> Optional[str]:
        return self.__retrieve_discord_opt(Option.DISCORD_FAIL_ICON)

    def retrieve_attach_file(self) -> bool:
        config = self.__config
        discord_opt = Option.DISCORD_ATTACH_FILE
        value = None

        if hasattr(config.option, discord_opt.inioption_str):
            value = getattr(config.option, discord_opt.inioption_str)

        if value is None:
            try:
                value = Bool(
                    os.environ.get(discord_opt.envvar_str), strict_level=StrictLevel.MIN
                ).convert()
            except TypeConversionError:
                value = None

        if value is None:
            value = config.getini(discord_opt.inioption_str)

        if value is None:
            return False

        return value

    def __retrieve_discord_opt(self, discord_opt: Option) -> Optional[str]:
        config = self.__config
        value = None

        if hasattr(config.option, discord_opt.inioption_str):
            value = getattr(config.option, discord_opt.inioption_str)

        if not value:
            value = os.environ.get(discord_opt.envvar_str)

        if not value:
            value = config.getini(discord_opt.inioption_str)

        return value

    @staticmethod
    def _to_int(value) -> Optional[int]:
        try:
            return Integer(value, strict_level=StrictLevel.MIN).convert()
        except TypeConversionError:
            return None
