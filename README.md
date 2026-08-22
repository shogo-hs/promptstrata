# promptstrata

カスタマーサポート AI エージェントのシステムプロンプトを、5枚の YAML レイヤーから1本の文字列に合成するライブラリです。

カスタマーサポートのシステムプロンプトは、要件を継ぎ足すたびに1本の巨大な文字列になっていきます。禁止事項、話し方のルール、電話とチャットでの違い、返金のような業務手順が同じファイルに混ざり、誰も全体を把握できなくなります。担当が違う人が同じファイルを編集すれば衝突しますし、電話向けの制約をチャットにも誤って持ち込む、といった事故も起きます。promptstrata は、この1本の文字列を「誰として振る舞うか」「用語」「禁止事項」「チャネル」「業務手順」の5レイヤーに分けて YAML で管理し、必要な組み合わせだけをビルド時に合成します。LLM 自体は呼ばず、文字列を組み立てるだけのライブラリです。

## インストール

```
pip install promptstrata
```

```
uv add promptstrata
```

## 最小の使い方

```python
from promptstrata import PromptSet

ps = PromptSet.load("examples/sorairo-pay")
built = ps.build(
    channel="voice",
    procedures=["refund"],
    vars={"company_name": "ソライロ決済株式会社"},
)

system_prompt = built.text  # そのままシステムプロンプトに渡す
print(built.fingerprint)  # 例: "a817c6ad1e90"。応対ログに残してどのプロンプトか特定する
```

## 5つのレイヤー

| レイヤー | ファイル | 何を書くか | 個数 |
|---|---|---|---|
| ロール | `role.yaml` | 誰として振る舞うか（identity）、あるべき振る舞い（principles）、話し方（tone） | ファイルにつき1つ |
| 語彙 | `vocabulary.yaml` | 扱うサービス名・用語（canonical・読み・別名・音声認識の誤変換） | terms を複数件 |
| ガバナンス | `governance.yaml` | 禁止事項（prohibitions）、引き継ぎ条件（escalation）、範囲外の断り文句（out_of_scope） | 各項目を複数件 |
| チャネル | `channels/<name>.yaml` | 媒体ごとの制約（constraints）と表記ルール（formatting） | チャネルの数だけファイル |
| 手順 | `procedures/<name>.yaml` | 業務手順の発動条件（trigger）、手順（steps）、逸脱を防ぐ制約（guardrails） | 手順の数だけファイル |

すべてのレイヤーは任意です。ファイルが無いレイヤーは無いものとして扱われます。

## ディレクトリ構成の例

`examples/sorairo-pay` は、架空のコード決済サービス「ソライロペイ」のカスタマーサポート窓口を題材にしたサンプルです。実在の企業・サービスとは関係ありません。

```
examples/sorairo-pay/
├── role.yaml
├── vocabulary.yaml
├── governance.yaml
├── channels/
│   ├── voice.yaml
│   └── chat.yaml
└── procedures/
    └── refund.yaml
```

## 各レイヤーの YAML 例

以下は `examples/sorairo-pay/` からの抜粋です。**架空のサービス「ソライロペイ」を題材にしたサンプル**で、実在の企業・サービスとは関係ありません。

### role.yaml

`${company_name}` はビルド時に `vars` で埋める変数です。`$company_name` とも書けますが、日本語の文中では直後の文字と続けて書ける `${...}` のほうが確実です。本文に `$` をそのまま出したい場合は `$$` と書きます。

**`vars` に顧客の個人情報を入れないでください。** 企業名・窓口名・営業時間のような、その窓口で固定の値だけに使います。氏名を入れると `built.text` が顧客ごとに変わり、`fingerprint` も顧客ごとに一意になるため「どのポリシーで応対したか」を横断で集計できなくなります。システムプロンプトのログも個人情報を含む扱いになり、保管と共有の条件が変わります。

```yaml
identity: |-
  あなたは${company_name}が提供するソライロペイのカスタマーサポート窓口担当です。
  ソライロペイアプリ、ソライロペイ残高、ソライロポイントに関する問い合わせに対応します。
principles:
  - id: verify_before_payment
    text: 返金や重複請求など金銭が動く申告は、注文番号や取引日時などの裏付けを確認してから対応する
tone: 丁寧だが事務的になりすぎない。落ち着いた低めのトーンで、誠実に淡々と話す。
```

