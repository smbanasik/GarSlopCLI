# GarSlopCLI

A zero-dependency Python library that turns a handful of declarations into a full
command + flag parser.

```
file.py command -abc cInput --long-flag longFlagInput
```

- **Declarative** — `add_command`, `add_short_flag`, `add_long_flag`. No parser objects, no `dest=` bookkeeping.
- **Three kinds** — `bool`, `string`, `number` (a callable like `int`/`Decimal` is also accepted).
- **Getopt-style clusters** — `-abc cInput` and `-abccInput` mean the same thing.
- **Stdlib only**, Python >= 3.14, MIT.

## Install

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"   # from a checkout
```

Not published to PyPI yet.

## Quick start

```python
#!/usr/bin/env python3
# file.py
from garslopcli import CLI

cli = CLI(prog="file.py", description="Example CLI")


@cli.command("doThing", help="Does the thing")
def do_thing(ns):
    print(f"all={ns.a_all} c={ns.c_var!r} long={ns.long_flag!r}")


cli.add_short_flag("a", "bool", "a_all")
cli.add_short_flag("b", "bool", "b_all")
cli.add_short_flag("c", "string", "c_var")
cli.add_long_flag("long-flag", "string", "long_flag")

if __name__ == "__main__":
    cli.main()
```

```
$ file.py doThing -abc cInput --long-flag longFlagInput
all=True c='cInput' long='longFlagInput'
```

All of these are equivalent:

```
file.py doThing -abc cInput --long-flag longFlagInput
file.py doThing -abccInput --long-flag=longFlagInput
file.py doThing -c cInput -a -b --long-flag longFlagInput
file.py doThing --long-flag longFlagInput -abc cInput
```

## API

| Call | Meaning |
| --- | --- |
| `cli.add_command(name, fn, help=..., aliases=(...))` | Register a command; returns its flag scope |
| `cli.command(name, ...)` | Decorator form; returns your function unchanged |
| `cli.add_flag("-n", "--count", type="number", variable="n")` | One flag under several names |
| `cli.add_short_flag("c", "string", "c_var")` | Short-only flag; the name must be a single character (`-c`) |
| `cli.add_long_flag("long-flag", "string", "long_flag")` | Long-only flag; `"count"` and `"--count"` both mean `--count` |
| `cli.set_default_command(name)` | Allow running with no command name |
| `cli.parse(argv=None)` | Parse only: returns a `Namespace`, raises `UsageError` (never exits) |
| `cli.run(argv=None)` | Parse and dispatch the handler; exits `2` on usage errors |
| `cli.main()` | `run()` wrapped in `sys.exit` for `console_scripts` |
| `cli.render_help(command=None)` | The generated help text |

Flag options: `default`, `required`, `multiple`, `help`, `metavar`, `aliases`.

`variable` is the attribute name on the namespace handed to your handler
(`ns.long_flag`) — flag names contain `-`, so they cannot be identifiers.
Flag names and variables are unique across the whole CLI; a clash raises
`RegistrationError` at declaration time.

| Declared type | Result |
| --- | --- |
| `"bool"` / `bool` | presence → `True`; `--flag=false` → `False`; never consumes the next token |
| `"string"` / `str` | the token verbatim, including leading `-` and `""` (`--flag=`) |
| `"number"` / `float` | `int` when integral (`7`, `-5`), otherwise `float` (`1e3`, `3.14`) |
| `int` | strict integer (`3.14` is an error) |
| any callable | called with the token; any exception becomes a usage error |

## Grammar

| Input | Result |
| --- | --- |
| `--long-flag value` | value-taking long flag |
| `--long-flag=value` | inline form (`--long-flag=` → `""`) |
| `--long-flag` (bool) | `True`; `--long-flag=false` → `False` |
| `-abcInput` | `-a` bool, `-b` bool, `-c` takes the remainder → `"Input"` |
| `-abc cInput` | `-a` bool, `-b` bool, `-c` takes the next token → `"cInput"` |
| `-abccInput` | same as `-abc cInput` (the `c` is not repeated in the value) |
| `-c -5`, `--count -5` | values are verbatim, so negative numbers work |
| `-c --other-flag` | **error** — a registered flag name is never swallowed as a value |
| `-c=v` | **error** — short flags take values as `-cVALUE` or `-c VALUE`, never with `=` |
| `-a=true` | **error** — short boolean flags take no inline value; use `--long=true` |
| `--` | everything after it is positional |
| `-` | positional (stdin convention) |

Value consumption is driven by the *declared kind*, not by syntax: `-abcInput`
gives `"Input"` because the characters after `c` are the value. Handler results
are returned by `run()`, so handlers are easy to test.

## Help and errors

```
$ file.py --help
file.py: Example CLI

Usage: file.py <command> [options]

Commands:
  doThing  Does the thing

Options:
  -a                 (bool)
  -b                 (bool)
  -c VALUE           (string)
  --long-flag VALUE  (string)
  -h, --help         Show this help
  --version          Show version
```

Undocumented flags fall back to a `(kind)` label — nothing is silently
undocumented. `-h`/`--help` exit `0`; `--version` prints `prog version`.

Usage errors go to stderr with exit code `2` and a scope-correct hint:

```
$ file.py doThing --bogus
file.py: error: unknown flag '--bogus'
Try 'file.py doThing --help'
```

Errors also name near-misses (`did you mean '--long-flag'?`), flags used in the
wrong command scope, missing required flags, and invalid values.

## Development

```powershell
.venv\Scripts\python -m pytest      # 106 tests
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
```

`examples/file.py` is the reference CLI; `tests/test_examples.py` runs it as a
real process to pin exit codes and streams. `parser.py` is at 100% statement
coverage (99% overall).

Known constraints: nested subcommands, positional specs, `choices`, env/config
fallback, counted flags, and shell completion are not implemented yet.
