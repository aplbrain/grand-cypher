import tomllib
from pathlib import Path

from . import __version__


def test_package_version_matches_project_metadata():
    pyproject = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text()
    )

    assert __version__ == pyproject["project"]["version"]
