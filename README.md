# GarSlopPyCLI

A zero-dependency Python library that turns a handful of declarations into a full
command + flag parser.

Target syntax:

```
file.py command -abc cInput --long-flag longFlagInput
```

## API

```python
from garsloppycli import CLI

cli = CLI(prog="file.py", description="Example CLI")

@cli.command("doThing", help="Does the thing")
def do_thing(ns):
    print(f"c={ns.c_var!r} long={ns.long_flag!r}")

cli.add_short_flag("a", "bool", "a_all")
cli.add_short_flag("b", "bool", "b_all")
cli.add_short_flag("c", "string", "c_var")
cli.add_long_flag("long-flag", "string", "long_flag")

if __name__ == "__main__":
    cli.main()
```

- Kinds: `bool`, `string`, `number` (a callable such as `int`/`Decimal` is also accepted).
- `variable` is the attribute name on the namespace passed to your handler.
- Zero runtime dependencies (stdlib only). Python >= 3.14. MIT licensed.

## Status

Scaffold only — `git init` + metadata. Implementation follows the phased plan
(see the vault note `Projects/Programming/LLM Maxxing/LangGraph/python-cli-framework-plan.md`).
