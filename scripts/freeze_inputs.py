#!/usr/bin/env python3
import sys

from exam_agents.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["freeze-inputs", *sys.argv[1:]]))
