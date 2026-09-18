"""Command dispatch, scoping, aliases, and the handler call convention."""

import pytest
from conftest import make_cli

from garsloppycli import CLI, UsageError


def test_run_dispatches_and_returns_the_handler_value():
    cli = CLI(prog="x")
    seen = {}

    def handler(ns):
        seen["count"] = ns.count
        return 7

    cli.add_command("go", handler)
    cli.add_short_flag("c", "number", "count")
    assert cli.run(["go", "-c", "3"]) == 7
    assert seen == {"count": 3}


def test_zero_argument_handler_is_called_without_arguments():
    cli = CLI(prog="x")
    calls = []
    cli.add_command("go", lambda: calls.append("called"))
    assert cli.run(["go"]) is None
    assert calls == ["called"]


def test_command_decorator_returns_the_function():
    cli = CLI(prog="x")

    @cli.command("doThing", help="Does the thing", aliases=("dt",))
    def do_thing(ns):
        return "ok"

    assert do_thing(None) == "ok"  # still a plain function
    assert cli.run(["dt"]) == "ok"


def test_alias_resolves_to_the_canonical_name():
    cli = CLI(prog="x")
    cli.add_command("doThing", lambda ns: None, aliases=("dt", "dthing"))
    assert cli.parse(["dt"]).command == "doThing"
    assert cli.parse(["dthing"]).command == "doThing"


def test_default_command():
    cli = CLI(prog="x")
    cli.add_command("doThing", lambda ns: None)
    cli.set_default_command("doThing")
    cli.add_short_flag("a", "bool", "a_all")
    ns = cli.parse(["-a"])
    assert ns.command == "doThing"
    assert ns.a_all is True
    assert cli.run(["-a"]) is None


def test_command_scoped_flags():
    cli = CLI(prog="x")
    command = cli.add_command("go", lambda ns: None)
    command.add_long_flag("path", "string", "path")
    command.add_flag("-q", "--quiet", type="bool", variable="quiet")
    ns = cli.parse(["go", "--path", "p", "-q"])
    assert (ns.path, ns.quiet) == ("p", True)


def test_command_flags_do_not_leak_between_commands():
    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: None).add_long_flag("path", "string", "path")
    cli.add_command("other", lambda ns: None)

    with pytest.raises(UsageError, match="belongs to command 'go', not 'other'"):
        cli.parse(["other", "--path", "p"])


def test_global_flags_are_visible_in_every_command():
    cli = make_cli()
    cli.add_command("other", lambda ns: None)
    assert cli.parse(["other", "--verbose"]).verbose is True


def test_handler_type_error_is_not_swallowed():
    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        cli.run(["go"])
