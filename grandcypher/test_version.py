import re
from pathlib import Path

from . import __version__


def test_package_version_matches_project_metadata():
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text()
    project = pyproject.split("[project]", 1)[1].split("[", 1)[0]
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', project, re.MULTILINE)

    assert version_match is not None
    assert __version__ == version_match.group(1)
