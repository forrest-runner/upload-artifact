#!/usr/bin/env python3
"""Pack action.py back into action.yml (inverse of unpack.py)."""

import sys
from pathlib import Path

import yaml


class LiteralDumper(yaml.SafeDumper):
    """Dumper that writes multiline strings as literal block scalars (|)."""

    pass


def str_representer(dumper, data):
    if "\n" in data.strip():
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    elif len(data) > 80:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=">")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


LiteralDumper.add_representer(str, str_representer)


def pack(action_yml: str = "action.yml", input_py: str = "action.py") -> None:
    yml_path = Path(action_yml)
    with yml_path.open() as fh:
        data = yaml.safe_load(fh)

    script = Path(input_py).read_text()

    steps = data["runs"]["steps"]
    for step in steps:
        if step.get("shell") == "python3 {0}":
            step["run"] = script
            break
    else:
        print("No step with shell 'python3 {0}' found.", file=sys.stderr)
        sys.exit(1)

    with yml_path.open("w") as fh:
        yaml.dump(data, fh, Dumper=LiteralDumper, default_flow_style=False, allow_unicode=True)


if __name__ == "__main__":
    pack(*sys.argv[1:])