### vocabulary.yaml

`misheard` は音声認識が実際に誤変換しそうな表記です。ここに載せることで、モデルが会話履歴中の誤変換を正しい語に読み替えられるようにします。

```yaml
terms:
  - canonical: ソライロペイ
    reading: ソライロペイ
    summary: コード決済サービス。バーコードやQRコードで加盟店にて支払いができる。
    aliases:
      - そらいろペイ
      - sorairo pay
    misheard:
      - 空色ペイ
      - ソライロペー
      - ソラエロペイ
```

### governance.yaml

```yaml
prohibitions:
  - id: no_smalltalk
    text: 雑談を始めない。世間話や不要な相槌を返さず、要件の解決に集中する
escalation:
  - when: 本人確認が取れない
    action: 有人窓口（電話サポート）に引き継ぐ
    say: 本人確認ができないため、担当者にお繋ぎします
out_of_scope: ソライロペイ以外のサービスに関するお問い合わせは担当外のためご案内できません。各サービスの窓口にご確認ください。
```

### channels/voice.yaml と channels/chat.yaml

同じ「返金の手順を伝える」場面でも、チャネルによって制約は変わります。voice には「URL を読み上げない」を必ず入れ、chat には入れません。

```yaml
# channels/voice.yaml
constraints:
  - id: no_url_readout
    text: URLやメールアドレス、記号列を読み上げない。案内が必要な場合はSMSでURLを送る
  - id: two_sentences_max
    text: 1回の発話は2文以内にまとめる
formatting:
  金額: 金額は「1,000円」ではなく「せんえん」のように読み上げの形で伝える
```

```yaml
# channels/chat.yaml
constraints:
  - id: url_ok
    text: URLはそのまま貼ってよい
  - id: numbered_steps
    text: 手順は番号付きの箇条書きにする
formatting:
  リンク: URLはそのままの形式で貼り付ける
```

### procedures/refund.yaml

```yaml
trigger: 返金、返品、二重請求の申告を受けたとき
steps:
  - 注文番号または取引日時、支払い方法を確認する
  - 本人確認を行う（本人確認ツールに登録氏名または生年月日を照会し、一致の結果を得る。顧客が名乗っただけの氏名・生年月日は本人確認の完了とみなさない）
guardrails:
  - 金額を独断で変更・確約しない。システムで確認できた金額のみを伝える
```

## 合成の規則

節の順序は次のとおりです。

```
優先順位 → 役割 → 語彙 → 手順 → チャネル → 禁止事項
```

節の並びと、制約の強さの優先順位は別です。優先順位はこの順で強くなります。

```
語彙 < 役割 < 手順 < チャネル < 禁止事項
```

強い制約ほど後ろに置いたうえで、冒頭でもこの優先順位を宣言します。モデルは長いプロンプトの末尾を重く扱う傾向があるため、順序と優先順位の宣言の両方で衝突時の勝ち負けを明示します。

レイヤーはすべて任意です。ファイルが無ければその層は無いものとして扱い、空の見出しは残しません。ただし `--channel voice` のように明示したチャネルのファイルが無い場合はエラーにします。存在しないレイヤーを暗黙に省くことと、指定を間違えたことは区別する必要があるためです。

## 会話中に判明したことは書き戻さない

`built.text` はビルド時に一度決まる固定の文字列です。会話が進んでも作り直さず、そのままシステムプロンプトとして渡してキャッシュさせてください。

本人確認が済んだ氏名や、契約から引いた注文番号のような会話中に確定する事実は、promptstrata の合成対象ではありません。**システムプロンプトの末尾に足さないでください。**

```
tools ──▶ system ──▶ messages [過去のターン …… 最新ターン]
```

プロンプトキャッシュはこの順の前方一致で効き、ある段が変わるとそれ以降の段のキャッシュも落ちます。Anthropic の仕様では "Changes at each level invalidate that level and all subsequent levels" と明記されています（[Prompt caching](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching)）。OpenAI も前方一致です。つまりシステムプロンプトの末尾を毎ターン書き換えると、それ以降の会話履歴のキャッシュが丸ごと落ちます。会話が伸びるほど再計算する量が増え、音声チャネルではそのままターンごとの応答遅延になります。

