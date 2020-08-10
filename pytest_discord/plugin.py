import asyncio
import io
import os
import time
from datetime import datetime
from typing import Dict, Optional, Sequence, Tuple

import aiohttp
import pytest
from _pytest.config import Config
from _pytest.terminal import TerminalReporter
from discord import AsyncWebhookAdapter, Colour, Embed, File, Webhook
from discord.errors import Forbidden, HTTPException, InvalidArgument, NotFound
from typepy import Bool, Integer, StrictLevel
from typepy.error import TypeConversionError

from ._const import Default, HelpMsg, Option


def pytest_addoption(parser):
    group = parser.getgroup("discord", "notify test results to a discord channel")

    group.addoption(
        Option.DISCORD_WEBHOOK.cmdoption_str,
        metavar="WEBHOOK_URL",
        help=Option.DISCORD_WEBHOOK.help_msg
        + HelpMsg.EXTRA_MSG_TEMPLATE.format(Option.DISCORD_WEBHOOK.envvar_str),
    )
    group.addoption(
        Option.DISCORD_VERBOSE.cmdoption_str,
        metavar="VERBOSITY_LEVEL",
        type=int,
        default=None,
        help=Option.DISCORD_VERBOSE.help_msg
        + HelpMsg.EXTRA_MSG_TEMPLATE.format(Option.DISCORD_VERBOSE.envvar_str),
    )
    group.addoption(
        Option.DISCORD_USERNAME.cmdoption_str,
        help=Option.DISCORD_USERNAME.help_msg
        + HelpMsg.EXTRA_MSG_TEMPLATE.format(Option.DISCORD_USERNAME.envvar_str),
    )
    group.addoption(
        Option.DISCORD_SUCCESS_ICON.cmdoption_str,
        metavar="ICON_URL",
        help=Option.DISCORD_SUCCESS_ICON.help_msg
        + HelpMsg.EXTRA_MSG_TEMPLATE.format(Option.DISCORD_SUCCESS_ICON.envvar_str),
    )
    group.addoption(
        Option.DISCORD_SKIP_ICON.cmdoption_str,
        metavar="ICON_URL",
        help=Option.DISCORD_SKIP_ICON.help_msg
        + HelpMsg.EXTRA_MSG_TEMPLATE.format(Option.DISCORD_SKIP_ICON.envvar_str),
    )
    group.addoption(
        Option.DISCORD_FAIL_ICON.cmdoption_str,
        metavar="ICON_URL",
        help=Option.DISCORD_FAIL_ICON.help_msg
        + HelpMsg.EXTRA_MSG_TEMPLATE.format(Option.DISCORD_FAIL_ICON.envvar_str),
    )
    group.addoption(
        Option.DISCORD_ATTACH_FILE.cmdoption_str,
        action="store_true",
        default=None,
        help=Option.DISCORD_ATTACH_FILE.help_msg
        + HelpMsg.EXTRA_MSG_TEMPLATE.format(Option.DISCORD_ATTACH_FILE.envvar_str),
    )

    parser.addini(
        Option.DISCORD_WEBHOOK.inioption_str, default=None, help=Option.DISCORD_WEBHOOK.help_msg,
    )
    parser.addini(
        Option.DISCORD_VERBOSE.inioption_str, default=None, help=Option.DISCORD_VERBOSE.help_msg,
    )
    parser.addini(
        Option.DISCORD_USERNAME.inioption_str, default=None, help=Option.DISCORD_USERNAME.help_msg,
    )
    parser.addini(
        Option.DISCORD_SUCCESS_ICON.inioption_str,
        default=None,
        help=Option.DISCORD_SUCCESS_ICON.help_msg,
    )
    parser.addini(
        Option.DISCORD_SKIP_ICON.inioption_str,
        default=None,
        help=Option.DISCORD_SKIP_ICON.help_msg,
    )
    parser.addini(
        Option.DISCORD_FAIL_ICON.inioption_str,
        default=None,
        help=Option.DISCORD_FAIL_ICON.help_msg,
    )
    parser.addini(
        Option.DISCORD_ATTACH_FILE.inioption_str,
        type="bool",
        default=None,
        help=Option.DISCORD_ATTACH_FILE.help_msg,
    )


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
        username = self.__retrieve_discord_opt(Option.DISCORD_USERNAME)  # type: ignore

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


def _normalize_stat_name(name: str) -> str:
    if name == "error":
        return "errors"

    return name


def _make_results_message(reporter: TerminalReporter) -> Tuple[str, Dict[str, int]]:
    messages = []
    stat_count_map = {}

    for name in ["failed", "passed", "skipped", "error", "xfailed", "xpassed"]:
        count = len(reporter.getreports(name))
        stat_count_map[name] = count

        if count:
            messages.append("{} {}".format(count, _normalize_stat_name(name)))

    return (", ".join(messages), stat_count_map)


def _decorate_code_block(lang: str, text: str) -> str:
    return "```{lang}\n{body}\n```\n".format(lang=lang, body=text)


