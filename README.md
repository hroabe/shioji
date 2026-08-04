# 潮路(shioji)

SSoT文書レイヤ・検証ゲート・自走モードを備えた **AIエージェント駆動開発のプロセスひな型**(copierテンプレート)。仕様(何を作るか)はプロジェクトごとに違っても、規律(どう作るか)は同じ航路を通れるようにする。

- 思想と規則の根拠: [PROCESS.md](PROCESS.md)(本キットのL1)

## 使い方(3ステップ)

### 1. 骨格を写す(機械・決定論)

```sh
pip install copier
copier copy gh:hroabe/shioji my-project
cd my-project && git init && git add -A && git commit -m "chore: 潮路から実体化"
make ci   # ← この時点で緑(0日目から緑の原則)
```

質問はプロジェクト名・REQ接頭辞・スタックの3つだけ。仕様に関する質問はここでは出ない(次のステップの仕事)。

### 2. 仕様を注ぐ(壁打ち=インセプション)

生成されたプロジェクトで、エージェント(Claude Code等)に `INCEPTION_PROMPT.md` を実行させる。仕様ドラフトがあれば取り込み、なければ構造化インタビューで壁打ちする。**出力はすべて docs/proposals/inception/ への提案**であり、エージェントは docs/spec/ と CLAUDE.md を直接書かない。

### 3. 人間が確定し、開発開始

`docs/proposals/inception/APPLY_CHECKLIST.md` に従って人間が仕様と規範を確定したら、`INITIAL_PROMPT.md` の §0(単発)または §1(自走)で tsukishio と同じ運用に入る。

## テンプレート更新の受け取り

導出プロジェクト側で:

```sh
copier update   # .copier-answers.yml が記録した版から差分適用
```

プロジェクト運用で見つかったプロセス改善は、本リポジトリへのPRで還流する(詳細は PROCESS.md §版管理)。

## リポジトリ構成

```
copier.yml          # Stage1 の質問(機械的パラメータのみ)
PROCESS.md          # キット自身の仕様 — 各規則の意図と根拠
template/           # 生成されるプロジェクトの全ツリー
.github/workflows/  # キット自身のCI(ダミー実体化→生成直後に緑を検証)
```

## ライセンス・命名

本キットは [MIT License](LICENSE)。**生成先プロジェクトにはライセンスを自動注入しない** — 各プロダクトのライセンス選定はプロジェクトごとの人間ゲート(PROCESS.md §人間ゲート)であり、キットの原則に従いインセプション/人間が選ぶ。名は澪標・海図・船霊の系譜から「潮路」— 後から続く船のための、潮の道筋。
