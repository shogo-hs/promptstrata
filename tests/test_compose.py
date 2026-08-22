"""合成と CLI のテスト。

レイヤーが欠けたときに空の節が残らないことと、明示指定のミスを黙って無視しないことが要点。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from promptstrata import BuildError, PromptSet
from promptstrata.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "sorairo-pay"
VARS = {"company_name": "ソライロ決済株式会社"}

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
"""


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def heading_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("## ")]


# --- レイヤーが欠けているとき --------------------------------------------------


def test_single_layer_leaves_no_empty_sections(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", ROLE)
    text = PromptSet.load(tmp_path).build(vars=VARS).text

    assert heading_lines(text) == ["## 役割"]
    assert "優先順位" not in text  # ぶつかる相手がいないので順位の節ごと出さない
    assert text == text.strip()  # 先頭・末尾に余分な空行が無い
    assert "\n\n\n" not in text  # 空の節が抜けた跡が残っていない


def test_precedence_lists_only_present_layers(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", ROLE)
    write(tmp_path, "governance.yaml", GOVERNANCE)
    text = PromptSet.load(tmp_path).build(vars=VARS).text

    numbered = [line for line in text.splitlines() if line[:2] in ("1.", "2.", "3.", "4.", "5.")]
    assert numbered == ["1. 禁止事項（ガバナンス）", "2. 役割"]


def test_empty_layer_fields_are_dropped(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", "kind: role\nidentity: 担当者です。\n")
    text = PromptSet.load(tmp_path).build().text
    assert "守ること" not in text
    assert "話し方" not in text


def test_directory_without_any_layer_raises(tmp_path: Path) -> None:
    with pytest.raises(BuildError):
        PromptSet.load(tmp_path).build()


# --- チャネルと手順 ------------------------------------------------------------


def test_channel_changes_the_output() -> None:
    prompt_set = PromptSet.load(EXAMPLES)
    voice = prompt_set.build(channel="voice", vars=VARS).text
    chat = prompt_set.build(channel="chat", vars=VARS).text

    assert "読み上げない" in voice
    assert "読み上げない" not in chat
    assert voice != chat


def test_unknown_channel_is_an_error_not_a_silent_skip() -> None:
    with pytest.raises(BuildError, match="sms"):
        PromptSet.load(EXAMPLES).build(channel="sms", vars=VARS)


def test_unknown_procedure_is_an_error() -> None:
    with pytest.raises(BuildError, match="unknown"):
        PromptSet.load(EXAMPLES).build(procedures=["unknown"], vars=VARS)


def test_omitting_channel_is_not_an_error() -> None:
    text = PromptSet.load(EXAMPLES).build(vars=VARS).text
    assert not any(line.startswith("## チャネル") for line in text.splitlines())


def test_section_order_is_fixed() -> None:
    text = PromptSet.load(EXAMPLES).build(channel="voice", procedures=["refund"], vars=VARS).text
    headings = heading_lines(text)
    assert headings[0] == "## 規則の優先順位"
    assert headings[1] == "## 役割"
    assert headings[2] == "## 語彙"
    assert headings[3].startswith("## 手順")
    assert headings[4].startswith("## チャネル")
    assert headings[5] == "## 禁止事項"


# --- 変数 ----------------------------------------------------------------------


def test_missing_var_stops_the_build() -> None:
    with pytest.raises(BuildError, match="company_name"):
        PromptSet.load(EXAMPLES).build(channel="voice")


def test_double_dollar_is_an_escape(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", "kind: role\nidentity: 上限は $$1000 です。\n")
    assert "$1000" in PromptSet.load(tmp_path).build().text


def test_malformed_placeholder_stops_the_build(tmp_path: Path) -> None:
    write(tmp_path, "role.yaml", "kind: role\nidentity: 上限は $1000 です。\n")
    with pytest.raises(BuildError):
        PromptSet.load(tmp_path).build()


# --- 出力の同一性 ------------------------------------------------------------


def test_fingerprint_tracks_the_content() -> None:
    prompt_set = PromptSet.load(EXAMPLES)
    a = prompt_set.build(channel="voice", vars=VARS)
    b = prompt_set.build(channel="voice", vars=VARS)
    c = prompt_set.build(channel="chat", vars=VARS)
    assert a.fingerprint == b.fingerprint
    assert a.fingerprint != c.fingerprint
    assert len(a.fingerprint) == 12


def test_sources_name_every_layer_used() -> None:
    built = PromptSet.load(EXAMPLES).build(channel="voice", procedures=["refund"], vars=VARS)
    kinds = [source.kind for source in built.sources]
    assert kinds == ["role", "vocabulary", "procedure", "channel", "governance"]
    assert all(Path(source.path).exists() for source in built.sources)


# --- CLI -----------------------------------------------------------------------


def test_cli_build_writes_the_prompt_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["build", str(EXAMPLES), "--channel", "voice", "--var", "company_name=ソライロ決済株式会社"]
    )
    out = capsys.readouterr()
    assert code == 0
    assert "## 役割" in out.out
    assert "fingerprint:" in out.err  # 標準出力はプロンプトだけにする


def test_cli_build_fails_on_unknown_channel(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["build", str(EXAMPLES), "--channel", "sms", "--var", "company_name=ソライロ決済株式会社"]
    )
    assert code == 1
    assert "sms" in capsys.readouterr().err


def test_cli_lint_passes_on_the_example(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["lint", str(EXAMPLES)])
    out = capsys.readouterr()
    assert code == 0
    assert "問題なし" in out.out
    assert "$company_name" in out.out


def test_cli_lint_reports_problems(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path, "role.yaml", ROLE.replace("verify_first", "shared_id"))
    write(tmp_path, "governance.yaml", GOVERNANCE.replace("no_smalltalk", "shared_id"))
    code = main(["lint", str(tmp_path), "--var", "company_name=ソライロ決済株式会社"])
    assert code == 1
    assert "shared_id" in capsys.readouterr().err


def test_cli_rejects_malformed_var() -> None:
    with pytest.raises(SystemExit):
        main(["build", str(EXAMPLES), "--var", "company_name"])
