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

## [0.2.3] — 2026-08-26

### 再レビュー反映

- **タグの木を検査する**: 従来の整合テストは「最新タグ名の見出しが main の CHANGELOG に
  あるか」しか見ず、v0.2.2(v0.2.1 と同一コミット)のように**タグの中身が見出しと食い違う**
  状態を通した。タグが指す木の CHANGELOG にその版の見出しがあることを各タグに求める。
  だから見出しは**タグの前に確定**し、その見出しを含むコミットにタグを打つ(順序が逆だと
  当のテストが赤になる)。main で「欠陥」と記録したタグは免除(動かさない方針)。
  v0.2.2 以前は規則の導入前のため対象外
- **依存追加の契約矛盾を解消**: INITIAL_PROMPT が「requirements.txt へ理由付き追記+
  インストール」を指示したまま残っていた。CLAUDE.md §8(新規依存の追記は人間ゲート・
  P0-9)と真っ向から矛盾し、供給網上もっとも重要な矛盾だった。既存依存の再インストール
  のみ自律、新規依存は追記せず ISSUE→blocked、へ揃えた。横断テストで検出する
- **実機確認の再利用を塞いだ**: 確認を追加したコミットも base..HEAD に限定。従来は
  履歴全体から探しており、タスクが todo だった頃の古い人間確認で、今回の done が
  通っていた
- **PROCESS.md のゴールデン規範を修正**: §8 人間ゲートの一覧に「初回生成は自律可」が
  残っていた(原本だけ古く、生成先は正しかった)。初回生成を含めて人間ゲートに統一
- **ordered照合の目的関数**: 窓内の対応数だけを最大化すると、遠い2対応(両方不合格)が
  近い1対応(合格)に勝つ偽陰性があった。**許容内の対応数 → 窓内の対応数 → |Δ|合計**の
  辞書式に変更。DP の best を2行・choice を1バイト/セルにし、n×m の上限を宣言して
  超過は赤にする(黙ってメモリ不足で落ちない)

## [0.2.2] — 欠陥タグ(使用しない)

タグ `v0.2.2` は **`v0.2.1` と同一コミット(`d1f207c`)を指しており**、v0.2.2 として
計画した改善を一切含まない。公開済みタグは動かさない方針とし、改善はすべて
**0.2.3** に収録する。`copier copy` / `copier update` は `--vcs-ref=v0.2.3`
(タグ付け後)を使うこと。既定(最新タグ)が v0.2.3 になるまで、既定実行は v0.2.1 相当
の内容を返す。


### 破壊的変更 — オラクルのディレクトリをリポジトリ内に封じ込め（v0.2.2 §2）

`predictions_dir` / `reference_dir` に絶対パス・`..`・ルートそのものを指定できなく
なった。予測の再生成は `predictions_dir` の `*.csv` を削除するため、外を指せると
**リポジトリ外のCSVを削除できた**。設定検査と、削除直前の再検査の両方で塞ぐ
（単体実行は設定検査を通った前提にできない）。拒否時は何も削除せず赤。

### ゲート本体を保護対象に（v0.2.2 §3）

`scripts/` の検査群・`run_gates.py`・pre-commit・CIワークフロー・プロセス写し・
`Makefile` を既定の `protected.paths` に追加。保護集合がこれらを覆っていなければ
設定検査が赤にする。**この検出は自己参照的で素朴な改変にしか効かない** —
実効的な強制は CODEOWNERS + 必須レビュー（T-004。所有者は人間が実値を設定し、
直接push拒否を実測するまで done にしない）。`migrate_config` は既存の独自パスを
保持したまま不足の中核だけ追記する。

### インセプションから開発への遷移を閉じた（v0.2.2 §4）

