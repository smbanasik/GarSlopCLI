"""Generated help text and the process behavior of ``run`` (exit codes, streams)."""

import pytest

from garslopcli import CLI, RegistrationError


def test_render_global_help(cli):
    text = cli.render_help()
    assert text.startswith("file.py: Example CLI")
    assert "Usage: file.py <command> [options]" in text
    assert "Commands:" in text
    assert "doThing" in text
    assert "Does the thing" in text
    assert "Options:" in text
    assert "-c VALUE" in text
    assert "--long-flag VALUE" in text
    assert "--count NUMBER" in text
    assert "(bool)" in text  # undocumented flags fall back to their kind
    assert "-h, --help" in text
    assert "--version" in text


def test_render_command_help(cli):
    text = cli.render_help("doThing")
    assert "Usage: file.py doThing [options]" in text
    assert "Commands:" not in text
    assert "--long-flag VALUE" in text  # globals still apply after the command


def test_help_output_is_ascii_for_legacy_consoles(cli):
    """Help must print on cp437/cp1252 consoles, where non-ASCII raises UnicodeEncodeError."""
    assert cli.render_help().isascii()
    assert cli.render_help("doThing").isascii()


def test_render_help_without_commands():
    cli = CLI(prog="x", description="Flags only")
    cli.add_short_flag("v", "bool", "verbose")
    text = cli.render_help()
    assert "Usage: x [options]" in text
    assert "Commands:" not in text


def test_render_help_unknown_command():
    with pytest.raises(RegistrationError, match="unknown command"):
        CLI(prog="x").render_help("nope")


def test_run_help_exits_zero_on_stdout(cli, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.run(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "Usage: file.py <command> [options]" in captured.out
    assert captured.err == ""


def test_run_command_help_exits_zero(cli, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.run(["doThing", "--help"])
    assert excinfo.value.code == 0
    assert "Usage: file.py doThing [options]" in capsys.readouterr().out


def test_run_version(cli, capsys):
    cli.version = "9.9.9"
    with pytest.raises(SystemExit) as excinfo:
        cli.run(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == "file.py 9.9.9"


def test_run_usage_error_exits_two_on_stderr(cli, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.run(["doThing", "--nope"])
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "file.py: error: unknown flag '--nope'" in captured.err
    assert "Try 'file.py doThing --help'" in captured.err


def test_run_reports_available_commands_when_none_given(cli, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.run([])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "error: no command given" in err
    assert "Available commands: doThing" in err
    assert "Try 'file.py --help'" in err


def test_main_propagates_the_handler_exit_code():
    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: 3)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["go"])
    assert excinfo.value.code == 3


def test_main_exits_zero_when_the_handler_returns_none():
    cli = CLI(prog="x")
    cli.add_command("go", lambda ns: None)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["go"])
    assert excinfo.value.code in (None, 0)  # SystemExit(None) exits with status 0
