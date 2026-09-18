"""Help and usage rendering.

Generated from the declared metadata: the command list, each flag's names,
placeholder, and help text. Falls back to a ``(kind)`` label when a flag was
declared without help text, so nothing is silently undocumented.
"""

from collections.abc import Sequence

from .model import CommandSpec, FlagSpec

COMMAND_USAGE = "{prog} <command> [options]"
FLAGS_USAGE = "{prog} [options]"


def flag_display(spec: FlagSpec) -> str:
    """``-n, --count NUMBER`` / ``-a`` / ``--long-flag VALUE``."""
    return spec.display


def render_help(
    *,
    prog: str,
    description: str = "",
    commands: Sequence[CommandSpec] = (),
    flags: Sequence[FlagSpec] = (),
    command: str | None = None,
) -> str:
    """Build the full help text for the CLI or for one command scope."""
    lines: list[str] = []
    if description:
        # ASCII only: help text must print on legacy Windows console code pages.
        lines += [f"{prog}: {description}", ""]

    if command is not None:
        lines.append(f"Usage: {prog} {command} [options]")
    elif commands:
        lines.append(f"Usage: {COMMAND_USAGE.format(prog=prog)}")
    else:
        lines.append(f"Usage: {FLAGS_USAGE.format(prog=prog)}")
    lines.append("")

    if commands and command is None:
        lines.append("Commands:")
        width = max(len(spec.name) for spec in commands)
        for spec in commands:
            lines.append(f"  {spec.name.ljust(width)}  {spec.help}".rstrip())
        lines.append("")

    entries = [(flag_display(spec), spec.help or f"({spec.kind})") for spec in flags]
    entries += [("-h, --help", "Show this help"), ("--version", "Show version")]

    lines.append("Options:")
    width = max(len(label) for label, _ in entries)
    for label, text in entries:
        lines.append(f"  {label.ljust(width)}  {text}".rstrip())

    return "\n".join(lines)
