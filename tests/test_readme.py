"""README のコード例が実際に動くことを確かめる。

実装から API を消したのに README のサンプルが取り残される、という事故が実際に起きた。
人が気づく前にテストが落ちるようにしておく。
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import pytest

from promptstrata.cli import main

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def _text() -> str:
    return README.read_text(encoding="utf-8")


def _python_blocks() -> list[str]:
    return re.findall(r"```python\n(.*?)```", _text(), re.S)


def _yaml_blocks() -> list[str]:
    return re.findall(r"```yaml\n(.*?)```", _text(), re.S)


def _cli_commands() -> list[str]:
    return re.findall(r"^promptstrata (.+)$", _text(), re.M)


def test_readme_shows_both_kinds_of_example() -> None:
    assert _python_blocks(), "README に python のコード例が無い"
    assert _cli_commands(), "README に CLI の例が無い"


def test_python_examples_run(monkeypatch: pytest.MonkeyPatch) -> None:
    # README は examples/sorairo-pay を相対パスで指すので、プロジェクト直下で実行する。
    monkeypatch.chdir(ROOT)
    namespace: dict[str, Any] = {}
    for block in _python_blocks():
        exec(compile(block, str(README), "exec"), namespace)


def test_cli_examples_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    for command in _cli_commands():
        assert main(shlex.split(command)) == 0, f"README の例が失敗した: {command}"


def test_yaml_examples_match_the_real_files() -> None:
    """README の YAML 抜粋が examples/ の実物とずれていないか。

    実際にずれた。README は formatting のキーを amount と書き、実物は 金額 だった。
    抜粋は手で写すものなので、写し間違いはテストでしか捕まらない。
    """
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "examples").rglob("*.yaml"))
    )
    for block in _yaml_blocks():
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert line in corpus, f"README の YAML 抜粋が実物に無い: {line!r}"
