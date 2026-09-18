"""Shared fixtures: the flagship example CLI from the project plan."""

import pytest

from garslopcli import CLI


def make_cli() -> CLI:
    """``file.py``-style CLI: a/b bools, c string, --long-flag string, --count, --verbose."""
    cli = CLI(prog="file.py", description="Example CLI")
    cli.add_command("doThing", lambda ns: None, help="Does the thing")
    cli.add_short_flag("a", "bool", "a_all")
    cli.add_short_flag("b", "bool", "b_all")
    cli.add_short_flag("c", "string", "c_var")
    cli.add_long_flag("long-flag", "string", "long_flag")
    cli.add_long_flag("count", "number", "count")
    cli.add_long_flag("verbose", "bool", "verbose")
    return cli


@pytest.fixture
def cli() -> CLI:
    return make_cli()
