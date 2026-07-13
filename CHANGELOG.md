# CHANGELOG — 潮路(shioji)

版管理は SemVer。タグ付け=リリースは人間ゲート(PROCESS.md)。

## [0.1.0] — 2026-07-13(人間承認によりリリース・MITライセンス付与)

初期実装(tsukishio からのプロセス抽出。提案書: tsukishio/docs/proposals/2026-07-12_process_kit_extraction.md)。

- Stage1: copier テンプレート(質問3つ: project_name / req_prefix / stack)
- project.yaml — プロセス設定のSSoT(汎用スクリプトはこれだけを読む)
- 汎用ゲート: check_req_links.py(REQトレーサビリティ)/ validate_oracle.py(オラクル照合・--dry-run/--gate/--selftest)/ run_gates.py(ゲート実行器)
- L0契約テンプレート(CLAUDE.md.jinja — §0/§2/§4/§5 はインセプションスロット)
- INITIAL_PROMPT(単発/自走/再開の3モード)・AGENTS.md・L3三点セット書式
- Stage2: INCEPTION_PROMPT.md(壁打ち→提案生成→人間確定の台本)
- kit-ci: ダミー実体化→生成直後に緑の検証(manual / flutter の2系統)

## [未リリース] — パイロット還流(kenpo-keisan)

- **fix(gate): 提案(docs/proposals)をREQ検査から除外**(project.yaml の `scan_exclude`・既定 `[docs/proposals]`)。パイロット還流#1: インセプション出力がREQ IDを提案すると、仕様適用前は幽霊REQ判定で pre-commit がブロックする問題を修正。提案は下書き(未定義/将来/却下のREQを含み得る)ため除外が正。src/test の幽霊REQ検出は不変(過剰除外なし)。
- **fix(scripts): 同梱 validate_oracle.py の ruff E702 を解消(還流#3)**。セミコロン多重文を分割。Python-stackで実体化し `ruff check .` を通すと同梱スクリプトが赤になる問題。kit-ci に「テンプレ同梱スクリプトの lint」ジョブ + 実体化matrixに `python` を追加し再発防止。
- **docs(release): 配布はタグ依存 — 既知の注意点(還流#2)**。copier 既定は「最新の git タグ」から複製する。リリースタグを GitHub へ push できていないと(本セッションはプロキシがタグ push を403拒否)、①リモートはタグ皆無→`copier copy gh:...` は HEAD 複製(可)、②タグを持つローカルclone は古いタグ内容で複製、という不一致が起きる。対策: リリースタグは必ず GitHub 側で作成(人間ゲート)。再現性が要る実体化は `--vcs-ref=<tag/sha>` を明示。

### v0.2 候補(パイロット還流待ち)
- モジュール条件生成(データ台帳・ゴールデン規約の copier 選択式)
- validate_oracle の整列強化(厳密DP・extra分類 — tsukishio で実証済みの発展形)
