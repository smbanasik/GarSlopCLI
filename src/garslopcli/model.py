"""The declared model (flags, commands) and the parsed namespace."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .types import BOOL, NUMBER


class _Missing:
    """Sentinel for "the user did not provide this required flag"."""

    __slots__ = ()

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _Missing()


@dataclass
class FlagSpec:
    """One declared flag (possibly under several names, e.g. ``-n``/``--count``)."""

    names: tuple[str, ...]
    variable: str
    kind: str
    coerce: Callable[[str], Any] | None
    default: Any = None
    required: bool = False
    help: str = ""
    metavar: str | None = None
    multiple: bool = False
    builtin: bool = False

    @property
    def takes_value(self) -> bool:
        """``False`` for booleans: they never consume the following token."""
        return self.kind != BOOL

    @property
    def placeholder(self) -> str:
        """Help-text placeholder, e.g. ``NUMBER`` for a number flag."""
        if not self.takes_value:
            return ""
        if self.metavar:
            return self.metavar
        return "NUMBER" if self.kind == NUMBER else "VALUE"

    @property
    def display(self) -> str:
        """Help-text label, e.g. ``-n, --count NUMBER``."""
        label = ", ".join(self.names)
        return f"{label} {self.placeholder}" if self.placeholder else label


@dataclass
class CommandSpec:
    """One declared command and the flags scoped to it."""

    name: str
    fn: Callable[..., Any]
    help: str = ""
    aliases: tuple[str, ...] = ()
    flags: list[FlagSpec] = field(default_factory=list)


class Namespace:
    """Parsed result: one attribute per registered ``variable``.

    Also carries ``command`` (canonical name), ``prog``, and ``positionals``
    (tokens left over after flag parsing).
    """

    __slots__ = ("_values", "command", "positionals", "prog")

    def __init__(
        self,
        values: dict[str, Any],
        *,
        command: str,
        prog: str,
        positionals: tuple[str, ...],
    ) -> None:
        self._values = values
        self.command = command
        self.prog = prog
        self.positionals = positionals

    def __getattr__(self, name: str) -> Any:
        try:
            values = object.__getattribute__(self, "_values")
        except AttributeError:  # pragma: no cover - only during unpickling
            raise AttributeError(name) from None
        try:
            return values[name]
        except KeyError:
            known = ", ".join(sorted(values)) or "(none)"
            raise AttributeError(
                f"{name!r} is not a registered flag variable; registered: {known}"
            ) from None

    def as_dict(self) -> dict[str, Any]:
        """The flag variables as a plain dict (``command``/``positionals`` excluded)."""
        return dict(self._values)

    def __repr__(self) -> str:
        return f"Namespace(command={self.command!r}, {self._values!r})"
