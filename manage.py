#!/usr/bin/env -S uv run  # noqa: EXE003
import sys

from django.core.management import execute_from_command_line


def main() -> None:
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
