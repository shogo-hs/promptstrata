"""レイヤーをまたぐ検査。

pydantic は1ファイルの中の形しか見ない。ここでは複数のファイルにまたがる矛盾を拾う。
id の重複と語彙の別名衝突は、1ファイルずつ見ている限り絶対に見つからない。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from string import Template
from typing import Any

from .models import LayerFileError, LoadedLayers, load_layers

__all__ = ["lint", "lint_layers", "required_vars"]


def _walk(value: Any, where: str) -> Iterator[tuple[str, str]]:
    """入れ子の中の文字列を (場所, 中身) で全部返す。"""
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(item, f"{where}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for index, item in enumerate(value):
            yield from _walk(item, f"{where}[{index}]")


def _all_texts(layers: LoadedLayers) -> Iterator[tuple[str, str]]:
    named: list[tuple[str, Any]] = [
        ("role", layers.role),
        ("vocabulary", layers.vocabulary),
        ("governance", layers.governance),
    ]
    named += [(f"channels/{name}", ch) for name, ch in sorted(layers.channels.items())]
    named += [(f"procedures/{name}", pr) for name, pr in sorted(layers.procedures.items())]
    for where, model in named:
        if model is not None:
            yield from _walk(model.model_dump(), where)


def required_vars(layers: LoadedLayers) -> set[str]:
    """このレイヤー一式をビルドするのに渡す必要がある変数名。"""
    found: set[str] = set()
    for _, text in _all_texts(layers):
        found |= set(Template(text).get_identifiers())
    return found


def _collect_ids(layers: LoadedLayers) -> dict[str, list[str]]:
    """id -> それが現れた場所の一覧。"""
    seen: dict[str, list[str]] = defaultdict(list)
    if layers.role is not None:
        for principle in layers.role.principles:
            seen[principle.id].append("role.principles")
    if layers.governance is not None:
        for prohibition in layers.governance.prohibitions:
            seen[prohibition.id].append("governance.prohibitions")
    for name, channel in sorted(layers.channels.items()):
        for constraint in channel.constraints:
            seen[constraint.id].append(f"channels/{name}.constraints")
    return seen


def _check_ids(layers: LoadedLayers) -> list[str]:
    problems = []
    for identifier, places in sorted(_collect_ids(layers).items()):
        if len(places) > 1:
            where = ", ".join(places)
            problems.append(f"id '{identifier}' が {len(places)} 箇所で重複している: {where}")
    return problems


def _check_vocabulary(layers: LoadedLayers) -> list[str]:
    """同じ表記が2つの見出し語に紐づいていないか。

    紐づいていると「そらいろペイ は ソライロペイ のこと」と
    「そらいろペイ は ソライロペイカード のこと」が同時にプロンプトに載り、
    モデルがどちらとも取れる状態になる。
    """
    if layers.vocabulary is None:
        return []
    owners: dict[str, set[str]] = defaultdict(set)
    for term in layers.vocabulary.terms:
        for surface in [term.canonical, *term.aliases, *term.misheard]:
            owners[surface].add(term.canonical)
    problems = []
    for surface, canonicals in sorted(owners.items()):
        if len(canonicals) > 1:
            names = ", ".join(sorted(canonicals))
            problems.append(f"語彙の表記 '{surface}' が複数の見出し語に紐づいている: {names}")
    return problems


def _check_vars(layers: LoadedLayers, provided: Mapping[str, str] | None) -> list[str]:
    problems = []
    for where, text in _all_texts(layers):
        template = Template(text)
        try:
            template.substitute(dict.fromkeys(template.get_identifiers(), ""))
        except ValueError:
            problems.append(
                f"{where}: 変数として解釈できない $ がある。"
                "金額などで $ をそのまま出したい場合は $$ と書く"
            )
    if provided is not None:
        missing = sorted(required_vars(layers) - set(provided))
        if missing:
            problems.append("変数が埋まっていない: " + ", ".join(f"${name}" for name in missing))
    return problems


def lint_layers(layers: LoadedLayers, vars: Mapping[str, str] | None = None) -> list[str]:
    """読み込み済みのレイヤーを検査して、問題の一覧を返す。空なら問題なし。"""
    if layers.is_empty():
        return [f"{layers.root}: レイヤーが1つも無い"]
    return _check_ids(layers) + _check_vocabulary(layers) + _check_vars(layers, vars)


def lint(root: str | Path, vars: Mapping[str, str] | None = None) -> list[str]:
    """ディレクトリを読み込んで検査する。読み込みに失敗した場合もその内容を返す。"""
    try:
        layers = load_layers(root)
    except LayerFileError as exc:
        return [str(exc)]
    return lint_layers(layers, vars)
