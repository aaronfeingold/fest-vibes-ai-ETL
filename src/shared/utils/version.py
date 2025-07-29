"""
Version utilities for reading project version from pyproject.toml
"""

import tomllib
from pathlib import Path
from typing import Any, Dict


def get_project_root() -> Path:
    """Get the project root directory by finding pyproject.toml"""
    current_path = Path(__file__).resolve()

    for parent in current_path.parents:
        if (parent / "pyproject.toml").exists():
            return parent

    raise FileNotFoundError("Could not find pyproject.toml in project hierarchy")


def read_pyproject_toml() -> Dict[str, Any]:
    """Read and parse the pyproject.toml file"""
    project_root = get_project_root()
    pyproject_path = project_root / "pyproject.toml"

    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


def get_version() -> str:
    """Get the current project version from pyproject.toml"""
    pyproject_data = read_pyproject_toml()

    try:
        return pyproject_data["project"]["version"]
    except KeyError:
        raise KeyError("Version not found in pyproject.toml [project] section")


def get_project_name() -> str:
    """Get the project name from pyproject.toml"""
    pyproject_data = read_pyproject_toml()

    try:
        return pyproject_data["project"]["name"]
    except KeyError:
        raise KeyError("Name not found in pyproject.toml [project] section")


if __name__ == "__main__":
    try:
        print(f"Project: {get_project_name()}")
        print(f"Version: {get_version()}")
    except Exception as e:
        print(f"Error: {e}")