§C を10手順に組み直した。`requirements.active_spec`・スタック設定（manual 含む）を
反映対象に明記し、**`lifecycle.phase: development` への切替（人間のみ）を最後に**
置いた。従来はこの切替が手順に無く、INITIAL_PROMPT に進むと T-001 の manifest
作成が inception として赤になる行き止まりだった。
「規範カタログの要点は§Cに転載」という誤参照も除去（§C は反映チェックリスト。
カタログを問うのは §A）。

### INITIAL_PROMPT を契約に一致させた（v0.2.2 目標4）

- 「状態不明なら `wip:` としてコミット」の指示を除去。**§3.5-6.5（素性の分から
  ない変更をコミットしない）と矛盾していた**。素性確認を独立の起動手順にし、
  素性不明なら何もコミットせず ISSUES.md だけを記帳して人間に返す
- ブランチ作成を §3.5-1 の識別子込み形式へ（#10 で直した衝突形式の3箇所目）
- kit テストを CLAUDE 限定からテンプレート全文書の走査へ一般化
- 起票先の場合分け(レビュー指摘): ISSUES.md 自体が汚れているときは add せず、
  リポジトリに書かずに人間へ報告して停止する(汚れたファイルを add すれば
  素性不明の編集ごとコミットすることになる)

### ゴールデン基準の README を同梱（v0.2.2 目標7）

`CLAUDE.md` が参照する `test/golden/README.md` がテンプレートに存在しなかった。
人間ゲートの規則（初回生成も更新も人間・基準が無ければ blocked・skip にしない）を
書いた README を同梱し、参照を実体化した。

### タグと CHANGELOG の整合を機械検査（v0.2.2 目標7）

「タグを打ったのに CHANGELOG は未リリースのまま」を v0.2.0 と v0.2.1 で2回
繰り返した。最新タグ `vX.Y.Z` に対応する `## [X.Y.Z]` 見出しが無ければ kit の
テストが赤になる（タグを取得できない浅いcloneでは skip）。

### 実機確認の帰属（v0.2.2 目標6）

「確認:」は自由記入の文字列で、エージェント自身が書けてしまった。確認状態が
成立した(無い→有る)コミットが **`Agent:` トレーラを持たない**ことを履歴で
確かめる。エージェントが3行記帳し、人間が確認の行を**別コミット**で足す分担。
作業ツリーに書いただけの確認は数えない(履歴に入って初めて痕跡になる)。
トレーラを書かない偽装は検出できない — 早期検出＋紙の契約(§3.5-6.5 と同じ)。
帰属は履歴で、**存在は現在のファイルで**見る — 履歴だけだと、人間の確認を後から
削除しても集合に残り続け、記録が無いのに通ってしまう(レビュー指摘)。

### ordered照合を全体最適に（v0.2.2 目標5・旧P1-10）

貪欲+1手先読みは局所最適に落ちる。実例: 参照 `[0, 2]`・予測 `[-1, 0]`・窓2 で、
先読みが p0 を extra へ送って1対応で終わる（最適は2対応）。動的計画法で
**対応数最大 → |Δ|合計最小**を選ぶ。同点の分解は 対応 > extra > missing の
固定順で決定論的。従来も決定論的ではあった — 直したのは局所最適性。
既存の selftest 11ケースは結果不変（単純ケース互換）。貪欲が誤る系列を
selftest 2件と pytest 1件に固定した（互換の主張自体を検査する）。

## [0.2.1] — 2026-08-26(タグ付け済み)

- **fix(docs): 規範カタログの番号衝突を直す(N6→N9)**。§6 の表は N6=商業倫理 を
  定義済みで、v0.2.0 で追加した構造規範の見出しが同じ番号を名乗っていた。
  構造規範は **N9** へ改番し、カタログ表に N9 の行を足した(標準装備)。
  番号の重複はテストで検査する(tests/test_kit_consistency.py)
- **fix(deps): template/requirements.txt の pyyaml を 6.0.2 に固定**。
  再現性を要求する側が固定していなかった(P1-14 の残件)
