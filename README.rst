.. contents:: **pytest-discord**
   :backlinks: top
   :depth: 2


Summary
============================================
.. image:: https://badge.fury.io/py/pytest-discord.svg
    :target: https://badge.fury.io/py/pytest-discord
    :alt: PyPI package version

.. image:: https://img.shields.io/pypi/pyversions/pytest-discord.svg
    :target: https://pypi.org/project/pytest-discord
    :alt: Supported Python versions

.. image:: https://img.shields.io/pypi/implementation/pytest-discord.svg
    :target: https://pypi.org/project/pytest-discord
    :alt: Supported Python implementations

.. image:: https://img.shields.io/travis/thombashi/pytest-discord/master.svg?label=Linux/macOS%20CI
    :target: https://travis-ci.org/thombashi/pytest-discord
    :alt: Linux/macOS CI status

.. image:: https://img.shields.io/appveyor/ci/thombashi/pytest-discord/master.svg?label=Windows%20CI
    :target: https://ci.appveyor.com/project/thombashi/pytest-discord/branch/master
    :alt: Windows CI status

A pytest plugin to report test results to a discord channel.


Installation
============================================
::

    pip install pytest-discord


Usage
============================================
::

    $ pytest --discord-webhook=<https://discordapp.com/api/webhooks/...>

Or 

::

    $ export PYTEST_DISCORD_WEBHOOK=<https://discordapp.com/api/webhooks/...>
    $ pytest

Or, you can specify webhook URL of a discord channel via a config file.


Increse the verbosity level
--------------------------------------------
::

    $ pytest --discord-verbose=1


Options
============================================

Command options
--------------------------------------------
::

    notify test results to a discord channel:
      --discord-webhook=WEBHOOK_URL
                            discord webhook url of a discord channel to notify
                            pytest results. you can also specify the value with
                            PYTEST_DISCORD_WEBHOOK environment variable.
      --discord-verbose=VERBOSITY_LEVEL
                            verbosity level for pytest-discord. if not set, using
                            verbosity level of pytest.
                            defaults to 0.
                            you can also specify the value with
                            PYTEST_DISCORD_VERBOSE environment variable.
      --discord-username=DISCORD_USERNAME
                            name for a message. defaults to pytest-discord. you can
                            also specify the value with PYTEST_DISCORD_USERNAME
                            environment variable.
      --discord-success-icon=ICON_URL
                            url to an icon of a successful run. you can also specify
                            the value with PYTEST_DISCORD_SUCCESS_ICON environment
                            variable.
      --discord-skip-icon=ICON_URL
                            url to an icon of a skipped run. you can also specify
                            the value with PYTEST_DISCORD_SKIP_ICON environment
                            variable.
      --discord-fail-icon=ICON_URL
                            url to an icon of a failed run. you can also specify the
                            value with PYTEST_DISCORD_FAIL_ICON environment
                            variable.
      --discord-attach-file
                            post pytest results as a markdown file to a discord
                            channel. you can also specify the value with
                            PYTEST_DISCORD_ATTACH_FILE environment variable.


ini-options
--------------------------------------------
[pytest] ini-options in the first ``pytest.ini``/``tox.ini``/``setup.cfg``/``pyproject.toml (pytest 6.0.0 or later)`` file found:

::

  discord_webhook (string):
                        discord webhook url of a discord channel to notify
                        pytest results.
  discord_verbose (string):
                        verbosity level for pytest-discord. if not set, using
                        verbosity level of pytest. defaults to 0.
  discord_username (string):
                        name for a message. defaults to pytest-discord.
  discord_success_icon (string):
                        url to an icon of a successful run.
  discord_skip_icon (string):
                        url to an icon of a skipped run.
  discord_fail_icon (string):
                        url to an icon of a failed run.
  discord_attach_file (bool):
                        post pytest results as a markdown file to a discord
                        channel.

:Example of ``pyproject.toml``:
    .. code-block:: toml

        [tool.pytest.ini_options]
        discord_webhook = "https://discordapp.com/api/webhooks/..."
        md_report_verbose = 1

:Example of ``setup.cfg``:
    .. code-block:: ini

        [tool:pytest]
        discord_webhook = https://discordapp.com/api/webhooks/...
        md_report_verbose = 1


Dependencies
============================================
- Python 3.5+
- `Python package dependencies (automatically installed) <https://github.com/thombashi/pytest-discord/network/dependencies>`__
