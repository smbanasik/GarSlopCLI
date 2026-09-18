"""Flag kinds and token coercion.

A declared flag type resolves to ``(kind, coercer)``:

===============  ==========  ====================================
declared         kind        coercer
===============  ==========  ====================================
``"bool"``       ``bool``    ``None`` (presence only)
``"string"``     ``string``  ``str``
``"number"``     ``number``  :func:`coerce_number` (int, else float)
``int``/``float``  ``number``  the callable itself (strict)
any callable     ``custom``  the callable
===============  ==========  ====================================
"""

import re
from collections.abc import Callable
from typing import Any

BOOL = "bool"
STRING = "string"
NUMBER = "number"
CUSTOM = "custom"

#: Human label used in "invalid <label> for '--flag': 'value'" messages.
_LABELS = {BOOL: "boolean", STRING: "string", NUMBER: "number", CUSTOM: "value"}

_INT_RE = re.compile(r"^[+-]?\d+$")
_TRUE = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE = frozenset({"0", "false", "f", "no", "n", "off"})


class ValueTypeError(ValueError):
    """A token could not be converted to the declared flag type."""


def resolve_kind(type_: Any) -> tuple[str, Callable[[str], Any] | None]:
    """Map a user-declared type to ``(kind, coercer)``.

    Raises :class:`TypeError` for values that are not a known kind name, a
    builtin, or a callable — a programming error, so it fails at registration.
    """
    if isinstance(type_, str):
        name = type_.strip().lower()
        if name == BOOL:
            return BOOL, None
        if name == STRING:
            return STRING, str
        if name == NUMBER:
            return NUMBER, coerce_number
        raise TypeError(
            f"unknown flag type {type_!r}: expected 'bool', 'string', 'number', or a callable"
        )
    if type_ is bool:
        return BOOL, None
    if type_ is str:
        return STRING, str
    if type_ in (int, float):
        return NUMBER, type_
    if callable(type_):
        return CUSTOM, type_
    raise TypeError(
        f"unknown flag type {type_!r}: expected 'bool', 'string', 'number', or a callable"
    )


def coerce_number(token: str) -> int | float:
    """``int`` when the token is integral, otherwise ``float``."""
    if _INT_RE.match(token):
        return int(token)
    try:
        return float(token)
    except ValueError as exc:
        raise ValueTypeError(f"invalid number: {token!r}") from exc


def coerce_bool(token: str) -> bool:
    """Parse an inline boolean (``--flag=false``, ``--flag=1``, ...)."""
    value = token.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueTypeError(f"invalid boolean: {token!r}")


def label(kind: str) -> str:
    """Message label for a kind (``number`` -> ``"number"``, custom -> ``"value"``)."""
    return _LABELS.get(kind, "value")