事実を反映したい場合は `messages` 側に足してください。整形と配線は利用側で組みます。基盤ごとに経路が違うためです。

| 基盤 | 事実を足す経路 |
|---|---|
| Pipecat | `LLMMessagesAppendFrame` でメッセージ履歴に追記する（[Context Management](https://docs.pipecat.ai/pipecat/learn/context-management)。システムメッセージの書き換えは信頼性が低いと明記されている） |
| LiveKit Agents | chat context の末尾に追記する（[Anthropic プラグイン](https://docs.livekit.io/reference/python/livekit/plugins/anthropic/index.html)） |
| Retell・Vapi | dynamic variables かツールの戻り値で渡す |

そもそも、客が口頭で名乗った氏名はモデルが会話履歴からすでに読めています。書き戻す必要があるのは「ツールで裏が取れた」という印が要る事実だけです。

`role.yaml` や `governance.yaml` に書くのは、事実そのものではなく事実の扱い方です。「確認済みと明示された事実だけを既知として扱う」「複数ある場合は会話履歴の最後のものを最新とする」といった規律をレイヤーに書いておけば、事実がどこから来ても振る舞いは揃います。

ただし、**これはモデルへの指示であって強制ではありません。** 本人確認が済んでいない状態で返金の操作が実行されるのを確実に止めたい場合は、ツール呼び出しの可否を判定する実行時のガードレール（NeMo Guardrails・Guardrails AI・OpenAI Agents SDK など。このライブラリの対象外）で止めてください。プロンプトは会話を導く指示であって、制御ではありません。

## CLI

```
promptstrata build examples/sorairo-pay --channel voice --procedure refund --var company_name=ソライロ決済株式会社
promptstrata lint examples/sorairo-pay
```

`build` は合成したプロンプトを標準出力に書きます。`lint` は YAML のスキーマ違反に加えて、`id` の重複（レイヤー横断）や `aliases` の衝突（同じ別名が2つの `canonical` に属する）を検出します。

## やらないこと

| やらないこと | 代わりに |
|---|---|
| STT の keyterm・カスタム語彙の出力 | STT 側の設定で持つ |
| プロンプトのレジストリ・Web UI・版管理サーバー | git。必要なら Langfuse |
| 実行時ガードレール（出力の検査とブロック） | NeMo Guardrails / Guardrails AI / OpenAI Agents SDK |
| eval・A/Bテスト | promptfoo |
| LLM の呼び出し | 呼ばない。文字列を返すだけ |
| テンプレートエンジン | `string.Template`（標準ライブラリ） |

## バージョンとリリース

版は `pyproject.toml` の `version` だけです。SemVer に従いますが、0.x のあいだは minor（例: 0.2.0）で破壊的変更が入ることがあります。1.0 以降は破壊的変更を major に限ります。

公開 API として扱うのは、`PromptSet` / `BuiltPrompt` / `SourceRef` などの型とそのフィールド・メソッド、例外（`PromptStrataError` / `LayerFileError` / `BuildError`）、レイヤーの型（`Role` / `Vocabulary` / `Governance` / `Channel` / `Procedure`）、レイヤー YAML のスキーマ、CLI のサブコマンドとオプション（`build` / `lint` / `--channel` / `--procedure` / `--var`）、そして**合成後のプロンプト本文の文面**です。文面を変えると `built.fingerprint` も変わり、過去の応対ログと突き合わせられなくなるため、意味が変わる変更は破壊的変更として扱います。誤字の修正のように意味が変わらない変更は patch で構いません。理由は [docs/adr/0009-versioning.md](docs/adr/0009-versioning.md) を参照してください。

変更履歴は [CHANGELOG.md](CHANGELOG.md) に Keep a Changelog 形式で記録します。

リリース手順（メンテナ向け）は次のとおりです。

1. `CHANGELOG.md` の `## [Unreleased]` の中身を新しい版の節に移し、日付を入れます。
2. `pyproject.toml` の `version` を上げます。
3. `uv sync` して `uv.lock` を更新し、コミットします。
4. `git tag vX.Y.Z` を打ち、`git push origin main --tags` します。
5. `.github/workflows/release.yml` が CI と同じ検査を回してから PyPI に公開します（タグと `pyproject.toml` の `version` が食い違う場合は失敗します）。