- **docs: PROCESS.md の front-matter を version 0.2 / 2026-08-26 に更新**
- **docs: S2スロットと INCEPTION_PROMPT の参照を同梱の写しへ**(生成元参照の残り)

注: v0.2.0 のタグに含まれる CHANGELOG は本節を「未リリース」表記のまま含む
(タグ後の整理のため)。

## [0.2.0] — 2026-08-26(タグ付け済み・人間承認) — パイロット還流(kenpo-keisan)より

### 破壊的変更 — project.yaml schema v2（0.2.0 への版上げを提案）

**既存の導出プロジェクトは、移行するまでゲートが赤になる。** `copier update` は
`project.yaml` を上書きしない(生成後プロジェクトの所有物)ため、移行は明示的に行う。

移行手順:

1. `copier update` でテンプレートを更新する(scripts/ が入れ替わる)
2. `python scripts/migrate_config.py` で変換結果を確認する(ファイルは変更されない)
3. `python scripts/migrate_config.py --write` で適用する
   — **コメントは失われる**ので、編集規則のコメントは書き戻すこと
4. 出力された「要確認」に対応する
   - `requirements.active_spec` — `spec_glob` の候補が複数あった場合は空になる。
     どれが有効かは人間が決める(自動選択こそが v2 で直した不具合)
   - `cutover.by_task` — 仮置きの `T-003` を TASK_INDEX の実在タスクに合わせる
5. `python scripts/run_gates.py --all` が緑になることを確認する

変更点:

- `req_prefix` → `requirements.prefix`
- `spec_glob` → `requirements.active_spec`(1件を明示。glob の自動選択を廃止 —
  文字列ソートでは `v0.10` が `v0.9` より前に並び、`status` も見ていなかった)
- `gates[].cmd` / `cutover.cmd` → `argv`(shell を経由しない)
- `stack.analyze` / `stack.test` → argv のリスト
- 設定検査(`scripts/check_project_config.py`)を追加。`gates` 列には書かず、
  `run_gates.py` が無条件で先に実行する
- `active_spec` 未設定の間、REQ整合ゲートは**未装備**(exit 3)を返す。
  従来は黙って緑だった

### 破壊的変更 — copier の質問 `spec_slug` を削除（同上）

`project_name` から決定的に導出できるため質問から外した(`when: false` で内部
変数としては残る)。第1段は決定的生成であり、導出可能な値を人間に尋ねない。

`copier update` では回答ファイルに残る `spec_slug` は使われず、`project_name`
からの導出値になる。**過去に `project_name` と対応しない `spec_slug` を指定して
いた場合、生成されるファイル名が変わる**ので `copier update` の差分を確認すること。

### 版の提案

上記はいずれも破壊的変更のため、**0.2.0** への版上げを提案する(SemVer では
0.x のマイナー版が破壊的変更を表す)。タグ付け=リリースは人間ゲート。

### 破壊的変更 — oracle に generate を必須化（同上・0.2.0）

オラクルを設定しているプロジェクトは、`oracle.generate` を追加するまでゲートが赤になる。

```yaml
oracle:
  generate: [python, scripts/generate_predictions.py]   # 追加(必須)
  predictions_dir: .verification/predictions            # 変更を推奨(gitignore 済み)
  metrics:                                              # 追加を推奨
    recall_min: 0.95
    precision_min: 0.95
```

- **予測を毎回作り直す** — 正しい実装で予測を作って合格させたあと実装を壊しても、
  古い予測が残っていれば合格し続けていた。照合対象を常に「いまのコードの出力」に固定する。
  生成前に `predictions_dir` の `*.csv` を消すため、生成が途中で失敗しても古い予測は残らない。
  生成の失敗は未装備ではなく赤。
- **参照イベント0件を合格にしない** — 従来は `rate = ok/denom if denom else 1.0` で、
  ヘッダ行だけのCSVが100%合格になっていた。
