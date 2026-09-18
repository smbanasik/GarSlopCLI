#!/usr/bin/env python3
"""Reference CLI for GarSlopCLI — the flagship example from the project plan.

python examples/file.py doThing -abc cInput --long-flag longFlagInput
"""

from garslopcli import CLI

cli = CLI(prog="file.py", description="Example CLI")


@cli.command("doThing", help="Does the thing")
def do_thing(ns):
    print(f"all={ns.a_all} c={ns.c_var!r} long={ns.long_flag!r}")
    return 0


cli.add_short_flag("a", "bool", "a_all")
cli.add_short_flag("b", "bool", "b_all")
cli.add_short_flag("c", "string", "c_var")
cli.add_long_flag("long-flag", "string", "long_flag")

if __name__ == "__main__":
    cli.main()
