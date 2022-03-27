import asyncio
import io
import os
import platform
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import aiohttp
import pytest
from _pytest.config import Config
from _pytest.terminal import TerminalReporter
from discord import AsyncWebhookAdapter, Colour, Embed, File, Webhook
from discord.errors import Forbidden, HTTPException, InvalidArgument, NotFound
from pytest_md_report.plugin import extract_pytest_stats

from ._const import HelpMsg, Option, TestResultType
from ._opt_retriever import DiscordOptRetriever


MAX_EMBED_LEN = 2048
MAX_EMBEDS_LEN = 6000
MAX_EMBED_CT = 10


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
        Option.DISCORD_WEBHOOK.inioption_str,
        default=None,
        help=Option.DISCORD_WEBHOOK.help_msg,
    )
    parser.addini(
        Option.DISCORD_VERBOSE.inioption_str,
        default=None,
        help=Option.DISCORD_VERBOSE.help_msg,
    )
    parser.addini(
        Option.DISCORD_USERNAME.inioption_str,
        default=None,
        help=Option.DISCORD_USERNAME.help_msg,
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
            messages.append(f"{count} {_normalize_stat_name(name)}")

    return (", ".join(messages), stat_count_map)


def _decorate_code_block(lang: str, text: str) -> str:
    return f"```{lang}\n{text}\n```\n"


def _extract_longrepr(reporter: TerminalReporter) -> List[str]:
    messages = []

    for stat_key, values in reporter.stats.items():
        if not stat_key or stat_key not in ["failed", "error"]:
            continue

        for i, value in enumerate(values):
            try:
                if value.longrepr:
                    messages.append(
                        "# {}: #{}\n{}".format(
                            stat_key, i + 1, _decorate_code_block(lang="py", text=value.longrepr)
                        )
                    )
            except AttributeError:
                pass

    return messages


def _extract_longrepr_embeds(
    reporter: TerminalReporter, embed_len: int, colour: Colour
) -> Tuple[List[Embed], bool]:
    embeds = []
    total_embed_len = embed_len
    exceeds_embeds_limit = False

    for stat_key, values in reporter.stats.items():
        if not stat_key or stat_key not in ["failed", "error"]:
            continue

        for i, value in enumerate(values):
            try:
                if not value.longrepr:
                    continue
            except AttributeError:
                continue

            lines_len = 0
            lines: List[str] = []
            for line in reversed(str(value.longrepr).splitlines()):
                if (lines_len + len(line)) > (MAX_EMBED_LEN - 64):
                    break

                lines.insert(0, line)
                lines_len += len(line) + 1

            embed = Embed(
                description="# {}: #{}\n{}".format(
                    stat_key, i + 1, _decorate_code_block(lang="py", text="\n".join(lines))
                ),
                colour=colour,
            )

            if (total_embed_len + len(embed.description)) > (MAX_EMBEDS_LEN - 128):
                embeds.append(
                    Embed(description=f"and other {len(values) - i} failed", colour=colour)
                )
                exceeds_embeds_limit = True
                break

            total_embed_len += len(embed.description)
            embeds.append(embed)

            if len(embeds) >= MAX_EMBED_CT:
                break

    return embeds, exceeds_embeds_limit


def _is_ci() -> bool:
    CI = os.environ.get("CI")
    if not CI:
        return False

    return CI.strip().lower() == "true"


def _make_md_report(config: Config) -> str:
    from pytest_md_report import ColorPolicy, ZerosRender, make_md_report, retrieve_stat_count_map

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
        config.option.md_report_color = ColorPolicy.NEVER
        config.option.md_report_zeros = ZerosRender.EMPTY

        return make_md_report(config, reporter, stat_count_map)
    finally:
        config.option.md_report_color = stash_md_report_color
        config.option.md_report_zeros = stash_md_report_zeros


def _make_header(tests: int) -> str:
    msgs = [f"{tests} tests"]

    if _is_ci():
        msgs.append("executed by CI")

        if os.environ.get("GITHUB_ACTION"):
            repo = os.environ.get("GITHUB_REPOSITORY")
            workflow = os.environ.get("GITHUB_WORKFLOW")
            msgs.append(f"({repo} {workflow})")

    return "test summary info: {}: {} Python {}".format(
        " ".join(msgs), platform.system(), ".".join(platform.python_version_tuple())
    )


def _make_summary_footer(reporter: TerminalReporter, verbosity_level: int) -> str:
    import platform

    msgs = []

    if verbosity_level >= 1:
        msgs.append(
            "start at {}".format(
                datetime.fromtimestamp(reporter._sessionstarttime).strftime("%d. %b %H:%M:%S%z")
            )
        )

        uname = platform.uname()
        host_info = f"{uname.system} {uname.node} {uname.release} {uname.machine}"
        python_info = f"{platform.python_implementation()} {platform.python_version()}"
        msgs.extend([host_info, python_info])

    return ",  ".join(msgs)


_logs = []


def extract_result_type(pytest_stats: Mapping[str, int]) -> TestResultType:
    if sum(pytest_stats[name] for name in ("failed", "error")):
        return TestResultType.FAIL

    if (
        sum(pytest_stats[name] for name in ("skipped", "xfailed", "xpassed"))
        and pytest_stats["passed"] == 0
    ):
        return TestResultType.SKIP

    return TestResultType.SUCCESS


_result_type_to_colour = {
    TestResultType.SUCCESS: Colour.green(),
    TestResultType.SKIP: Colour.gold(),
    TestResultType.FAIL: Colour.red(),
}


def pytest_unconfigure(config):
    if config.option.help:
        return

    opt_retriever = DiscordOptRetriever(config)
    url = opt_retriever.retrieve_webhook_url()
    if not url:
        return

    verbosity_level = opt_retriever.retrieve_verbosity_level()
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    md_report = _make_md_report(config)

    try:
        duration = time.time() - reporter._sessionstarttime
    except AttributeError:
        return

    message, stat_count_map = _make_results_message(reporter)

    if sum(stat_count_map[name] for name in ["failed", "error"]):
        avatar_url = opt_retriever.retrieve_fail_icon()
        colour = Colour.red()
    elif (
        sum(stat_count_map[name] for name in ("skipped", "xfailed", "xpassed"))
        and stat_count_map["passed"] == 0
    ):
        avatar_url = opt_retriever.retrieve_skip_icon()
        colour = Colour.gold()
    else:
        avatar_url = opt_retriever.retrieve_success_icon()
        colour = Colour.green()

    embeds: List[Embed] = []
    embeds_len_ct = 0
    exceeds_embeds_limit = False

    embed_summary = Embed(description=f"{message} in {duration:.1f} seconds", colour=colour)
    embed_summary.set_footer(text=_make_summary_footer(reporter, verbosity_level))
    embeds.append(embed_summary)
    embeds_len_ct += len(embed_summary.description) + len(embed_summary.footer)

    if verbosity_level >= 1:
        pytest_stats = extract_pytest_stats(
            reporter=reporter,
            outcomes=["passed", "failed", "error", "skipped", "xfailed", "xpassed"],
            verbosity_level=max(0, verbosity_level - 1),
        )
        result_lines_map = defaultdict(list)

        for key, stats in pytest_stats.items():
            result_lines_map[extract_result_type(stats)].append(
                "`{}`: {}".format(
                    ":".join(key),
                    ", ".join([f"`{ct}` {outcome}" for outcome, ct in stats.items() if ct > 0]),
                )
            )

        for result_type, result_lines in result_lines_map.items():
            embed = Embed(
                description="\n".join(result_lines)[:MAX_EMBED_LEN],
                colour=_result_type_to_colour[result_type],
            )
            embeds.append(embed)
            embeds_len_ct += len(embed.description)

        _embeds, exceeds_embeds_limit = _extract_longrepr_embeds(
            reporter, embeds_len_ct, colour=colour
        )
        embeds.extend(_embeds)

    header = _make_header(sum(stat_count_map.values()))
    attach_file = None

    if opt_retriever.retrieve_attach_file() or exceeds_embeds_limit:
        attach_file = File(
            io.BytesIO(
                "# {}\n{}\n\n{}".format(
                    header, md_report, "\n\n".join(_extract_longrepr(reporter))
                ).encode("utf8")
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
            reporter.write_line(f"pytest-discord error: {str(e)}")
            return

        await webhook.send(
            header, username=username, avatar_url=avatar_url, embeds=embeds, file=attach_file
        )


@pytest.hookimpl()
def pytest_report_teststatus(report):
    if report.longreprtext:
        _logs.append(report.longreprtext)
    if report.capstdout:
        _logs.append(report.capstdout)
    if report.capstderr:
        _logs.append(report.capstderr)
