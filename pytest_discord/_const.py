from enum import Enum, auto, unique
from textwrap import dedent

from pathvalidate import replace_symbol
from pytest_md_report import ColorPolicy


class Default:
    COLOR = ColorPolicy.AUTO
    USERNAME = "pytest-discord"


@unique
class TestResultType(Enum):
    SUCCESS = auto()
    SKIP = auto()
    FAIL = auto()


@unique
class Option(Enum):
    DISCORD_WEBHOOK = (
        "discord-webhook",
        "discord webhook url of a discord channel to notify pytest results.",
    )
    DISCORD_VERBOSE = (
        "discord-verbose",
        dedent(
            """\
            verbosity level for pytest-discord. if not set, using verbosity level of pytest.
            defaults to 0.
            """
        ),
    )
    DISCORD_USERNAME = (
        "discord-username",
        f"name for a message. defaults to {Default.USERNAME}.",
    )
    DISCORD_SUCCESS_ICON = (
        "discord-success-icon",
        "url to an icon of a successful run.",
    )
    DISCORD_SKIP_ICON = ("discord-skip-icon", "url to an icon of a skipped run.")
    DISCORD_FAIL_ICON = ("discord-fail-icon", "url to an icon of a failed run.")
    DISCORD_ATTACH_FILE = (
        "discord-attach-file",
        "post pytest results as a markdown file to a discord channel.",
    )

    @property
    def cmdoption_str(self) -> str:
        return "--" + replace_symbol(self.__name, "-").lower()

    @property
    def envvar_str(self) -> str:
        return "PYTEST_" + replace_symbol(self.__name, "_").upper()

    @property
    def inioption_str(self) -> str:
        return replace_symbol(self.__name, "_").lower()

    @property
    def help_msg(self) -> str:
        return self.__help_msg

    def __init__(self, name: str, help_msg: str) -> None:
        self.__name = name.strip()
        self.__help_msg = help_msg


class HelpMsg:
    EXTRA_MSG_TEMPLATE = " you can also specify the value with {} environment variable."
