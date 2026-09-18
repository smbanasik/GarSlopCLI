"""Registration API contract: kinds, name normalization, and fail-fast validation."""

import pytest

from garsloppycli import CLI, RegistrationError


def test_kind_resolution():
    cli = CLI(prog="x")
    assert cli.add_short_flag("a", "bool", "v1").kind == "bool"
    assert cli.add_short_flag("b", "string", "v2").kind == "string"
    assert cli.add_short_flag("c", "number", "v3").kind == "number"
    assert cli.add_short_flag("d", bool, "v4").kind == "bool"
    assert cli.add_short_flag("e", str, "v5").kind == "string"
    assert cli.add_short_flag("f", float, "v6").kind == "number"
    assert cli.add_short_flag("g", lambda token: token.upper(), "v7").kind == "custom"
    assert cli.add_short_flag("i", "NUMBER", "v8").kind == "number"


@pytest.mark.parametrize("bad", ["integer", "int", 42, None, object()])
def test_unknown_kind_fails_at_registration(bad):
    cli = CLI(prog="x")
    with pytest.raises(TypeError, match="unknown flag type"):
        cli.add_short_flag("a", bad, "value")


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        ("a", ("-a",)),
        ("-a", ("-a",)),
        ("long-flag", ("--long-flag",)),
        ("--long-flag", ("--long-flag",)),
    ],
)
def test_name_normalization(declared, expected):
    cli = CLI(prog="x")
    assert cli.add_flag(declared, type="string", variable="v").names == expected


def test_explicit_helpers_force_their_shape():
    """add_short_flag/add_long_flag must not quietly produce the other shape."""
    cli = CLI(prog="x")
    assert cli.add_long_flag("count", "number", "n1").names == ("--count",)
    assert cli.add_long_flag("n", "number", "n2").names == ("--n",)
    assert cli.add_long_flag("--other", "number", "n3").names == ("--other",)
    assert cli.add_short_flag("x", "bool", "b1").names == ("-x",)
    with pytest.raises(RegistrationError, match="short flags are a single alphanumeric"):
        cli.add_short_flag("long-flag", "bool", "b2")


def test_paired_names_and_aliases():
    cli = CLI(prog="x")
    spec = cli.add_flag("-n", "--count", type="number", variable="n", aliases=("--total",))
    assert spec.names == ("-n", "--count", "--total")
    assert spec.display == "-n, --count, --total NUMBER"
    assert spec.takes_value


def test_bool_display_has_no_placeholder():
    cli = CLI(prog="x")
    spec = cli.add_short_flag("a", "bool", "a_all")
    assert spec.display == "-a"
    assert not spec.takes_value


def test_metavar_override():
    cli = CLI(prog="x")
    spec = cli.add_long_flag("output", "string", "out", metavar="FILE")
    assert spec.display == "--output FILE"


@pytest.mark.parametrize("bad", ["-ab", "--", "-", "--with=equals", "-1a"])
def test_invalid_flag_names(bad):
    cli = CLI(prog="x")
    with pytest.raises(RegistrationError, match=r"invalid (short|long) flag name"):
        cli.add_flag(bad, type="bool", variable="v")


def test_empty_flag_name():
    cli = CLI(prog="x")
    with pytest.raises(RegistrationError, match="flag name must not be empty"):
        cli.add_flag("", type="bool", variable="v")


def test_flag_needs_a_name():
    cli = CLI(prog="x")
    with pytest.raises(RegistrationError, match="at least one name"):
        cli.add_flag(type="bool", variable="v")


@pytest.mark.parametrize("reserved", ["-h", "--help", "--version"])
def test_reserved_names_are_rejected(reserved):
    cli = CLI(prog="x")
    with pytest.raises(RegistrationError, match="reserved"):
        cli.add_flag(reserved, type="bool", variable="v")


def test_duplicate_flag_name():
    cli = CLI(prog="x")
    cli.add_short_flag("a", "bool", "a_all")
    with pytest.raises(RegistrationError, match="flag name '-a' is already declared"):
        cli.add_short_flag("a", "string", "other")


def test_duplicate_variable():
    cli = CLI(prog="x")
    cli.add_short_flag("a", "bool", "a_all")
    with pytest.raises(RegistrationError, match="already bound to flag '-a'"):
        cli.add_short_flag("z", "bool", "a_all")


@pytest.mark.parametrize("bad", ["not-an-identifier", "", "with space", 7])
def test_variable_must_be_an_identifier(bad):
    cli = CLI(prog="x")
    with pytest.raises(RegistrationError, match="valid identifier"):
        cli.add_short_flag("a", "bool", bad)


def test_cross_scope_conflicts():
    cli = CLI(prog="x")
    command = cli.add_command("go", lambda ns: None)
    cli.add_short_flag("a", "bool", "a_all")
    with pytest.raises(RegistrationError, match="already declared"):
        command.add_short_flag("a", "bool", "cmd_a")
    with pytest.raises(RegistrationError, match="already bound"):
        command.add_short_flag("z", "bool", "a_all")


def test_required_with_default_is_rejected():
    cli = CLI(prog="x")
    with pytest.raises(RegistrationError, match="cannot be both required and have a default"):
        cli.add_long_flag("input", "string", "i", required=True, default="x")


def test_command_validation():
    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: None, aliases=("g",))
    with pytest.raises(RegistrationError, match="invalid command name"):
        cli.add_command("-go", lambda ns: None)
    with pytest.raises(RegistrationError, match="invalid command alias"):
        cli.add_command("other", lambda ns: None, aliases=("-g",))
    with pytest.raises(RegistrationError, match="already registered"):
        cli.add_command("go", lambda ns: None)
    with pytest.raises(RegistrationError, match="already registered"):
        cli.add_command("other", lambda ns: None, aliases=("g",))
    with pytest.raises(RegistrationError, match="not callable"):
        cli.add_command("third", "not a function")


def test_set_default_command_validation():
    cli = CLI(prog="x")
    with pytest.raises(RegistrationError, match="unknown command 'nope'"):
        cli.set_default_command("nope")
