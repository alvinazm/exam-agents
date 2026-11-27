#!/usr/bin/env python3
import sys

from exam_agents.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["submit-result", *sys.argv[1:]]))
