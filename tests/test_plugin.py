import re
import sys
from textwrap import dedent
from unittest import mock

import pytest
from discord import Colour


DUMMY_WEBHOOK_URL = "https://discordapp.com/api/webhooks/111111111111111111/abcABC111111111111111111111111111111111111111111111111111111111111-"
SUCCESS_ICON_URL = "https://success.png"
FAILED_ICON_URL = "https://fail.png"

PYCODE_PASS = dedent(
    """\
    import pytest

    def test_pass():
        assert True
    """
)


class AsyncMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


def test_pytest_discord_passed(testdir):
    testdir.makepyfile(PYCODE_PASS)

    with mock.patch("discord.Webhook.send", new_callable=AsyncMock) as mock_send:
        testdir.runpytest("--discord-webhook", DUMMY_WEBHOOK_URL)

        args = mock_send.call_args[1]

        assert not args["avatar_url"]

        embed = args["embeds"][0]
        assert embed.colour == Colour.green()
        assert re.search(r"1 passed in [0-9\.]+ seconds", embed.description)


def test_pytest_discord_skipped(testdir):
    testdir.makepyfile(
        dedent(
            """\
            import pytest

            def test_skip():
                pytest.skip()
            """
        )
    )

    with mock.patch("discord.Webhook.send", new_callable=AsyncMock) as mock_send:
        testdir.runpytest("--discord-webhook", DUMMY_WEBHOOK_URL)

        args = mock_send.call_args[1]

        assert not args["avatar_url"]

        embed = args["embeds"][0]
        assert embed.colour == Colour.gold()
        assert re.search(r"1 skipped in [0-9\.]+ seconds", embed.description)


def test_pytest_discord_failed(testdir):
    testdir.makepyfile(
        dedent(
            """\
            import pytest

            def test_pass():
                assert True

            def test_failed():
                assert False

            def test_skipped():
                pytest.skip()

            def test_error(test):
                pass

            @pytest.mark.xfail()
            def test_xfailed():
                assert False

            @pytest.mark.xfail()
            def test_xpassed():
                assert True
            """
        )
    )

    with mock.patch("discord.Webhook.send", new_callable=AsyncMock) as mock_send:
        testdir.runpytest("--discord-webhook", DUMMY_WEBHOOK_URL)

        args = mock_send.call_args[1]

        print("!!!", args["avatar_url"], file=sys.stderr)
        assert not args["avatar_url"]

        embed = args["embeds"][0]
        assert embed.colour == Colour.red()
        assert re.search(
            r"1 failed, 1 passed, 1 skipped, 1 errors, 1 xfailed, 1 xpassed in [0-9\.]+ seconds",
            embed.description,
        )


@pytest.mark.parametrize(
    ["value", "expected"],
    [
        ("custom username", "custom username"),
        ("", "pytest-discord"),
    ],
)
def test_pytest_discord_username(testdir, value, expected):
    testdir.makepyfile(PYCODE_PASS)

    with mock.patch("discord.Webhook.send", new_callable=AsyncMock) as mock_send:
        testdir.runpytest("--discord-webhook", DUMMY_WEBHOOK_URL, "--discord-username", value)

        args = mock_send.call_args[1]

        assert args["username"] == expected


@pytest.mark.parametrize(
    ["value", "expected"],
    [
        ("True", SUCCESS_ICON_URL),
        ("False", FAILED_ICON_URL),
    ],
)
def test_pytest_discord_avatar_url(testdir, value, expected):
    testdir.makepyfile(
        """
        def test_avatar_url():
            assert {}
        """.format(
            value
        )
    )

    with mock.patch("discord.Webhook.send", new_callable=AsyncMock) as mock_send:
        testdir.runpytest(
            "--discord-webhook",
            DUMMY_WEBHOOK_URL,
            "--discord-success-icon",
            SUCCESS_ICON_URL,
            "--discord-fail-icon",
            FAILED_ICON_URL,
        )

        args = mock_send.call_args[1]

        assert args["avatar_url"] == expected


@pytest.mark.parametrize(
    ["value", "expected"],
    [("invalid-webhook-url", "pytest-discord error: Invalid webhook URL given.")],
)
def test_pytest_discord_invalid_webhoook(testdir, value, expected):
    testdir.makepyfile(PYCODE_PASS)

    result = testdir.runpytest("--discord-webhook", value)
    result.assert_outcomes(passed=1)
    assert result.outlines[-1] == expected
    assert result.errlines == []
