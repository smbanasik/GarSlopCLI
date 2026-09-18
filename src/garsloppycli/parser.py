"""Pure argv parsing: no I/O, no ``sys.exit``, no printing.

Grammar (see the project plan §4):

1. **Pass one** consumes leading *global* flags until the first positional token.
2. That token is the **command** name (or one of its aliases).
3. **Pass two** parses the remainder against ``globals + command flags``.

Short clusters (``-abcInput``) are consumed left to right: every boolean flag sets
``True``; the first value-taking flag takes the rest of the token as its value, or
the next argv token when nothing remains. A value is consumed verbatim (so
``--count -5`` works) unless the next token is itself a registered flag name — then
the parser reports a missing value instead of swallowing a flag.
"""

import difflib
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import HelpRequested, RegistrationError, UsageError, VersionRequested
from .model import MISSING, CommandSpec, FlagSpec, Namespace
from .types import BOOL, coerce_bool, label

END_OF_OPTIONS = "--"
HELP_NAMES = ("-h", "--help")
VERSION_NAMES = ("--version",)

_HELP_VAR = "_help"
_VERSION_VAR = "_version"


def builtin_flags() -> list[FlagSpec]:
    """``-h/--help`` and ``--version``, registered as ordinary flags for uniform parsing."""
    return [
        FlagSpec(
            names=HELP_NAMES,
            variable=_HELP_VAR,
            kind=BOOL,
            coerce=None,
            help="Show this help",
            builtin=True,
        ),
        FlagSpec(
            names=VERSION_NAMES,
            variable=_VERSION_VAR,
            kind=BOOL,
            coerce=None,
            help="Show version",
            builtin=True,
        ),
    ]


class _Table:
    """Flag-name lookup (``-c`` -> spec) preserving declaration order."""

    def __init__(self) -> None:
        self.specs: list[FlagSpec] = []
        self._by_name: dict[str, FlagSpec] = {}

    def add(self, spec: FlagSpec) -> None:
        for name in spec.names:
            if name in self._by_name:
                raise RegistrationError(f"flag name '{name}' is declared twice")
            self._by_name[name] = spec
        self.specs.append(spec)

    def get(self, name: str) -> FlagSpec | None:
        return self._by_name.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    def names(self) -> tuple[str, ...]:
        return tuple(self._by_name)