- **precision で誤検出を落とせる** — 従来 `extra` は件数表示のみで合否に影響しなかった。
  正解100件を全部当てても誤検出を10,000件出せば合格する状態だった。
  `metrics.recall_min` / `precision_min` / `f1_min` で判定する。
  `metrics` 未設定なら `pass_rate` を `recall_min` として使う従来挙動を保つが、
  precision が無制限になるため設定検査が警告する。
- `oracle.values` 未設定のときは値を比較していない旨を出力に明示する。

### 破壊的変更 — ゴールデン基準の初回生成を人間ゲートへ（同上・0.2.0）

`CLAUDE.md` §3.5-10 の「基準画像が存在しないテストの初回生成は自律で行ってよい」を
撤回した。**検証の正解を、検証される側が作ってはならない。** 参照オラクルを人間専管に
しているのと同じ理由である。基準が無いテストは ISSUE 起票→blocked とし、次のタスクへ移る。

自走中のエージェントの挙動が変わる。ゴールデンを採用しているプロジェクトは、
基準画像の初回投入を人間の作業として計画すること。

### 保護パス検査を追加

`scripts/check_protected_paths.py` を追加し、`project.yaml` に `protected` 節を置いた。

```yaml
protected:
  by_task: T-004
  paths: [CLAUDE.md, AGENTS.md, "docs/spec/**", "verification/reference/**",
          "test/golden/**", requirements.txt, <app_manifest>]
  keys: [oracle, protected]     # project.yaml の中で人間専管の節
```

- エージェントのコミット(`Agent:` トレーラ)が保護パスを変更していたら赤にする
- `project.yaml` はパス単位で保護しない(gates への行追加・stack の調整は提案可)。
  代わりに `keys` で節単位に保護する。**エージェントが自分を縛る設定を緩められない**
- **これは早期検出であって強制ではない。** トレーラを書かなければ回避できる。
  強制は GitHub の CODEOWNERS + 必須レビューが担う。T-004 を新設した
- CODEOWNERS は同梱しない。GitHub は解決できない owner を黙って無視するため、
  プレースホルダ入りで配ると「設定済みに見えて効いていない」状態を作ることになる
- 保護パス検査は `run_gates.py` の**組み込み**。`gates` 列には書かない
  (その行を消すコミット自身が素通りしてしまうため。設定検査と同じ理由)
- **保護方針は base の版から読む。** 現在の `project.yaml` から読むと、方針を
  弱めるコミット自身が弱めたあとの方針で検査され、緑になってしまう
- 保護節の変更はコミットとその親を比べる。base から最終形をまとめて比べると、
  人間の変更をエージェントの違反として数えてしまう
- `protected.by_task` の期限を `run_gates.py` が見る
- 生成CIの `guardrails` に `fetch-depth: 0` を追加(浅いクローンでは比較元を解決できない)。
  push では `github.event.before` を `PROTECTED_BASE` として渡す
  (push では checkout が origin の既定ブランチ参照を HEAD へ進めるため、
  そのままだと `base..HEAD` が空になり何も検査されない)

### 破壊的変更 — requirements.txt への新規依存追加を人間ゲートへ（同上・0.2.0）

`CLAUDE.md` §8 の自己修復は「既に requirements.txt にある依存のインストール」までとした。
新しいモジュールが必要になったら追記せず、ISSUE 起票→blocked とする。台帳への追記は
供給網の入口であり、綴り違いの取り違え(typosquatting)をエージェントの判断で通さない。

### kit-ci に Windows と Node を追加

テンプレートは Windows ネイティブ対応を明記しているのに、CI は Linux だけだった。
実際、日本語出力が非UTF-8ロケールで UnicodeEncodeError になる不具合を2回出している
(いずれも Linux では出ない)。copier は node をサポートしているのに、node の実体化は
一度も検証されていなかった。

```
Ubuntu  : manual / flutter / node / python
Windows : manual / node / python     （flutter は重いので除外）
```

