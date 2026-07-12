# CLAUDE.md — 潮路(shioji)キット開発の契約

本リポジトリは**プロセスひな型そのもの**である。ここで作業するエージェントは以下に従う。

1. **規範は PROCESS.md** — 本キットのL1。テンプレートの規則を変えたい場合、まず PROCESS.md との整合を確認し、変更理由を PR 説明に書く。PROCESS.md 自体の編集は人間のみ(提案は Issue / PR コメントで)。
2. **template/ 配下は製品であり、本リポジトリの契約ではない** — `template/CLAUDE.md.jinja` は生成先プロジェクトの契約。本リポジトリでの作業ルールと混同しない。
3. **実体化テストが精度ゲート** — template/ または copier.yml を変更したら、ローカルでダミー実体化(kit-ci.yml と同じ手順)を行い、生成直後の `python scripts/run_gates.py --all` が緑であることを確認してからコミットする。「0日目から緑」を壊す変更は不合格。
4. **スクリプト変更は selftest 併走** — scripts/validate_oracle.py 等の汎用スクリプトを変更したら --selftest を更新・実行する。
5. **人間ゲート** — リリースタグ付け(SemVer)、ライセンス選定、PROCESS.md の規則変更の確定。
6. **後方互換** — 導出プロジェクトは `copier update` で追随する。破壊的変更(質問の削除・ファイル改名)は CHANGELOG.md に移行手順を書き、メジャー版を上げる提案とする。
