"""レイヤー YAML の型と読み込み。

レイヤーはすべて任意。ファイルが無ければそのレイヤーは ``None``（チャネルと手順は空の dict）
になる。「書かれていないものは無い」を全レイヤー・全フィールドに通す。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "Channel",
    "Constraint",
    "Escalation",
    "Governance",
    "LayerFileError",
    "LoadedLayers",
    "Principle",
    "Procedure",
    "Prohibition",
    "PromptStrataError",
    "Role",
    "Term",
    "Vocabulary",
    "load_layers",
]


class PromptStrataError(Exception):
    """promptstrata が投げる例外の親。"""


class LayerFileError(PromptStrataError):
    """レイヤー YAML の読み込みか検証に失敗した。"""


_T = TypeVar("_T", bound=BaseModel)


class _Strict(BaseModel):
    # YAML のキーの打ち間違いを黙って捨てない。
    model_config = ConfigDict(extra="forbid")


# --- ロール -------------------------------------------------------------------


class Principle(_Strict):
    """あるべき振る舞いの1項目。"""

    id: str
    text: str


class Role(_Strict):
    """誰として振る舞うか。"""

    kind: Literal["role"] = "role"
    version: int = 1
    identity: str | None = None
    principles: list[Principle] = Field(default_factory=list)
    tone: str | None = None


# --- 語彙 ---------------------------------------------------------------------


class Term(_Strict):
    """サービス名などの1語。

    ``misheard`` は音声認識が実際に間違えた表記。これをプロンプトに載せて矯正する。
    """

    canonical: str
    reading: str | None = None
    summary: str | None = None
    aliases: list[str] = Field(default_factory=list)
    misheard: list[str] = Field(default_factory=list)


class Vocabulary(_Strict):
    """扱うサービス・用語の一覧。"""

    kind: Literal["vocabulary"] = "vocabulary"
    version: int = 1
    terms: list[Term] = Field(default_factory=list)


# --- ガバナンス ---------------------------------------------------------------


class Prohibition(_Strict):
    """禁止事項の1項目。"""

    id: str
    text: str
    on_violation: str | None = None


class Escalation(_Strict):
    """自分で判断せず引き継ぐ条件。"""

    when: str
    action: str
    say: str | None = None


class Governance(_Strict):
    """禁止事項と引き継ぎの規則。"""

    kind: Literal["governance"] = "governance"
    version: int = 1
    prohibitions: list[Prohibition] = Field(default_factory=list)
    escalation: list[Escalation] = Field(default_factory=list)
    out_of_scope: str | None = None


# --- チャネル -----------------------------------------------------------------


class Constraint(_Strict):
    """そのチャネルで守るべき制約の1項目。"""

    id: str
    text: str


class Channel(_Strict):
    """電話・チャット・メールなど、媒体ごとの制約。"""

    kind: Literal["channel"] = "channel"
    version: int = 1
    name: str
    description: str | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    formatting: dict[str, str] = Field(default_factory=dict)


# --- 手順 ---------------------------------------------------------------------


class Procedure(_Strict):
    """返金・本人確認などの業務手順。"""

    kind: Literal["procedure"] = "procedure"
    version: int = 1
    name: str
    trigger: str | None = None
    steps: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


# --- 読み込み -----------------------------------------------------------------


@dataclass(frozen=True)
class LoadedLayers:
    """1つのディレクトリから読み込んだレイヤー一式。"""

    root: Path
    role: Role | None = None
    vocabulary: Vocabulary | None = None
    governance: Governance | None = None
    channels: dict[str, Channel] = field(default_factory=dict)
    procedures: dict[str, Procedure] = field(default_factory=dict)
    # "role" / "channel:voice" のような識別子 -> 読み込み元のパス
    paths: dict[str, Path] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (
            self.role or self.vocabulary or self.governance or self.channels or self.procedures
        )


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LayerFileError(f"{path}: YAML として読めない: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise LayerFileError(f"{path}: トップレベルがマッピングでない（{type(raw).__name__}）")
    return raw


def _find(root: Path, stem: str) -> Path | None:
    """``stem.yaml`` か ``stem.yml`` を探す。無ければ None。"""
    for suffix in (".yaml", ".yml"):
        candidate = root / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _parse(model: type[_T], path: Path, raw: dict[str, Any] | None = None) -> _T:
    """YAML を読んで検証する。``raw`` を渡した場合は読み込みを省く。"""
    data = _read_yaml(path) if raw is None else raw
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise LayerFileError(f"{path}: {exc}") from exc


def _glob_dir(root: Path, name: str) -> list[Path]:
    directory = root / name
    if not directory.is_dir():
        return []
    found = [p for p in directory.iterdir() if p.suffix in (".yaml", ".yml") and p.is_file()]
    return sorted(found)


def load_layers(root: str | Path) -> LoadedLayers:
    """ディレクトリからレイヤーを読み込む。無いレイヤーは None のまま返す。

    Raises:
        LayerFileError: ディレクトリが無い、YAML が壊れている、スキーマに合わない場合。
    """
    base = Path(root)
    if not base.is_dir():
        raise LayerFileError(f"{base}: ディレクトリが無い")

    paths: dict[str, Path] = {}

    role: Role | None = None
    if (p := _find(base, "role")) is not None:
        role, paths["role"] = _parse(Role, p), p

    vocabulary: Vocabulary | None = None
    if (p := _find(base, "vocabulary")) is not None:
        vocabulary, paths["vocabulary"] = _parse(Vocabulary, p), p

    governance: Governance | None = None
    if (p := _find(base, "governance")) is not None:
        governance, paths["governance"] = _parse(Governance, p), p

    channels: dict[str, Channel] = {}
    for p in _glob_dir(base, "channels"):
        raw = _read_yaml(p)
        raw.setdefault("name", p.stem)
        channel = _parse(Channel, p, raw)
        channels[channel.name] = channel
        paths[f"channel:{channel.name}"] = p

    procedures: dict[str, Procedure] = {}
    for p in _glob_dir(base, "procedures"):
        raw = _read_yaml(p)
        raw.setdefault("name", p.stem)
        procedure = _parse(Procedure, p, raw)
        procedures[procedure.name] = procedure
        paths[f"procedure:{procedure.name}"] = p

    return LoadedLayers(
        root=base,
        role=role,
        vocabulary=vocabulary,
        governance=governance,
        channels=channels,
        procedures=procedures,
        paths=paths,
    )
