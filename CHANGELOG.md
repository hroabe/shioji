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

### v0.2 候補(パイロット還流待ち)
- モジュール条件生成(データ台帳・ゴールデン規約の copier 選択式)
- validate_oracle の整列強化(厳密DP・extra分類 — tsukishio で実証済みの発展形)
