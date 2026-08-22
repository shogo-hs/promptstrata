"""コマンドライン。``build`` と ``lint`` の2つだけ。

``build`` は合成したプロンプトを標準出力に出す。そのままファイルに落とせるよう、
fingerprint などの付随情報は標準エラーに出す。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .compose import BuildError, PromptSet
from .lint import lint, required_vars
from .models import LayerFileError, load_layers

__all__ = ["main"]


def _parse_var(item: str) -> tuple[str, str]:
    key, sep, value = item.partition("=")
    if not sep or not key:
        raise argparse.ArgumentTypeError(f"--var は KEY=VALUE の形で渡す: {item!r}")
    return key, value


def _add_var(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        dest="variables",
        type=_parse_var,
        metavar="KEY=VALUE",
        help="本文の $KEY を埋める値。複数指定できる",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptstrata",
        description="レイヤーごとの YAML からシステムプロンプトを合成する",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="レイヤーを合成してシステムプロンプトを出す")
    build.add_argument("root", help="レイヤー YAML を置いたディレクトリ")
    build.add_argument(
        "--channel",
        default=None,
        help="使うチャネル名。省略するとチャネルの節を出さない",
    )
    build.add_argument(
        "--procedure",
        action="append",
        default=[],
        dest="procedures",
        metavar="NAME",
        help="載せる手順の名前。複数指定できる。省略すると手順の節を出さない",
    )
    _add_var(build)

    lint_cmd = sub.add_parser("lint", help="レイヤーをまたぐ矛盾を検査する")
    lint_cmd.add_argument("root", help="レイヤー YAML を置いたディレクトリ")
    _add_var(lint_cmd)

    return parser


def _cmd_build(args: argparse.Namespace) -> int:
    try:
        prompt_set = PromptSet.load(args.root)
        built = prompt_set.build(
            channel=args.channel,
            procedures=args.procedures or None,
            vars=dict(args.variables),
        )
    except (LayerFileError, BuildError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(built.text)
    print(f"fingerprint: {built.fingerprint}", file=sys.stderr)
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    provided = dict(args.variables) if args.variables else None
    problems = lint(args.root, vars=provided)
    if problems:
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        print(f"{len(problems)} 件の問題", file=sys.stderr)
        return 1
    # ここまで来ていれば読み込みは成功している。
    needed = sorted(required_vars(load_layers(args.root)))
    if needed:
        print("必要な変数: " + ", ".join(f"${name}" for name in needed))
    print("問題なし")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "build":
        return _cmd_build(args)
    return _cmd_lint(args)


if __name__ == "__main__":
    sys.exit(main())
