#!/usr/bin/env python3

import argparse
from pathlib import Path

from navigation import NavigationError, load_navigation, validate_navigation


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Zola Docs navigation JSON or TOML")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        normalized, nodes = validate_navigation(load_navigation(args.path))
    except (OSError, ValueError, NavigationError) as error:
        raise SystemExit(str(error)) from error
    print(f"valid: {len(normalized['groups'])} groups, {nodes} nodes")


if __name__ == "__main__":
    main()
