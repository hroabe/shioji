# proposals — L1(仕様)への変更提案・インセプション出力の置き場

エージェントは docs/spec/* と CLAUDE.md を直接編集しない。変更したい場合は本ディレクトリに提案文書を作成する。

- **仕様変更提案**: `<日付>_<slug>.md`。必須項目: 対象REQ / 現行の記述 / 変更案 / 根拠(実装知見・計測値) / 影響範囲(REQ・タスク・テスト)。
- **インセプション出力**: `inception/` 配下(INCEPTION_PROMPT.md §B の6ファイル。front-matter は status: draft)。

マージ判断と仕様書・CLAUDE.md への反映は人間のみが行う。