- 手順をOSで分岐させないため、全ステップを `shell: bash` に揃えた
- 出力先は `$RUNNER_TEMP` を `cygpath` で正規化して使う
- **汎用スクリプトを単体でも実行する**。`run_gates.py` 経由なら子プロセスに
  UTF-8 が渡るが、CLAUDE.md §4 は単体実行も案内している。Windows ではこの経路
  だけが落ちていた
- **pre-commit フックを実行する**。Windows 分岐(`.venv/Scripts/python.exe`)を
  持ちながら一度も実行されていなかった
- `fail-fast: false`。片方のOSで落ちても他方の結果を捨てない

必須チェックは集約ジョブ `required-checks` だけを指定しているため、matrix が
3件から7件に増えても branch protection の設定変更は要らない。

### fix(kit-ci): 実体化テストが最新タグを検証していた

copier の既定 vcs ref はテンプレートの「最新タグ」である。`v0.1.0` があるため、
kit-ci の実体化テストは作業中のブランチではなく v0.1.0 を実体化していた。
**つまり template/ への変更は、このジョブで一度も検証されていなかった。**

`CLAUDE.md` 3項が「実体化テストが精度ゲート」と定めている当のゲートが、現在の
コードではなく過去のタグを検証していたことになる。古いテンプレートでも当時の
検査項目がすべて通っていたため、表面化しなかった。

`copier copy --vcs-ref=HEAD` を付け、生成元が HEAD であることを検査する
ステップ(新しいスクリプトの存在と `schema_version: 2`)を足した。

### fix(hooks): Windows で make を使わないようにする

`scripts/hooks/pre-commit` は `command -v make` があれば `make guard` を使うが、
Makefile は `.venv/bin/python` を前提としており Windows では成立しない
(CLAUDE.md §8 が「Windowsネイティブでは make を使わない」と定めている)。
Git Bash に make がある環境で、フックが壊れた経路を選んでいた。
`$OS` を `Windows_NT` と**明示的に比べて**、Windows では直接 python を使う。
非空かどうかで見ると、`OS` を別の値で輸出している Linux/macOS を Windows と
誤判定し、venv 未作成のまま直接 python を呼んで依存不足で落ちる。

### 同梱スクリプトの回帰テストを追加

`tests/` に pytest の回帰テストを置いた（113件）。これまで検証はPRごとの手動
ワンショットで、リポジトリに残っていなかった。同じ確認を毎回やり直すことになり、
一度直した不具合が戻っても気づけない。

対象は `template/scripts/*.py`。生成先と同じ配置を一時ディレクトリに作り、
**サブプロセスとして実行して終了コードを見る**。ゲートの契約は終了コードであり、
そこを直接検査するのが正しい。

これまでに見つけた不具合をすべて負のテストとして固定した。

- 未装備と合格を混ぜない（`gate_status.json` / `--strict` / 期限）
- 設定検査・保護パス検査が `gates` 列から消せない
- `argv` がシェルを経由しない（メタ文字がファイルを作らない）
- スタックコマンドの exit 3 は赤（pytest の internal error）
- 実行できないコマンドは例外でなく赤
- 古い予測・空の参照・誤検出で合格しない
- `metrics` の綴り違い / `match` の綴り違い
- 予測先が参照と同じなら何も消さずに中止
- 保護方針を弱めても、弱めた側の方針では検査されない
- 人間の節変更をエージェントの違反として数えない
- `active_spec` の版を glob で自動選択しない / L1 の外を指せない
- copier の入力検査（`foo_bar` / 日本語 / `A1` などを弾く）
- `NO` / `ON` / `NULL` が YAML で真偽値にならない
- 生成CIに `${{ }}` を書かない（Jinja2 が先に解釈する）
- 非UTF-8ロケールで落ちない

kit-ci に `scripts-unit` ジョブ（Ubuntu / Windows）を足し、`required-checks` の
依存に加えた。`lint-scripts` の対象に `tests` も含めた。

### 構造規範（N9）と構造検査を追加

