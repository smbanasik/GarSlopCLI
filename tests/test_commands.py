"""Command dispatch, scoping, aliases, and the handler call convention."""

import pytest
from conftest import make_cli

from garslopcli import CLI, UsageError


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


def test_command_scope_object_exposes_its_spec():
    cli = CLI(prog="x")

    def handler(ns):
        return None

    command = cli.add_command("go", handler, help="Go somewhere", aliases=("g",))
    assert (command.name, command.help, command.aliases, command.fn) == (
        "go",
        "Go somewhere",
        ("g",),
        handler,
    )
    assert repr(command) == "<Command 'go'>"
    assert command.add_flag("-n", "--count", type="number", variable="count").kind == "number"


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


def test_end_of_options_before_the_command_name():
    """`-- doThing -a` takes the next token as the command literally, then parses flags."""
    cli = CLI(prog="x")
    cli.add_command("doThing", lambda ns: None)
    cli.add_short_flag("a", "bool", "a_all")
    ns = cli.parse(["--", "doThing", "-a"])
    assert ns.command == "doThing"
    assert ns.a_all is True


def test_end_of_options_before_an_unknown_command():
    cli = CLI(prog="x")
    cli.add_command("doThing", lambda ns: None)
    with pytest.raises(UsageError, match="unknown command '--weird'"):
        cli.parse(["--", "--weird"])


def test_parse_is_usable_without_the_cli_facade():
    """The pure core takes flag/command specs directly; duplicates are caught defensively."""
    from garslopcli.errors import RegistrationError
    from garslopcli.model import CommandSpec, FlagSpec
    from garslopcli.parser import parse
    from garslopcli.types import BOOL

    go = CommandSpec(name="go", fn=lambda ns: None)
    go.flags.append(FlagSpec(names=("-a",), variable="a_all", kind=BOOL, coerce=None))
    ns = parse(["go", "-a"], prog="x", commands={"go": go}, aliases={})
    assert ns.a_all is True

    go.flags.append(FlagSpec(names=("-a",), variable="other", kind=BOOL, coerce=None))
    with pytest.raises(RegistrationError, match="flag name '-a' is declared twice"):
        parse(["go"], prog="x", commands={"go": go}, aliases={})


def test_custom_validator_errors_are_reported_verbatim():
    def positive(token):
        value = int(token)
        if value <= 0:
            raise RuntimeError("must be positive")
        return value

    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: None)
    cli.add_long_flag("n", positive, "n")
    assert cli.parse(["go", "--n", "2"]).n == 2
    with pytest.raises(UsageError, match=r"invalid value for '--n': '-1' \(must be positive\)"):
        cli.parse(["go", "--n", "-1"])


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
