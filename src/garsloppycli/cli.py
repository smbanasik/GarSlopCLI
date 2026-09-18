"""The public façade: declaration API, parsing entry points, and process behavior.

::

    cli = CLI(prog="file.py", description="Example CLI")

    @cli.command("doThing", help="Does the thing")
    def do_thing(ns):
        ...

    cli.add_short_flag("a", "bool", "a_all")
    cli.add_long_flag("long-flag", "string", "long_flag")

    if __name__ == "__main__":
        cli.main()

Flag names and variables are unique across the whole CLI (globals and every
command), so a variable name always resolves to exactly one flag.
"""

import inspect
import os
import sys
from collections.abc import Callable, Sequence
from importlib import metadata
from typing import Any

from . import help as _help
from .errors import (
    EXIT_OK,
    EXIT_USAGE,
    HelpRequested,
    RegistrationError,
    UsageError,
    VersionRequested,
)
from .model import MISSING, CommandSpec, FlagSpec, Namespace
from .parser import parse
from .types import BOOL, resolve_kind

RESERVED_FLAGS = ("-h", "--help", "--version")


def _package_version() -> str:
    try:
        return metadata.version("garsloppycli")
    except metadata.PackageNotFoundError:  # running from a source checkout
        return "0.0.0+unknown"


def _normalize_flag_name(name: str, form: str | None = None) -> str:
    """Normalize a declared flag name to ``-x`` or ``--long``.

    ``form`` forces the shape (``"short"``/``"long"``) so ``add_short_flag`` and
    ``add_long_flag`` cannot quietly produce the other shape; ``None`` infers it
    from the spelling (``"a"`` -> ``-a``, ``"long-flag"`` -> ``--long-flag``).
    """
    name = name.strip()
    if form == "short":
        body = name[1:] if name.startswith("-") and not name.startswith("--") else name
        if len(body) != 1 or not body.isalnum():
            raise RegistrationError(
                f"invalid short flag name {name!r}: short flags are a single alphanumeric character"
            )
        return f"-{body}"
    if form == "long":
        body = name.lstrip("-")
        if not body or "=" in body:
            raise RegistrationError(f"invalid long flag name {name!r}")
        return f"--{body}"
    if name.startswith("--"):
        body = name[2:]
        if not body or "=" in body or body.startswith("-"):
            raise RegistrationError(f"invalid long flag name {name!r}")
        return f"--{body}"
    if name.startswith("-"):
        body = name[1:]
        if len(body) != 1 or not body.isalnum():
            raise RegistrationError(
                f"invalid short flag name {name!r}: short flags are a single alphanumeric character"
            )
        return f"-{body}"
    if not name:
        raise RegistrationError("flag name must not be empty")
    return f"-{name}" if len(name) == 1 else f"--{name}"


def _call(fn: Callable[..., Any], ns: Namespace) -> Any:
    """Call a handler with the namespace, or with no arguments if it takes none."""
    try:
        parameters = inspect.signature(fn).parameters
    except TypeError, ValueError:  # builtins and some callables
        return fn(ns)
    return fn() if not parameters else fn(ns)


class Command:
    """A registered command; also the scope object for its own flags."""

    def __init__(self, cli: CLI, spec: CommandSpec) -> None:
        self._cli = cli
        self._spec = spec

    @property
    def name(self) -> str:
        return self._spec.name

    @property
    def help(self) -> str:
        return self._spec.help

    @property
    def aliases(self) -> tuple[str, ...]:
        return self._spec.aliases

    @property
    def fn(self) -> Callable[..., Any]:
        return self._spec.fn

    # Flags scoped to this command.
    def add_flag(self, *names: str, type: Any, variable: str, **kw: Any) -> FlagSpec:
        return self._cli._register(names, type, variable, scope=self._spec, **kw)

    def add_short_flag(self, name: str, type: Any, variable: str, **kw: Any) -> FlagSpec:
        return self._cli._register((name,), type, variable, scope=self._spec, form="short", **kw)

    def add_long_flag(self, name: str, type: Any, variable: str, **kw: Any) -> FlagSpec:
        return self._cli._register((name,), type, variable, scope=self._spec, form="long", **kw)

    def __repr__(self) -> str:
        return f"<Command {self.name!r}>"