文書は L0-L3 で統治され、仕様と実装の対応も検査されるのに、**コードの形には規範が
無かった**。その空白では、1000行超の単一ファイルや、import した瞬間に実行が始まる
テスト不能なエントリポイントが、何の抵抗もなく生まれる。

`PROCESS.md` に **N9 構造規範** を起こし、`scripts/check_structure.py` を追加した。
規範の唯一の定義は `project.yaml` の `structure` 節で、散文で層やサイズを語らない。

```yaml
structure:
  by_task: T-005
  max_file_lines: 400
  max_function_lines: 60          # Python のみ(AST)
  exclude: ["**/*.g.dart", "**/*_generated.*", "**/node_modules/**", "**/.venv/**"]
  layers: []                      # 例: [{name: ui, path: "lib/ui/**", may_import: [domain]}]
  pure_modules: []                # import しただけで実行が始まらないこと(Python のみ)
  pure_exempt: []                 # 枠組み上やむを得ないものを明示する
```

検査は3つ。いずれも決定論的で速い。

| 検査 | 対象 | 性質 |
|---|---|---|
| 行数 | 全言語 | `max_file_lines` / `max_function_lines` |
| 層の依存方向 | 全言語 | import 文に他層のディレクトリ名が現れるかを見る**発見的**検査 |
| 純粋性 | Python | import しただけで実行が始まらないこと(AST) |

- **禁止ではなく「免除を明示的に書かせる」**。`exclude` / `pure_exempt` に書かれた
  免除は人間がレビューで見られる
- 対象ファイルが0件のときは緑ではなく**未装備**。検査していないことと合格は別
- 層が宣言されていないときは何もしない。発見的な検査を推測で動かさない
- `may_import` の未知の層名は赤。綴り違いが許可として効かないようにする
- 純粋性は**種類だけで通さない**。`print(...)` は式、`CLIENT = connect()` は代入で、
  どちらも import した瞬間に走る。式は docstring だけを認め、代入は中の呼び出しを見る。
  定義時に必要な呼び出しは `pure_allow_calls` に明記する（免除を書かせる）
- import の取り出しは**順番に意味がある**。JS/TS の `import x from '...'` を先に見ないと、
  汎用の `import 名前` が先に当たって `x` を取り出し、層をまたぐ依存が素通りする

### ゲートの置き場所を「何を縛るか」で決める（PROCESS.md §5-14）

エージェント自身を縛るゲート（設定検査・保護パス検査・**構造検査**）は
`run_gates.py` の**組み込み**とし、`gates` 列に書かない。`gates` は `project.yaml`
の中にあるため、そこに置くとその行を消すコミット自身が素通りする。
`gates` 列に書くのは成果物を検査するゲート（REQ整合・精度）だけ。

`structure` を `protected.keys` に加えた。閾値をエージェントが緩められない。

### 実機確認の痕跡を要求する

検証器には**原理的に見えないもの**がある。新鮮で、非空で、しかし**利用者に届く
ものとは別の対象を検証している**場合である。古くも空でもないため、stale / empty
のどちらの対策でも捕まらない。

> 実例: 196件のテストがすべて緑のまま、機能3つが画面に一度も表示されていなかった。
> テストは毎回新しく生成された文字列を検証していたが、フレームワークが実際に配信
> するのは別のオブジェクトだった。

機械では検出できない。できるのは**人間が実機を触った痕跡を要求する**ことだけである。

```yaml
progress:
  by_task: T-004
  file: docs/L3/PROGRESS.md
  task_index: TASK_INDEX.md
  marker: "確認:"
  exempt: []          # 実機確認が要らないタスク(理由を DECISIONS へ)
```

- `done` になったタスクは、`PROGRESS.md` の**同じエントリ**にタスクIDと「確認:」が要る
- 対象は **base..HEAD で `done` になった分**に限る。過去の完了を遡って責めない
- 同じ行に限らないのは PROGRESS の書式(見出し + 3行以内)と噛み合わないため。
  文書全体で見ると別のタスクの確認で代用できてしまうので、エントリ単位にした
