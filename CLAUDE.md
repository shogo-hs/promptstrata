# CLAUDE.md — promptstrata

カスタマーサポート AI エージェントのシステムプロンプトを、ロール・語彙・ガバナンス・
チャネル・手順の5レイヤーの YAML から合成する Python ライブラリ。PyPI に `promptstrata`
の名前で配布する。Python 3.11+ / uv / ruff / mypy strict / pytest。

## コマンド

| 用途 | コマンド |
|---|---|
| 依存インストール | `uv sync` |
| テスト | `uv run pytest -q` |
| lint・型検査 | `uv run ruff check . && uv run ruff format --check . && uv run mypy src` |
| プロンプト合成 | `uv run promptstrata build examples/sorairo-pay --channel voice` |
| レイヤー間の検査 | `uv run promptstrata lint examples/sorairo-pay` |

## モジュール

| モジュール | 役割 |
|---|---|
| `models.py` | レイヤーの型（`Role` / `Vocabulary` / `Governance` / `Channel` / `Procedure`）と `load_layers` |
| `compose.py` | 各レイヤーの整形と、パーツの逐次連結によるプロンプト合成 |
| `lint.py` | 層をまたぐ検査（`id` の重複・語彙の別名衝突・変数の書式と不足） |
| `cli.py` | `build` / `lint` サブコマンドを持つ `argparse` ベースの CLI |

## 規約

- **依存を増やさない。** pydantic と PyYAML 以外を足すときは ADR を書く。
- **Python 3.11 で動くこと。** PEP 695 のジェネリクス構文（`def f[T]()`）は使わない。
- **設計判断は `docs/adr/` に残す。** 既存の ADR は書き換えず、新しい ADR で置き換える。
- **レイヤーは全て任意。** 新しい整形を足すときも「出すものが無ければ空文字を返す」を
  守る（空の見出しをプロンプトに残さない）。
- **PyPI 配布物なので `py.typed` を消さない**（消すと利用側から型が Any になる）。
- サンプルは `examples/sorairo-pay/` の1式だけ。条件ごとに別ディレクトリを増やさない。

## 設計の背景

レイヤー構成・優先順位・依存の絞り込み・合成方式・固定部と可変部の分離・バージョン管理は、
いずれも `docs/adr/` に理由つきで記録済み。実装を変える前に該当する ADR を読む
（一覧は `docs/adr/README.md`）。

## バージョンとリリース

版の正本は `pyproject.toml` の `version` 1つ（`__version__` は書き写さず読む）。SemVer に従い、
0.x のあいだは minor で破壊的変更が入りうる。公開 API の範囲（合成後のプロンプト本文の文面を
含む）と理由は `docs/adr/0009-versioning.md`。

リリース手順は次のとおり。

1. `CHANGELOG.md` の `## [Unreleased]` の中身を新しい版の節に移し、日付を入れる
2. `pyproject.toml` の `version` を上げる
3. `uv sync` して `uv.lock` を更新し、コミットする
4. `git tag vX.Y.Z` を打ち、`git push origin main --tags` する
5. `.github/workflows/release.yml` が CI と同じ検査を回してから PyPI に上げる
   （タグと `pyproject.toml` の `version` が食い違う場合は落ちる）