def parse(
    argv: Sequence[str],
    *,
    prog: str,
    global_flags: Sequence[FlagSpec] = (),
    commands: Mapping[str, CommandSpec] | None = None,
    aliases: Mapping[str, str] | None = None,
    default_command: str | None = None,
) -> Namespace:
    """Parse ``argv`` (without the program name) into a :class:`Namespace`.

    Never touches the process: raises :class:`UsageError` on bad input and
    :class:`HelpRequested` / :class:`VersionRequested` for the built-in flags.
    """
    commands = commands or {}
    aliases = aliases or {}
    command_flag_owner = {
        name: spec.name for spec in commands.values() for flag in spec.flags for name in flag.names
    }

    globals_table = _Table()
    for spec in (*builtin_flags(), *global_flags):
        globals_table.add(spec)

    values: dict[str, Any] = {}

    def assign(spec: FlagSpec, raw: str | None, name: str, scope: str | None) -> None:
        """Record one flag occurrence, coercing its value."""
        if spec.builtin:
            if spec.variable == _HELP_VAR:
                raise HelpRequested(scope)
            raise VersionRequested()
        if spec.kind == BOOL:
            value: Any = True if raw is None else _convert(raw, coerce_bool, name, BOOL, scope)
        else:
            value = _convert(raw or "", spec.coerce, name, spec.kind, scope)
        if spec.multiple:
            values.setdefault(spec.variable, []).append(value)
        else:
            values[spec.variable] = value

    def unknown_flag(name: str, token: str, table: _Table, scope: str | None) -> UsageError:
        owner = None if name in globals_table else command_flag_owner.get(name)
        detail = f" (in '{token}')" if token != name else ""
        if owner is not None:
            if scope is None:
                message = f"flag '{name}' belongs to command '{owner}' and must follow it"
            else:
                message = f"flag '{name}' belongs to command '{owner}', not '{scope}'"
            return UsageError(message, command=scope)
        return UsageError(
            f"unknown flag '{name}'{detail}{_suggest(name, table.names())}", command=scope
        )

    def next_value(index: int, table: _Table, name: str, scope: str | None) -> tuple[str, int]:
        """The following argv token, unless it is a registered flag name."""
        if index + 1 >= len(argv):
            raise UsageError(f"flag '{name}' requires a value", command=scope)
        candidate = argv[index + 1]
        if candidate.split("=", 1)[0] in table:
            raise UsageError(f"flag '{name}' requires a value", command=scope)
        return candidate, index + 2

    def consume_long(index: int, table: _Table, scope: str | None) -> int:
        token = argv[index]
        name, sep, inline = token.partition("=")
        spec = table.get(name)
        if spec is None:
            raise unknown_flag(name, token, table, scope)
        if spec.kind == BOOL:
            assign(spec, inline if sep else None, name, scope)
            return index + 1
        if sep:
            assign(spec, inline, name, scope)
            return index + 1
        value, index = next_value(index, table, name, scope)
        assign(spec, value, name, scope)
        return index

    def consume_short(index: int, table: _Table, scope: str | None) -> int:
        token = argv[index]
        chars = token[1:]
        position = 0
        while position < len(chars):
            char = chars[position]
            name = "-" + char
            spec = table.get(name)
            if spec is None:
                raise unknown_flag(name, token, table, scope)
            if spec.kind == BOOL:
                if chars[position + 1 : position + 2] == "=":
                    raise UsageError(
                        f"cannot assign a value to short bool flag '{name}'", command=scope
                    )
                assign(spec, None, name, scope)
                position += 1
                continue
            rest = chars[position + 1 :]
            if rest.startswith("="):
                hint = rest[1:] or "..."
                raise UsageError(
                    f"short flag '{name}' does not take '=' "
                    f"(use '{name}{hint}' or '{name} {hint}')",
                    command=scope,
                )
            if rest:
                assign(spec, rest, name, scope)
                return index + 1
            value, index = next_value(index, table, name, scope)
            assign(spec, value, name, scope)
            return index
        return index + 1

    # --- Passes one and two: leading globals, then the command token -----------
    index = 0
    command_name: str | None = None
    literal = False
    while index < len(argv):
        token = argv[index]
        if literal:
            command_name = token
            index += 1
            break
        if token == END_OF_OPTIONS:
            literal = True
            index += 1
            continue
        if token.startswith("--") and len(token) > 2:
            index = consume_long(index, globals_table, None)
            continue
        if token.startswith("-") and token != "-":
            index = consume_short(index, globals_table, None)
            continue
        command_name = token
        index += 1
        break

    if command_name is None:
        if default_command is None:
            raise UsageError("no command given")
        command_name = default_command
    canonical = aliases.get(command_name, command_name)
    command = commands.get(canonical)
    if command is None:
        candidates = [*commands, *aliases]
        raise UsageError(f"unknown command '{command_name}'{_suggest(command_name, candidates)}")

    table = _Table()
    for spec in globals_table.specs:
        table.add(spec)
    for spec in command.flags:
        table.add(spec)

    # --- Pass three: everything after the command ------------------------------
    positionals: list[str] = []
    literal = False
    while index < len(argv):
        token = argv[index]
        if literal:
            positionals.append(token)
            index += 1
            continue
        if token == END_OF_OPTIONS:
            literal = True
            index += 1
            continue
        if token.startswith("--") and len(token) > 2:
            index = consume_long(index, table, canonical)
            continue
        if token.startswith("-") and token != "-":
            index = consume_short(index, table, canonical)
            continue
        positionals.append(token)
        index += 1

    return Namespace(
        _finalize(table, values, command),
        command=canonical,
        prog=prog,
        positionals=tuple(positionals),
    )


def _finalize(table: _Table, values: dict[str, Any], command: CommandSpec) -> dict[str, Any]:
    """Check required flags and fill defaults, in declaration order."""
    final: dict[str, Any] = {}
    for spec in table.specs:
        if spec.builtin:
            continue
        if spec.variable in values:
            final[spec.variable] = values[spec.variable]
            continue
        if spec.default is MISSING:
            raise UsageError(
                f"missing required flag '{spec.names[-1]}'",
                command=command.name,
            )
        if spec.multiple:
            final[spec.variable] = list(spec.default or ())
        else:
            final[spec.variable] = spec.default
    return final


def _convert(token: str, coercer: Any, name: str, kind: str, scope: str | None) -> Any:
    """Convert ``token`` with ``coercer``, reporting user-facing errors."""
    assert coercer is not None  # every value-taking kind has one
    try:
        return coercer(token)
    except ValueError:
        raise UsageError(f"invalid {label(kind)} for '{name}': {token!r}", command=scope) from None
    except Exception as exc:  # a user-supplied validator raised something else
        raise UsageError(f"invalid value for '{name}': {token!r} ({exc})", command=scope) from exc


def _suggest(name: str, candidates: Sequence[str]) -> str:
    """``" (did you mean '--count'?)"`` when a near-miss name exists."""
    matches = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    return f" (did you mean '{matches[0]}'?)" if matches else ""
