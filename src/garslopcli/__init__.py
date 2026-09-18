"""GarSlopCLI — zero-dependency command and flag parsing for Python CLIs.

::

    from garslopcli import CLI

    cli = CLI(prog="file.py", description="Example CLI")

    @cli.command("doThing", help="Does the thing")
    def do_thing(ns):
        print(ns.c_var)

    cli.add_short_flag("a", "bool", "a_all")
    cli.add_long_flag("long-flag", "string", "long_flag")

    if __name__ == "__main__":
        cli.main()
"""

from .cli import CLI, Command
from .errors import (
    EXIT_OK,
    EXIT_USAGE,
    GarSlopCLIError,
    HelpRequested,
    RegistrationError,
    UsageError,
    VersionRequested,
)
from .model import CommandSpec, FlagSpec, Namespace

__all__ = [
    "CLI",
    "EXIT_OK",
    "EXIT_USAGE",
    "Command",
    "CommandSpec",
    "FlagSpec",
    "GarSlopCLIError",
    "HelpRequested",
    "Namespace",
    "RegistrationError",
    "UsageError",
    "VersionRequested",
]
