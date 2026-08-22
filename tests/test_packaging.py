"""版の管理が崩れていないかを確かめる。

版の正本は pyproject.toml の [project].version ただ1つ。__init__.py に書き写すと
いつか必ず食い違うので、importlib.metadata から読ませている。それが効いているかを見る。
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import promptstrata

ROOT = Path(__file__).resolve().parent.parent


def declared_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = data["project"]["version"]
    assert isinstance(version, str)
    return version


def test_version_has_a_single_source() -> None:
    assert promptstrata.__version__ == declared_version()


def test_changelog_has_an_entry_for_the_current_version() -> None:
    # 節が無いまま公開しないための歯止め。release.yml も同じことを CI 側で見ている。
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{declared_version()}]" in changelog
