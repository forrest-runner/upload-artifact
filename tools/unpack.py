#!/usr/bin/env python3
"""Extract the composite step that runs with `shell: python3 {0}` from action.yml."""

import sys
from pathlib import Path

import yaml


def unpack(action_yml: str = "action.yml", output_py: str = "action.py") -> None:
    path = Path(action_yml)
    with path.open() as fh:
        data = yaml.safe_load(fh)

    steps = data["runs"]["steps"]
    for step in steps:
        if step.get("shell") == "python3 {0}":
            script = step["run"]
            out = Path(output_py)
            out.write_text(script)
            return

    print("No step with shell 'python3 {0}' found.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    unpack(*sys.argv[1:])