class CLI:
    """A declarative command-line interface."""

    def __init__(
        self,
        prog: str | None = None,
        *,
        description: str = "",
        version: str | None = None,
    ) -> None:
        self.prog = prog or os.path.basename(sys.argv[0]) or "python"
        self.description = description
        self.version = version or _package_version()
        self._globals: list[FlagSpec] = []
        self._commands: dict[str, CommandSpec] = {}
        self._aliases: dict[str, str] = {}
        self._default_command: str | None = None

    # --- Declaration ---------------------------------------------------------
    def add_command(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        help: str = "",
        aliases: Sequence[str] = (),
    ) -> Command:
        """Register ``name`` -> ``fn`` and return the command's flag scope."""
        if not name or name.startswith("-"):
            raise RegistrationError(f"invalid command name {name!r}")
        if name in self._commands or name in self._aliases:
            raise RegistrationError(f"command name '{name}' is already registered")
        for alias in aliases:
            if not alias or alias.startswith("-"):
                raise RegistrationError(f"invalid command alias {alias!r}")
            if alias in self._commands or alias in self._aliases:
                raise RegistrationError(f"command name '{alias}' is already registered")
        if not callable(fn):
            raise RegistrationError(f"handler for command '{name}' is not callable")
        spec = CommandSpec(name=name, fn=fn, help=help, aliases=tuple(aliases))
        self._commands[name] = spec
        for alias in spec.aliases:
            self._aliases[alias] = name
        return Command(self, spec)

    def command(
        self, name: str, *, help: str = "", aliases: Sequence[str] = ()
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator form of :meth:`add_command`; returns the function unchanged."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.add_command(name, fn, help=help, aliases=aliases)
            return fn

        return decorator

    def set_default_command(self, name: str) -> None:
        """Allow running with no command name (e.g. ``file.py -a``)."""
        if name not in self._commands:
            raise RegistrationError(f"unknown command '{name}'")
        self._default_command = name

    def add_flag(self, *names: str, type: Any, variable: str, **kw: Any) -> FlagSpec:
        """Global flag: valid before and after the command name."""
        return self._register(names, type, variable, scope=None, **kw)

    def add_short_flag(self, name: str, type: Any, variable: str, **kw: Any) -> FlagSpec:
        """Short-only flag; the name must be a single alphanumeric character."""
        return self._register((name,), type, variable, scope=None, form="short", **kw)

    def add_long_flag(self, name: str, type: Any, variable: str, **kw: Any) -> FlagSpec:
        """Long-only flag; ``"count"`` and ``"--count"`` both mean ``--count``."""
        return self._register((name,), type, variable, scope=None, form="long", **kw)

    def _register(
        self,
        names: Sequence[str],
        type: Any,
        variable: str,
        *,
        scope: CommandSpec | None,
        form: str | None = None,
        help: str = "",
        default: Any = None,
        required: bool = False,
        metavar: str | None = None,
        multiple: bool = False,
        aliases: Sequence[str] = (),
    ) -> FlagSpec:
        kind, coerce = resolve_kind(type)
        if not isinstance(variable, str) or not variable.isidentifier():
            raise RegistrationError(f"variable must be a valid identifier, got {variable!r}")
        if not names:
            raise RegistrationError("a flag needs at least one name")

        normalized = tuple(dict.fromkeys(_normalize_flag_name(n, form) for n in names))
        normalized += tuple(
            n for n in (_normalize_flag_name(a) for a in aliases) if n not in normalized
        )
        for name in normalized:
            if name in RESERVED_FLAGS:
                raise RegistrationError(f"flag name '{name}' is reserved by the library")
            for spec in self._iter_flags():
                if name in spec.names:
                    raise RegistrationError(f"flag name '{name}' is already declared")
                if spec.variable == variable:
                    names = "', '".join(spec.names)
                    raise RegistrationError(
                        f"variable '{variable}' is already bound to flag '{names}'"
                    )

        if required and default is not None:
            raise RegistrationError(
                f"flag '{normalized[-1]}' cannot be both required and have a default value"
            )
        if default is None and kind == BOOL:
            default = False
        if multiple and default is None:
            default = ()
        if required:
            default = MISSING

        spec = FlagSpec(
            names=normalized,
            variable=variable,
            kind=kind,
            coerce=coerce,
            default=default,
            required=required,
            help=help,
            metavar=metavar,
            multiple=multiple,
        )
        (self._globals if scope is None else scope.flags).append(spec)
        return spec

    def _iter_flags(self) -> list[FlagSpec]:
        specs = list(self._globals)
        for command in self._commands.values():
            specs.extend(command.flags)
        return specs

    # --- Parsing -------------------------------------------------------------
    def parse(self, argv: Sequence[str] | None = None) -> Namespace:
        """Parse ``argv`` (defaults to ``sys.argv[1:]``); never exits or prints."""
        return parse(
            list(sys.argv[1:] if argv is None else argv),
            prog=self.prog,
            global_flags=self._globals,
            commands=self._commands,
            aliases=self._aliases,
            default_command=self._default_command,
        )

    def render_help(self, command: str | None = None) -> str:
        """Full help text, optionally scoped to one command."""
        spec = self._commands.get(command) if command is not None else None
        if command is not None and spec is None:
            raise RegistrationError(f"unknown command '{command}'")
        return _help.render_help(
            prog=self.prog,
            description=self.description,
            commands=tuple(self._commands.values()) if spec is None else (),
            flags=[*self._globals, *(spec.flags if spec else ())],
            command=command,
        )

    def print_help(self, command: str | None = None) -> None:
        print(self.render_help(command))

    # --- Running -------------------------------------------------------------
    def run(self, argv: Sequence[str] | None = None) -> Any:
        """Parse and dispatch. Usage errors print to stderr and exit with code 2."""
        try:
            ns = self.parse(argv)
        except HelpRequested as exc:
            self.print_help(exc.command)
            raise SystemExit(EXIT_OK) from None
        except VersionRequested:
            print(f"{self.prog} {self.version}")
            raise SystemExit(EXIT_OK) from None
        except UsageError as exc:
            self._fail(exc)
            raise SystemExit(EXIT_USAGE) from None
        return _call(self._commands[ns.command].fn, ns)

    def main(self, argv: Sequence[str] | None = None) -> None:
        """``console_scripts`` entry point: run and exit with the handler's code."""
        raise SystemExit(self.run(argv))

    def _fail(self, exc: UsageError) -> None:
        print(f"{self.prog}: error: {exc}", file=sys.stderr)
        if exc.command is None and self._commands:
            print(f"Available commands: {', '.join(sorted(self._commands))}", file=sys.stderr)
        scope = f" {exc.command}" if exc.command else ""
        print(f"Try '{self.prog}{scope} --help'", file=sys.stderr)
