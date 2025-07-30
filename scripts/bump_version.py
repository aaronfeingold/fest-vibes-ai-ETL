#!/usr/bin/env python3
"""
Simple version bumping script for pyproject.toml
Increments the patch version and updates the file.
"""

import re
import sys
import tomllib


def bump_patch_version():
    """Bump the patch version in pyproject.toml"""
    try:
        # Read current pyproject.toml
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)

        # Get current version and bump patch
        current = data["project"]["version"]
        major, minor, patch = map(int, current.split("."))
        new_version = f"{major}.{minor}.{patch + 1}"

        # Update the file
        with open("pyproject.toml", "r") as f:
            content = f.read()

        content = re.sub(r"version = \"[^\"]+\"", f'version = "{new_version}"', content)

        with open("pyproject.toml", "w") as f:
            f.write(content)

        print(f"Bumped version from {current} to {new_version}")
        return new_version

    except Exception as e:
        print(f"Error bumping version: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    bump_patch_version()