- `run_gates.py` の**組み込み**。`progress` を `protected.keys` に加え、
  エージェントが実機確認の要求を外せないようにした
- タスクIDは**語として**照合する。部分一致だと `T-001` が `T-0010` の記録で通る

### 既存プロジェクトの更新手順（重要）

`copier update` は `project.yaml` を上書きしない（生成後プロジェクトの所有物）。
そのため **`copier update` だけではスクリプトが新しくなるだけで、増えた節
（`protected` / `structure` / `progress`）は入りません。** その状態では増えた
ゲートが未装備のまま**期限も持たず**、非strict の guard は永久に緑になります。

```bash
copier update                          # スクリプトを更新
python scripts/migrate_config.py       # 何が補われるかを確認
python scripts/migrate_config.py --write
python scripts/run_gates.py --all      # 補われた節の中身を確認して緑にする
```

`migrate_config.py` は**版が合っていても**欠けた節を既定値で補い、
`protected.keys` の要素も足します。設定検査は必須の節が欠けていれば赤にし、
移行スクリプトを案内します。

### 組み込みゲートを表に整理

4本になったので `run_gates.py` に `BUILTIN` 表を置いた。`main()` は 82行から 60行へ。

| ゲート | 何を縛るか |
|---|---|
| `config` / `protected` / `structure` / `progress` | **エージェント自身** |
| `req-links` / `oracle` | 成果物(`gates` 列・設定可) |

### ライフサイクル（P1-4）

`lifecycle.phase` を追加し、段階と実体の食い違いを赤にする。

```yaml
lifecycle:
  phase: inception     # inception | development
```

| 段階 | 赤にするもの |
|---|---|
| `inception` | 実装が始まっている / 依存台帳がある |
| `development` | `requirements.active_spec` が空 / `stack.ready_marker` が空 |

**どちらの向きにも赤がある**のが要点。片方だけだと「段階を進めない」または
「段階だけ進める」で回避できる。

**実装の検出は設定に依存させない。** `layers.src` を別の場所へ向ける・`scan_ext` を
狭める・`ready_marker` を存在しないパスにする、のいずれでも実装が見えなくなる。
設定はエージェントが提案できる（`stack` の調整は §4 で認められている）ため、
検出方針を設定から読むと弱められる。固定のディレクトリ名（`src` / `lib` / `app`）と
既知のマニフェスト名を併せて見る。`run_gates.py` の組み込みで、`lifecycle` は
`protected.keys` が守る（段階を進めるのは人間の判断）。

### 生成先を自己完結させる（P1-5）

`template/docs/process/SHIOJI_PROCESS.md` に生成時点のプロセス定義を同梱した。
`INCEPTION_PROMPT.md` と **L0契約（`CLAUDE.md` 冒頭）** が生成元キットの `PROCESS.md`
を参照していたため、生成先だけでは規範カタログを引けなかった。生成先に `PROCESS.md`
は出ないので、**最も優先される文書が届かない参照を持っていた**ことになる。

写しなので二重管理になる。**原本と一致することをテストで照合する**ことで、
ずれたら気づけるようにした（`tests/test_kit_consistency.py`）。

### 自走モードの安全化（P1-6 / P1-7）

- **素性の分からない変更をコミットしない**（§3.5-6.5）。自走開始前に
  `git status --porcelain` を見て、clean なら開始、自セッションの続きなら resume、
  **素性が分からなければ ISSUE 起票 → blocked**。WIPコミットにしてはならない。
  人間の作業・他エージェントの作業・秘密情報・デバッグ用ファイルのいずれでも
  ありうる。**これは検出できない paper contract である**（素性を機械的に判定する
  手段が無い）
