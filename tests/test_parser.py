"""The grammar matrix from the project plan (§9) plus the edges it implies."""

from decimal import Decimal

import pytest

from garslopcli import CLI, HelpRequested, UsageError, VersionRequested

FLAGSHIP = (True, True, "cInput", "longFlagInput")


@pytest.mark.parametrize(
    "argv",
    [
        ["doThing", "-abc", "cInput", "--long-flag", "longFlagInput"],
        ["doThing", "-abccInput", "--long-flag=longFlagInput"],
        ["doThing", "-c", "cInput", "-a", "-b", "--long-flag", "longFlagInput"],
        ["doThing", "--long-flag", "longFlagInput", "-abc", "cInput"],
        ["--verbose", "doThing", "-abc", "cInput", "--long-flag", "longFlagInput"],
    ],
)
def test_flagship_equivalents(cli, argv):
    ns = cli.parse(argv)
    assert (ns.a_all, ns.b_all, ns.c_var, ns.long_flag) == FLAGSHIP
    assert ns.command == "doThing"
    assert ns.positionals == ()
    assert ns.prog == "file.py"


def test_cluster_value_is_the_token_remainder(cli):
    """`-abccInput` is the remainder spelling of `-abc cInput`; `-abcInput` is not."""
    assert cli.parse(["doThing", "-abccInput"]).c_var == "cInput"
    assert cli.parse(["doThing", "-abcInput"]).c_var == "Input"
    assert cli.parse(["doThing", "-cInput"]).c_var == "Input"


def test_globals_after_the_command(cli):
    assert cli.parse(["doThing", "--verbose"]).verbose is True


def test_string_values_are_verbatim(cli):
    assert cli.parse(["doThing", "--long-flag", "-x"]).long_flag == "-x"
    assert cli.parse(["doThing", "-c", "--weird"]).c_var == "--weird"
    assert cli.parse(["doThing", "--long-flag="]).long_flag == ""


def test_number_coercions(cli):
    assert cli.parse(["doThing", "--count", "-5"]).count == -5
    assert cli.parse(["doThing", "--count", "7"]).count == 7
    assert isinstance(cli.parse(["doThing", "--count", "7"]).count, int)
    assert cli.parse(["doThing", "--count", "1e3"]).count == 1000.0
    assert isinstance(cli.parse(["doThing", "--count", "1e3"]).count, float)


def test_boolean_inline_values(cli):
    assert cli.parse(["doThing", "--verbose=false"]).verbose is False
    assert cli.parse(["doThing", "--verbose=Yes"]).verbose is True
    assert cli.parse(["doThing", "--verbose"]).verbose is True


def test_bool_never_consumes_the_next_token(cli):
    ns = cli.parse(["doThing", "--verbose", "false"])
    assert ns.verbose is True
    assert ns.positionals == ("false",)


def test_end_of_options(cli):
    ns = cli.parse(["doThing", "--", "-a", "-b"])
    assert ns.positionals == ("-a", "-b")
    assert ns.a_all is False


def test_single_dash_is_positional(cli):
    assert cli.parse(["doThing", "-"]).positionals == ("-",)


def test_leftover_tokens_are_positionals(cli):
    assert cli.parse(["doThing", "one", "two"]).positionals == ("one", "two")


def test_defaults(cli):
    ns = cli.parse(["doThing"])
    assert ns.a_all is False
    assert ns.b_all is False
    assert ns.c_var is None
    assert ns.long_flag is None
    assert ns.count is None
    assert ns.verbose is False


def test_declared_default(cli):
    cli.add_long_flag("output", "string", "out", default="stdout")
    assert cli.parse(["doThing"]).out == "stdout"
    assert cli.parse(["doThing", "--output", "-"]).out == "-"


def test_multiple_accumulates(cli):
    cli.add_long_flag("tag", "string", "tags", multiple=True)
    assert cli.parse(["doThing"]).tags == []
    assert cli.parse(["doThing", "--tag", "a", "--tag", "b"]).tags == ["a", "b"]


def test_last_occurrence_wins(cli):
    assert cli.parse(["doThing", "-c", "a", "-c", "b"]).c_var == "b"