def _concat_longrepr(reporter: TerminalReporter) -> str:
    messages = []

    for stat_key, values in reporter.stats.items():
        if not stat_key or stat_key not in ["failed", "error"]:
            continue

        for i, value in enumerate(values):
            try:
                if value.longrepr:
                    messages.append(
                        "# {}: #{}\n{}".format(
                            stat_key, i + 1, _decorate_code_block(lang="py", text=value.longrepr),
                        )
                    )
            except AttributeError:
                pass

    return "\n\n\n".join(messages)


def make_mdreport(config: Config) -> str:
    from pytest_md_report import ColorPoicy, ZerosRender, make_md_report, retrieve_stat_count_map

    opt_retriever = DiscordOptRetriever(config)
    verbosity_level = opt_retriever.retrieve_verbosity_level()
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    stat_count_map = retrieve_stat_count_map(reporter)

    stash_md_report_color = (
        config.option.md_report_color if hasattr(config.option, "md_report_color") else None
    )
    stash_md_report_zeros = (
        config.option.md_report_zeros if hasattr(config.option, "md_report_zeros") else None
    )

    if not hasattr(config.option, "md_report_verbose"):
        config.option.md_report_verbose = max(0, verbosity_level - 1)
    if not hasattr(config.option, "md_report_margin"):
        config.option.md_report_margin = 1

    try:
        config.option.md_report_color = ColorPoicy.NEVER
        config.option.md_report_zeros = ZerosRender.EMPTY

        return make_md_report(config, reporter, stat_count_map)
    finally:
        config.option.md_report_color = stash_md_report_color
        config.option.md_report_zeros = stash_md_report_zeros


logs = []


def pytest_unconfigure(config):
    opt_retriever = DiscordOptRetriever(config)
    url = opt_retriever.retrieve_webhook_url()
    if not url:
        return

    verbosity_level = opt_retriever.retrieve_verbosity_level()
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    md_report = make_mdreport(config)

    try:
        duration = time.time() - reporter._sessionstarttime
    except AttributeError:
        return

    message, stat_count_map = _make_results_message(reporter)

    if sum([stat_count_map[name] for name in ["failed", "error"]]):
        avatar_url = opt_retriever.retrieve_fail_icon()
        colour = Colour.red()
    elif (
        sum([stat_count_map[name] for name in ("skipped", "xfailed", "xpassed")])
        and stat_count_map["passed"] == 0
    ):
        avatar_url = opt_retriever.retrieve_skip_icon()
        colour = Colour.gold()
    else:
        avatar_url = opt_retriever.retrieve_success_icon()
        colour = Colour.green()

    if verbosity_level >= 1:
        description = _decorate_code_block(lang="md", text="# test results\n{}".format(md_report))
    else:
        description = "{} in {:.1f} seconds".format(message, duration)

    header = "test summary info: {} tests".format(sum(stat_count_map.values()))
    embeds = []  # type: List[Embed]
    embed_summary = Embed(description=description, colour=colour)
    embed_summary.set_footer(
        text="start at {}".format(
            datetime.fromtimestamp(reporter._sessionstarttime).strftime("%d. %b %H:%M:%S%z")
        )
    )
    embeds.append(embed_summary)

    if verbosity_level >= 1:
        embeds.append(Embed(description=_concat_longrepr(reporter), colour=colour))

    attach_file = None

    if opt_retriever.retrieve_attach_file():
        attach_file = File(
            io.BytesIO(
                "# {}\n{}\n\n{}".format(header, md_report, _concat_longrepr(reporter)).encode(
                    "utf8"
                )
            ),
            datetime.fromtimestamp(reporter._sessionstarttime).strftime(
                "pytest_%Y-%m-%dT%H:%M:%S.md"
            ),
        )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        _send_message(
            reporter=reporter,
            url=url,
            header=header,
            username=opt_retriever.retrieve_username(),
            avatar_url=avatar_url,
            embeds=embeds,
            attach_file=attach_file,
        )
    )


async def _send_message(
    reporter: TerminalReporter,
    url: str,
    header: str,
    username: Optional[str],
    avatar_url: Optional[str],
    embeds: Sequence[Embed],
    attach_file: Optional[File] = None,
) -> None:
    async with aiohttp.ClientSession() as session:
        try:
            webhook = Webhook.from_url(url, adapter=AsyncWebhookAdapter(session))
        except (InvalidArgument, HTTPException, NotFound, Forbidden) as e:
            reporter.write_line("pytest-discord error: {}".format(str(e)))
            return

        await webhook.send(
            header, username=username, avatar_url=avatar_url, embeds=embeds, file=attach_file,
        )


@pytest.hookimpl()  # after _pytest.runner
def pytest_report_teststatus(report):
    if report.longreprtext:
        logs.append(report.longreprtext)
    if report.capstdout:
        logs.append(report.capstdout)
    if report.capstderr:
        logs.append(report.capstderr)
