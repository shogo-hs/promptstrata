"""promptstrata: レイヤー YAML からカスタマーサポート AI のシステムプロンプトを合成する。"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .compose import BuildError, BuiltPrompt, PromptSet, SourceRef
from .models import (
    Channel,
    Constraint,
    Escalation,
    Governance,
    LayerFileError,
    Principle,
    Procedure,
    Prohibition,
    PromptStrataError,
    Role,
    Term,
    Vocabulary,
)

try:
    # 版の正本は pyproject.toml の [project].version ただ1つ。ここに書き写すと必ず食い違う。
    __version__ = version("promptstrata")
except PackageNotFoundError:  # pragma: no cover - インストールせずに import した場合
    __version__ = "0.0.0+unknown"

__all__ = [
    "BuildError",
    "BuiltPrompt",
    "Channel",
    "Constraint",
    "Escalation",
    "Governance",
    "LayerFileError",
    "Principle",
    "Procedure",
    "Prohibition",
    "PromptSet",
    "PromptStrataError",
    "Role",
    "SourceRef",
    "Term",
    "Vocabulary",
    "__version__",
]