def test_required_flag(cli):
    cli.add_long_flag("input", "string", "input_path", required=True)
    with pytest.raises(UsageError, match="missing required flag '--input'"):
        cli.parse(["doThing"])
    assert cli.parse(["doThing", "--input", "f"]).input_path == "f"


def test_aliases_share_one_flag(cli):
    cli.add_flag("-n", "--count2", type="number", variable="n", aliases=("--total",))
    assert cli.parse(["doThing", "-n", "3"]).n == 3
    assert cli.parse(["doThing", "--total=4"]).n == 4


def test_callable_and_strict_number_types():
    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: None)
    cli.add_long_flag("amount", Decimal, "amount")
    cli.add_long_flag("strict", int, "strict")
    assert cli.parse(["go", "--amount", "1.5"]).amount == Decimal("1.5")
    assert cli.parse(["go", "--strict", "3"]).strict == 3
    with pytest.raises(UsageError, match="invalid value for '--amount': 'abc'"):
        cli.parse(["go", "--amount", "abc"])
    with pytest.raises(UsageError, match=r"invalid number for '--strict': '3\.14'"):
        cli.parse(["go", "--strict", "3.14"])


def test_namespace_access(cli):
    ns = cli.parse(["doThing", "-a"])
    assert ns.as_dict() == ns.as_dict()
    assert ns.as_dict()["a_all"] is True
    assert "a_all" in repr(ns)
    with pytest.raises(AttributeError, match="not a registered flag variable"):
        ns.nope  # noqa: B018 - the attribute access itself is what must raise


def test_command_flag_used_before_the_command():
    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: None).add_long_flag("path", "string", "path")
    with pytest.raises(UsageError, match="belongs to command 'go' and must follow it"):
        cli.parse(["--path", "x", "go"])
    assert cli.parse(["go", "--path", "x"]).path == "x"


def test_command_flag_used_in_the_wrong_command():
    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: None).add_long_flag("path", "string", "path")
    cli.add_command("other", lambda ns: None)
    with pytest.raises(UsageError, match="belongs to command 'go', not 'other'"):
        cli.parse(["other", "--path", "x"])


def test_builtin_help_and_version_requests(cli):
    with pytest.raises(HelpRequested):
        cli.parse(["--help"])
    with pytest.raises(HelpRequested):
        cli.parse(["doThing", "-h"])
    with pytest.raises(HelpRequested):
        cli.parse(["doThing", "--help"])
    with pytest.raises(VersionRequested):
        cli.parse(["doThing", "--version"])


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["doThing", "-ab", '-c="v"'], r"short flag '-c' does not take '='"),
        (["doThing", "-a=true"], r"cannot assign a value to short bool flag '-a'"),
        (["doThing", "-abc", "--long-flag", "x"], r"flag '-c' requires a value"),
        (["doThing", "-abc"], r"flag '-c' requires a value"),
        (["doThing", "-az", "cInput"], r"unknown flag '-z' \(in '-az'\)"),
        (["doThing", "--count", "abc"], "invalid number for '--count': 'abc'"),
        (["doThing", "--verbose=maybe"], "invalid boolean for '--verbose': 'maybe'"),
        (["dothing"], "unknown command 'dothing'"),
        ([], "no command given"),
        (["doThing", "--lng-flag", "x"], "unknown flag '--lng-flag'"),
        (["doThing", "--long-flag"], "flag '--long-flag' requires a value"),
        (["doThing", "--long-flag", "--verbose"], "flag '--long-flag' requires a value"),
        (["doThing", "-5"], "unknown flag '-5'"),
    ],
)
def test_usage_errors(cli, argv, message):
    with pytest.raises(UsageError, match=message):
        cli.parse(argv)


def test_error_messages_name_the_near_miss(cli):
    with pytest.raises(UsageError, match=r"did you mean 'doThing'\?"):
        cli.parse(["dothing"])
    with pytest.raises(UsageError, match=r"did you mean '--long-flag'\?"):
        cli.parse(["doThing", "--long-flg", "x"])


def test_error_scope_tracks_the_command(cli):
    with pytest.raises(UsageError) as excinfo:
        cli.parse(["doThing", "--nope"])
    assert excinfo.value.command == "doThing"
    with pytest.raises(UsageError) as excinfo:
        cli.parse(["--nope", "doThing"])
    assert excinfo.value.command is None
