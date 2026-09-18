"""Exceptions and process exit codes.

Two error families:

* :class:`RegistrationError` — the *programmer* declared something the parser
  cannot represent (duplicate flag, bad kind, reserved name). Raised at
  registration time so mistakes surface at import, not at parse time.
* :class:`UsageError` — the *user* typed something the parser cannot
  understand. ``CLI.run`` prints it and exits with :data:`EXIT_USAGE`.
"""

EXIT_OK = 0
EXIT_USAGE = 2


class GarSlopCLIError(Exception):
    """Base class for every error raised by this library."""


class RegistrationError(GarSlopCLIError):
    """A command or flag was declared in a way the parser cannot represent."""


class UsageError(GarSlopCLIError):
    """The command line could not be understood.

    ``command`` carries the resolved command name when the error happened after
    the command was known, so the CLI can print a scope-correct help hint.
    """

    def __init__(self, message: str, *, command: str | None = None) -> None:
        super().__init__(message)
        self.command = command


class HelpRequested(GarSlopCLIError):
    """``-h`` / ``--help`` was used. Not an error — control flow for ``run``."""

    def __init__(self, command: str | None = None) -> None:
        super().__init__("help requested")
        self.command = command


class VersionRequested(GarSlopCLIError):
    """``--version`` was used. Not an error — control flow for ``run``."""
