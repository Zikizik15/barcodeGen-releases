# tests/test_version.py — номер версии один и тот же везде

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from version import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_version_format():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_pyproject_matches():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        match = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    assert match and match.group(1) == __version__, \
        "Версия в pyproject.toml не совпадает с version.py"
