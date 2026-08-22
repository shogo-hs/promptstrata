"""レイヤーを1本のシステムプロンプトに合成する。

穴あきテンプレートには流し込まない。存在するレイヤーだけをパーツとして順に足し、
``"\\n\\n"`` で連結する。各 render 関数は出すものが無ければ空文字を返し、呼び出し側は
空文字を parts に足さない。これで欠損レイヤーの空節や余分な改行が絶対に残らない。
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from string import Template

from .models import (
    Channel,
    Governance,
    LoadedLayers,
    Procedure,
    PromptStrataError,
    Role,
    Vocabulary,
    load_layers,
)

__all__ = ["BuildError", "BuiltPrompt", "PromptSet", "SourceRef"]

# 優先順位表のラベルと強さの並び（強い順）。存在する層だけを filter して番号を振り直す。
_PRIORITY_ORDER: tuple[tuple[str, str], ...] = (
    ("governance", "禁止事項（ガバナンス）"),
    ("channel", "チャネルの制約"),
    ("procedure", "業務手順"),
    ("role", "役割"),
    ("vocabulary", "語彙"),
)


class BuildError(PromptStrataError):
    """プロンプトの合成に失敗した。"""


@dataclass(frozen=True)
class SourceRef:
    """合成に使ったレイヤーファイル1つへの参照。"""

    kind: str
    name: str
    path: str
    version: int


@dataclass(frozen=True)
class BuiltPrompt:
    """合成結果。``text`` をそのままシステムプロンプトに渡す。

    会話中に判明したこと（顧客名など）はここに書き戻さない。モデルは会話履歴から読めるし、
    システムプロンプトを1文字でも変えると、それ以降の会話履歴のプロンプトキャッシュが
    丸ごと落ちる（キャッシュは tools → system → messages の順の前方一致で効く）。
    """

    text: str
    fingerprint: str
    sources: tuple[SourceRef, ...]


@dataclass(frozen=True)
class PromptSet:
    """1つのディレクトリから読み込んだレイヤー一式。"""

    layers: LoadedLayers

    @staticmethod
    def load(root: str | Path) -> PromptSet:
        return PromptSet(layers=load_layers(root))

    def build(
        self,
        *,
        channel: str | None = None,
        procedures: Sequence[str] | None = None,
        vars: Mapping[str, str] | None = None,
    ) -> BuiltPrompt:
        layers = self.layers
        if layers.is_empty():
            raise BuildError(f"{layers.root}: レイヤーが1つも無い")

        selected_channel: Channel | None = None
        if channel is not None:
            selected_channel = layers.channels.get(channel)
            if selected_channel is None:
                available = ", ".join(sorted(layers.channels)) or "（無し）"
                raise BuildError(f"チャネル '{channel}' が無い。存在するチャネル: {available}")

        selected_procedures: list[Procedure] = []
        for name in procedures or ():
            procedure = layers.procedures.get(name)
            if procedure is None:
                available = ", ".join(sorted(layers.procedures)) or "（無し）"
                raise BuildError(f"手順 '{name}' が無い。存在する手順: {available}")
            selected_procedures.append(procedure)

        present_kinds = {
            kind
            for kind, present in (
                ("role", layers.role is not None),
                ("vocabulary", layers.vocabulary is not None),
                ("governance", layers.governance is not None),
                ("channel", selected_channel is not None),
                ("procedure", bool(selected_procedures)),
            )
            if present
        }

        parts: list[str] = []
        for section in (
            _render_priority(present_kinds),
            _render_role(layers.role),
            _render_vocabulary(layers.vocabulary),
            *(_render_procedure(p) for p in selected_procedures),
            _render_channel(selected_channel) if selected_channel is not None else "",
            _render_governance(layers.governance),
        ):
            if section:
                parts.append(section)

        text = "\n\n".join(parts)
        text = _substitute_vars(text, vars or {})

        sources = tuple(_build_sources(layers, selected_channel, selected_procedures))
        fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        return BuiltPrompt(text=text, fingerprint=fingerprint, sources=sources)


def _render_priority(present_kinds: set[str]) -> str:
    """存在する層が2種以上のときだけ優先順位の節を返す。"""
    if len(present_kinds) < 2:
        return ""
    ordered = [label for kind, label in _PRIORITY_ORDER if kind in present_kinds]
    lines = "\n".join(f"{i}. {label}" for i, label in enumerate(ordered, start=1))
    return (
        f"## 規則の優先順位\n\n規則がぶつかったときは、次の順で上にあるものを優先する。\n\n{lines}"
    )


def _render_role(role: Role | None) -> str:
    if role is None:
        return ""
    blocks: list[str] = []
    if role.identity:
        blocks.append(role.identity)
    if role.principles:
        lines = "\n".join(f"- {p.text}" for p in role.principles)
        blocks.append(f"守ること:\n{lines}")
    if role.tone:
        blocks.append(f"話し方: {role.tone}")
    if not blocks:
        return ""
    return "## 役割\n\n" + "\n\n".join(blocks)


def _render_vocabulary(vocabulary: Vocabulary | None) -> str:
    if vocabulary is None or not vocabulary.terms:
        return ""
    lines: list[str] = []
    for term in vocabulary.terms:
        head = term.canonical
        if term.reading:
            head += f"（読み: {term.reading}）"
        if term.summary:
            head += f"— {term.summary}"
        lines.append(f"- {head}")
        if term.aliases:
            lines.append(f"  - 別名: {' / '.join(term.aliases)}")
        if term.misheard:
            misheard = "".join(f"「{m}」" for m in term.misheard)
            lines.append(
                f"  - {misheard}と書き起こされることがあるが、いずれも {term.canonical} のこと"
            )
    body = "\n".join(lines)
    return f"## 語彙\n\nこの窓口で扱う用語。表記はここに書いた形に揃える。\n\n{body}"


def _render_procedure(procedure: Procedure) -> str:
    """手順の節。procedure は明示指定されたものだけが渡るので、見出しは常に出す。"""
    blocks: list[str] = [f"## 手順: {procedure.name}"]
    if procedure.trigger:
        blocks.append(f"対象: {procedure.trigger}")
    if procedure.steps:
        steps = "\n".join(f"{i}. {step}" for i, step in enumerate(procedure.steps, start=1))
        blocks.append(steps)
    if procedure.guardrails:
        guardrails = "\n".join(f"- {g}" for g in procedure.guardrails)
        blocks.append(f"守ること:\n{guardrails}")
    return "\n\n".join(blocks)


def _render_channel(channel: Channel) -> str:
    """チャネルの節。channel は明示指定されたものだけが渡るので、見出しは常に出す。"""
    blocks: list[str] = [f"## チャネル: {channel.name}"]
    if channel.description:
        blocks.append(channel.description)
    if channel.constraints:
        constraints = "\n".join(f"- {c.text}" for c in channel.constraints)
        blocks.append(f"守ること:\n{constraints}")
    if channel.formatting:
        formatting = "\n".join(f"- {key}: {value}" for key, value in channel.formatting.items())
        blocks.append(f"書き方:\n{formatting}")
    return "\n\n".join(blocks)


def _render_governance(governance: Governance | None) -> str:
    if governance is None:
        return ""
    blocks: list[str] = []
    if governance.prohibitions:
        lines = []
        for p in governance.prohibitions:
            line = f"- {p.text}"
            if p.on_violation:
                line += f"（破りそうになったら: {p.on_violation}）"
            lines.append(line)
        blocks.append("\n".join(lines))
    if governance.escalation:
        lines = []
        for e in governance.escalation:
            line = f"- {e.when} → {e.action}"
            if e.say:
                line += f"（「{e.say}」と伝える）"
            lines.append(line)
        blocks.append("引き継ぎ:\n" + "\n".join(lines))
    if governance.out_of_scope:
        blocks.append(f"範囲外の問い合わせには次のように答える:\n{governance.out_of_scope}")
    if not blocks:
        return ""
    return "## 禁止事項\n\n" + "\n\n".join(blocks)


def _substitute_vars(text: str, vars: Mapping[str, str]) -> str:
    """連結済みの text に対して1度だけ変数展開する。未解決や不正な書式は BuildError にする。"""
    tpl = Template(text)
    missing = sorted(set(tpl.get_identifiers()) - set(vars))
    if missing:
        names = ", ".join(missing)
        raise BuildError(
            f"未解決の変数がある: {names}（本文に金額などで $ を書きたい場合は $$ と書く）"
        )
    try:
        return tpl.substitute(vars)
    except ValueError as exc:
        raise BuildError(
            f"変数の書式が不正: {exc}（$ を文字として書きたい場合は $$ と書く）"
        ) from exc


def _build_sources(
    layers: LoadedLayers,
    channel: Channel | None,
    procedures: Sequence[Procedure],
) -> list[SourceRef]:
    """build に実際に使われたレイヤーファイルの一覧を、節の並びと同じ順で返す。"""
    sources: list[SourceRef] = []
    if layers.role is not None:
        sources.append(
            SourceRef(
                kind="role",
                name="role",
                path=str(layers.paths["role"]),
                version=layers.role.version,
            )
        )
    if layers.vocabulary is not None:
        sources.append(
            SourceRef(
                kind="vocabulary",
                name="vocabulary",
                path=str(layers.paths["vocabulary"]),
                version=layers.vocabulary.version,
            )
        )
    for procedure in procedures:
        sources.append(
            SourceRef(
                kind="procedure",
                name=procedure.name,
                path=str(layers.paths[f"procedure:{procedure.name}"]),
                version=procedure.version,
            )
        )
    if channel is not None:
        sources.append(
            SourceRef(
                kind="channel",
                name=channel.name,
                path=str(layers.paths[f"channel:{channel.name}"]),
                version=channel.version,
            )
        )
    if layers.governance is not None:
        sources.append(
            SourceRef(
                kind="governance",
                name="governance",
                path=str(layers.paths["governance"]),
                version=layers.governance.version,
            )
        )
    return sources