- **自走ブランチ名にタスクID等を足す**（§3.5-1）。`autopilot/<日付>-<agent名>` だけ
  では、同じ日に同じagentを複数起動すると衝突する。**同じ文書内の §3.5-12 に古い形式が
  残っていた**ため、そちらに従えば防ごうとした衝突がそのまま起きる状態だった。
  規則が2箇所にあるとずれるので、参照する形に統一し、テストで見るようにした

### 再現性（P1-14）

`.python-version`（`3.12`）をキットと生成先の両方に置いた。CI の pin と手元がずれない。

### 新しいゲートを足すときの点検表（PROCESS.md §5-17）

ゲートを足したら、**そのゲート自体が外れる経路**を4つとも塞ぐ。
v0.2 では、この4つがそれぞれ別のPRで指摘された。

1. **消せないか** — `gates` 列に置くと、その行を消すコミット自身が素通りする
2. **弱められないか** — 判定に使う方針を可変の設定から読むと、弱めるコミット自身が弱めた方針で検査される
3. **期限は読まれるか** — `by_task` を宣言しても、それを読むコードが無ければ何も起きない
4. **更新経路で入るか** — `copier update` は `project.yaml` を上書きしない

### その他

- **fix(gate): 未装備と合格を分けて報告**(`緑N件 / 未装備M件`・`gate_status.json`・
  Job Summary)。ゲートは exit 3 で未装備を自己申告する。`by_task` で未装備に期限を
  与え、期限のタスクが `done` になったのに装備されていなければ赤にする
- **fix(ci): 生成CIのスタックジョブから `if [ -f ... ]; then ...; else echo skip; fi`
  を撤去**し `run_gates.py --all` へ寄せた。検証を飛ばして成功する経路であり、
  `stack.by_task` の期限も評価されていなかった
- **fix(scripts): Windows(cp932)で日本語の出力が UnicodeEncodeError で落ちる**
  問題を修正。pre-commit フックだけが `PYTHONUTF8` を立てており、`make guard` /
  CI から直接呼ばれる経路が保護されていなかった。単体実行(`python scripts/validate_oracle.py --gate` など。CLAUDE.md §4 が案内している)も落ちていたため、全スクリプトで自分の出力を UTF-8 に固定した
- **fix(copier): validator を説明文と一致させた**。`foo_bar` / `foo.bar` /
  `foo/bar` / 日本語 / `-foo` / `foo--bar`、`req_prefix` の `A1` などが通っていた

- **fix(gate): 提案(docs/proposals)をREQ検査から除外**(project.yaml の `scan_exclude`・既定 `[docs/proposals]`)。パイロット還流#1: インセプション出力がREQ IDを提案すると、仕様適用前は幽霊REQ判定で pre-commit がブロックする問題を修正。提案は下書き(未定義/将来/却下のREQを含み得る)ため除外が正。src/test の幽霊REQ検出は不変(過剰除外なし)。
- **fix(scripts): 同梱 validate_oracle.py の ruff E702 を解消(還流#3)**。セミコロン多重文を分割。Python-stackで実体化し `ruff check .` を通すと同梱スクリプトが赤になる問題。kit-ci に「テンプレ同梱スクリプトの lint」ジョブ + 実体化matrixに `python` を追加し再発防止。
- **docs(release): 配布はタグ依存 — 既知の注意点(還流#2)**。copier 既定は「最新の git タグ」から複製する。リリースタグを GitHub へ push できていないと(本セッションはプロキシがタグ push を403拒否)、①リモートはタグ皆無→`copier copy gh:...` は HEAD 複製(可)、②タグを持つローカルclone は古いタグ内容で複製、という不一致が起きる。対策: リリースタグは必ず GitHub 側で作成(人間ゲート)。再現性が要る実体化は `--vcs-ref=<tag/sha>` を明示。

### v0.2 候補(パイロット還流待ち)
- モジュール条件生成(データ台帳・ゴールデン規約の copier 選択式)
- validate_oracle の整列強化(厳密DP・extra分類 — tsukishio で実証済みの発展形)
