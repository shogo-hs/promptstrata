"""層をまたぐ検査のテスト。

pydantic が1ファイル内で拾える誤りではなく、複数ファイルにまたがる矛盾を確かめる。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from promptstrata.lint import lint, lint_layers, required_vars
from promptstrata.models import LayerFileError, load_layers

ROLE = """\
kind: role
identity: あなたは $company_name のサポート担当です。
principles:
  - id: verify_first
    text: 支払いの操作の前に本人確認を行う
tone: 丁寧に、短く。
"""

GOVERNANCE = """\
kind: governance
prohibitions:
  - id: no_smalltalk
    text: 雑談を始めない
out_of_scope: そのご質問はこちらでは承っておりません。
"""

VOCABULARY = """\
kind: vocabulary
terms:
  - canonical: ソライロペイ
    reading: ソライロペイ
    summary: コード決済サービス
    aliases: [そらいろペイ]
    misheard: [空色ペイ]
"""


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_clean_set_has_no_problems(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", ROLE)
    write(tmp_path, "governance.yaml", GOVERNANCE)
    write(tmp_path, "vocabulary.yaml", VOCABULARY)
    assert lint(tmp_path, vars={"company_name": "ソライロ決済株式会社"}) == []


def test_empty_directory_is_reported(tmp_path: Path) -> None:
    problems = lint(tmp_path)
    assert len(problems) == 1
    assert "レイヤーが1つも無い" in problems[0]


def test_duplicate_id_across_layers(tmp_path: Path) -> None:
    # 同じ id が役割と禁止事項の両方にある。1ファイルずつ見ても見つからない誤り。
    write(tmp_path, "role.yaml", ROLE.replace("verify_first", "shared_id"))
    write(tmp_path, "governance.yaml", GOVERNANCE.replace("no_smalltalk", "shared_id"))
    problems = lint(tmp_path, vars={"company_name": "ソライロ決済株式会社"})
    assert any("shared_id" in p and "重複" in p for p in problems)


def test_alias_collision_between_terms(tmp_path: Path) -> None:
    write(
        tmp_path,
        "vocabulary.yaml",
        """\
kind: vocabulary
terms:
  - canonical: ソライロペイ
    aliases: [そらいろペイ]
  - canonical: ソライロペイカード
    aliases: [そらいろペイ]
""",
    )
    problems = lint(tmp_path)
    assert any("そらいろペイ" in p and "複数の見出し語" in p for p in problems)


def test_canonical_used_as_another_terms_alias(tmp_path: Path) -> None:
    write(
        tmp_path,
        "vocabulary.yaml",
        """\
kind: vocabulary
terms:
  - canonical: ソライロペイ
  - canonical: ソライロポイント
    misheard: [ソライロペイ]
""",
    )
    assert any("ソライロペイ" in p for p in lint(tmp_path))


def test_malformed_placeholder_is_reported(tmp_path: Path) -> None:
    # $1000 は変数名として解釈できない。$$ と書かないとビルドで必ず落ちる。
    write(tmp_path, "role.yaml", "kind: role\nidentity: 上限は $1000 円です。\n")
    problems = lint(tmp_path)
    assert any("$$" in p for p in problems)


def test_missing_var_is_reported_only_when_vars_given(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", ROLE)
    assert lint(tmp_path) == []  # vars を渡さなければ「足りない」とは言えない
    problems = lint(tmp_path, vars={})
    assert any("$company_name" in p for p in problems)


def test_required_vars_lists_every_placeholder(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", ROLE)
    write(
        tmp_path, "governance.yaml", GOVERNANCE.replace("雑談を始めない", "$desk_name の話をしない")
    )
    assert required_vars(load_layers(tmp_path)) == {"company_name", "desk_name"}


def test_unknown_key_is_rejected_by_schema(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", "kind: role\nidentitiy: 打ち間違えたキー\n")
    problems = lint(tmp_path)
    assert len(problems) == 1
    assert "identitiy" in problems[0]


def test_broken_yaml_is_reported(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", "kind: role\n  identity: [壊れている\n")
    assert lint(tmp_path) != []


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(LayerFileError):
        load_layers(tmp_path / "ない")


def test_lint_layers_accepts_already_loaded(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", ROLE)
    assert lint_layers(load_layers(tmp_path), vars={"company_name": "ソライロ決済株式会社"}) == []
