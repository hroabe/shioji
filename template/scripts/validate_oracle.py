#!/usr/bin/env python3
"""精度ゲート(潮路キット汎用版)— 参照オラクル照合ハーネス。

構造(PROCESS.md §5): verification/reference/(人間投入・エージェント改変禁止)と
verification/predictions/(決定論ハーネスの出力)を、project.yaml の oracle 節が宣言する
許容誤差で照合する。不合格の検出は成果であり、閾値・参照データ・テストの調整で
合格させることを禁ずる(CLAUDE.md §2-1)。oracle 節の許容値は人間確定後、変更禁止。

モード:
  --dry-run   常に exit 3(未装備)。参照があれば合否を表示するが、それは参考であって
              判定ではない。装備は --gate への切替(人間ゲート)をもって成立する。
  --gate      本判定。oracle未定義・参照不在・生成失敗・予測欠落・基準未達は exit 1。
              切替は人間ゲート(CLAUDE.md §5)。
  --selftest  整列・判定ロジック自体の検査(CIで実行)。

照合(oracle.match):
  exact   : group_by + order_by の完全一致で対応付け、values を許容誤差で比較。
  ordered : group_by ごとに order_by(ISO8601日時または数値)で整列し、探索窓内で
            時系列順の一対一対応(貪欲・1手先読み・再利用禁止)。tsukishio 実証方式の基本形。
合否: 対応ペアが |Δorder|<=order_tolerance かつ 全values |Δ|<=許容 → その1件が合格(TP)。
      recall    = TP / 参照イベント数 (取りこぼしを見る。旧 pass_rate と同じ)
      precision = TP / 予測イベント数 (誤検出を見る。extra と許容外ペアが効く)
      oracle.metrics の recall_min / precision_min / f1_min で判定する。
      metrics 未設定なら pass_rate を recall_min として使い、precision は無制限
      (従来挙動。誤検出を何件出しても合格しうるため設定検査が警告する)。
      参照イベントが0件の系列は合格にしない(判定できないため)。
予測: oracle.generate を毎回実行して作り直す。古い予測での合格を防ぐ。
CSVスキーマ: ヘッダ行必須。group_by / order_by / values に宣言した列を持つこと。
"""
import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNARMED = 3                       # 未装備(run_gates.py が「緑」と区別して数える)


def load_oracle_config():
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("ERROR: pyyaml がない — 自己修復: python -m pip install -r requirements.txt (CLAUDE.md §8)")
    path = ROOT / "project.yaml"
    if not path.exists():
        sys.exit("ERROR: project.yaml がない(プロセス設定のSSoT)")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return cfg.get("oracle")


def parse_order(raw: str, where: str):
    raw = raw.strip()
    try:
        return ("t", datetime.fromisoformat(raw))
    except ValueError:
        try:
            return ("n", float(raw))
        except ValueError:
            sys.exit(f"ERROR: {where}: order列を解釈できない: {raw!r}(ISO8601日時または数値)")


def order_delta(a, b) -> float:
    """aとbの差。日時なら分、数値ならそのままの単位。"""
    if a[0] != b[0]:
        sys.exit("ERROR: order列の型(日時/数値)が参照と予測で混在している")
    if a[0] == "t":
        return (a[1] - b[1]).total_seconds() / 60.0
    return a[1] - b[1]


def load_events(path: Path, cfg: dict) -> list[dict]:
    group_cols = [str(c) for c in cfg.get("group_by") or []]
    order_col = str(cfg["order_by"])
    value_cols = [str(c) for c in (cfg.get("values") or {})]
    out, seen = [], set()
    with path.open(encoding="utf-8") as f:
        for lineno, row in enumerate(csv.DictReader(f), 2):
            where = f"{path.name} L{lineno}"
            for col in [*group_cols, order_col, *value_cols]:
                if row.get(col) is None:
                    sys.exit(f"ERROR: {where}: 列 {col!r} がない")
            group = tuple(row[c].strip() for c in group_cols)
            order = parse_order(row[order_col], where)
            try:
                values = {c: float(row[c]) for c in value_cols}
            except ValueError:
                sys.exit(f"ERROR: {where}: 値列が数値でない")
            for c, v in values.items():
                if v != v:  # NaN
                    sys.exit(f"ERROR: {where}: {c} がNaN")
            key = (group, row[order_col].strip())
            if key in seen:
                sys.exit(f"ERROR: {where}: 重複イベント {key}")
            seen.add(key)
            out.append({"group": group, "order": order,
                        "raw_order": row[order_col].strip(), "values": values})
    return out


def match_exact(ref: list, pred: list, cfg: dict):
    pred_map: dict = {}
    for e in pred:
        pred_map.setdefault((e["group"], e["raw_order"]), []).append(e)
    pairs, missing = [], []
    for e in ref:
        bucket = pred_map.get((e["group"], e["raw_order"]))
        if bucket:
            pairs.append((e, bucket.pop(0)))
        else:
            missing.append(e)
    extra = [e for b in pred_map.values() for e in b]
    return pairs, missing, extra


def match_ordered(ref: list, pred: list, cfg: dict):
    window = float(cfg.get("order_window", cfg["order_tolerance"]))
    pairs, missing, extra = [], [], []
    groups = sorted({e["group"] for e in ref} | {e["group"] for e in pred})
    for g in groups:
        r = sorted((e for e in ref if e["group"] == g), key=lambda e: e["order"][1])
        p = sorted((e for e in pred if e["group"] == g), key=lambda e: e["order"][1])
        i = j = 0
        while i < len(r) and j < len(p):
            d = order_delta(p[j]["order"], r[i]["order"])
            if d < -window:
                extra.append(p[j])
                j += 1
            elif d > window:
                missing.append(r[i])
                i += 1
            else:
                # 1手先読み: 次の予測の方が現参照に近ければ、現予測はextraへ送る(再利用禁止・非交差)
                if j + 1 < len(p):
                    d_next = order_delta(p[j + 1]["order"], r[i]["order"])
                    if abs(d_next) < abs(d) and abs(d_next) <= window:
                        extra.append(p[j])
                        j += 1
                        continue
                pairs.append((r[i], p[j]))
                i += 1
                j += 1
        missing.extend(r[i:])
        extra.extend(p[j:])
    return pairs, missing, extra


def scores(ok: int, n_ref: int, n_pred: int) -> dict:
    """TP=ok / FN=n_ref-ok / FP=n_pred-ok から recall・precision・F1 を出す。

    許容誤差を外した対応ペアは、正解を取り逃がした(FN)であると同時に、誤った
    予測を出した(FP)でもある。片方にしか数えないと誤検出が見えなくなる。
    予測が0件のときの precision は 0 とする(何も検出していない以上、精度は
    主張できない)。
    """
    recall = ok / n_ref if n_ref else 0.0
    precision = ok / n_pred if n_pred else 0.0
    total = precision + recall
    return {"recall": recall, "precision": precision,
            "f1": (2 * precision * recall / total) if total else 0.0}


def thresholds(cfg: dict) -> tuple:
    """判定基準を返す。

    metrics 未設定なら従来どおり合格率(=recall)のみで判定する。この場合
    precision は無制限になり、誤検出を何件出しても合格しうる。
    check_project_config.py がそのことを警告する。
    """
    limits = cfg.get("metrics") or {}
    if limits:
        return (float(limits.get("recall_min", 0.0)),
                float(limits.get("precision_min", 0.0)),
                limits.get("f1_min"))
    return (float(cfg.get("pass_rate", 1.0)), 0.0, None)


def evaluate(name: str, ref: list, pred: list, cfg: dict, quiet: bool = False) -> dict:
    tol_order = float(cfg["order_tolerance"])
    tols = {str(c): float(t) for c, t in (cfg.get("values") or {}).items()}
    matcher = match_exact if cfg.get("match", "exact") == "exact" else match_ordered
    pairs, missing, extra = matcher(ref, pred, cfg)
    ok, fails = 0, []
    for r, p in pairs:
        d_order = abs(order_delta(p["order"], r["order"]))
        bad = d_order > tol_order or any(
            abs(p["values"][c] - r["values"][c]) > t for c, t in tols.items())
        if bad:
            fails.append((r, p, d_order))
        else:
            ok += 1
    denom = len(ref)
    m = scores(ok, denom, len(pred))
    recall_min, precision_min, f1_min = thresholds(cfg)
    passed = m["recall"] >= recall_min and m["precision"] >= precision_min
    if f1_min is not None:
        passed = passed and m["f1"] >= float(f1_min)

    # 参照が0件のとき、従来は合格率を 1.0 として合格にしていた。
    # 「全問正解」ではなく「判定できない」であり、空の参照で合格させてはならない。
    empty = denom == 0
    if empty:
        passed = False

    if not quiet:
        if empty:
            print(f"{name}: 参照イベントが0件 — FAIL(判定できない。空の参照を合格にしない)")
        else:
            print(f"{name}: {ok}/{denom} — {'OK' if passed else 'FAIL'}"
                  f"  recall {m['recall']:.1%} / precision {m['precision']:.1%}"
                  f" / F1 {m['f1']:.1%}  missing {len(missing)} / extra {len(extra)}件")
            limit = f"  [基準: Δorder<={tol_order} / {tols or '値の比較なし'}" \
                    f" / recall>={recall_min} / precision>={precision_min}"
            print(limit + (f" / F1>={f1_min}" if f1_min is not None else "") + "]")
        if not tols:
            print("  注意: oracle.values が未設定 — 値を比較していない(順序と件数だけで判定)")
        for r, p, d in fails[:5]:
            deltas = ", ".join(
                f"Δ{c}={abs(p['values'][c] - r['values'][c]):.1f}" for c in tols)
            print(f"  FAIL {r['raw_order']} {'/'.join(r['group']) or '-'}: Δorder={d:.1f} {deltas}")
        if len(fails) > 5:
            print(f"  … 他{len(fails) - 5}件")

    return {"passed": passed, "ok": ok, "denom": denom, "rate": m["recall"],
            "missing": len(missing), "extra": len(extra), "empty": empty, **m}


def regenerate(cfg: dict, pred_dir: Path, gate: bool):
    """現在のコードから予測を作り直す。成功なら None、失敗なら終了コード。

    再生成しないと次が成立する:
      正しい実装で予測を生成 → 合格 → 実装を壊す → 古い予測が残る → 合格。
    照合するのは常に「いまのコードの出力」でなければならない。
    """
    argv = cfg.get("generate")
    if not argv:
        print("NG: oracle.generate が無い — 予測を再生成できないため判定しない")
        print("    (古い予測のまま合格させないため。project.yaml に生成コマンドを書く)")
        return 1 if gate else UNARMED
    argv = [str(a) for a in argv]
    if argv[0] == "python":
        argv[0] = sys.executable

    # 消す前に、消してよい場所かを確かめる。
    # 参照オラクルは人間専管であり、ここで消えると「同じファイルを参照とも
    # 予測とも読む」状態になって必ず緑になる。設定検査でも弾いているが、
    # 破壊的操作の直前でもう一度確かめる。
    ref_dir = (ROOT / str(cfg.get("reference_dir", "verification/reference"))).resolve()
    target = pred_dir.resolve()
    if target == ref_dir or target.is_relative_to(ref_dir) or ref_dir.is_relative_to(target):
        print("NG: predictions_dir が reference_dir と同じか入れ子になっている"
              f"({target} / {ref_dir})")
        print("    再生成で参照オラクルを消してしまうため、何も削除せずに中止する")
        return 1

    pred_dir.mkdir(parents=True, exist_ok=True)
    # 生成が途中で失敗しても古い予測が残らないよう、先に消す。
    for stale in pred_dir.glob("*.csv"):
        stale.unlink()
    print(f"== 予測を再生成: {' '.join(argv)}", flush=True)
    try:
        proc = subprocess.run(argv, cwd=ROOT)
    except OSError as error:
        print(f"NG: 予測生成コマンドを実行できない: {argv[0]} — {error}")
        return 1
    if proc.returncode != 0:
        # 生成の失敗は「未装備」ではない。ハーネスが壊れている。
        print(f"NG: 予測の生成に失敗 (exit {proc.returncode})")
        return 1
    return None


def run_check(gate: bool) -> int:
    cfg = load_oracle_config()
    if cfg is None:
        if gate:
            print("NG: project.yaml に oracle 節が無いまま --gate は実行できない(インセプションN1で確定)")
            return 1
        print("oracle: 未装備(インセプション N1 で project.yaml の oracle 節を確定すると有効化)")
        return UNARMED
    ref_dir = ROOT / str(cfg.get("reference_dir", "verification/reference"))
    pred_dir = ROOT / str(cfg.get("predictions_dir", ".verification/predictions"))
    refs = sorted(ref_dir.glob("*.csv")) if ref_dir.exists() else []
    if not refs:
        if gate:
            print(f"NG: 参照データが無い({ref_dir.relative_to(ROOT)}/ — 投入は人間ゲート)")
            return 1
        print(f"oracle: 未装備(参照データ未投入: {ref_dir.relative_to(ROOT)}/)")
        return UNARMED

    failed = regenerate(cfg, pred_dir, gate)
    if failed is not None:
        return failed

    all_passed = True
    for ref_path in refs:
        pred_path = pred_dir / ref_path.name
        if not pred_path.exists():
            print(f"{ref_path.stem}: 予測が無い({pred_path})— 生成コマンドが出力していない")
            all_passed = False
            continue
        result = evaluate(ref_path.stem, load_events(ref_path, cfg), load_events(pred_path, cfg), cfg)
        all_passed = all_passed and result["passed"]
    if gate:
        print("GATE " + ("OK" if all_passed else "NG"))
        return 0 if all_passed else 1
    # dry-run は装備されていない。合否を表示しても「合格」として数えさせない。
    # ここで 0 を返すと、失敗しているのに run_gates が緑に数えてしまう。
    print("DRY-RUN 終了(未装備 — 合否は参考。--gate 切替は人間ゲート)")
    return UNARMED


def selftest() -> int:
    def ev(kind: str, time: str, h: float) -> dict:
        return {"group": (kind,), "order": parse_order(time, "selftest"),
                "raw_order": time, "values": {"h": h}}

    cfg = {"match": "ordered", "group_by": ["kind"], "order_by": "time",
           "order_tolerance": 10, "order_window": 360,
           "values": {"h": 15.0}, "pass_rate": 0.95}

    # 1) 完全一致 → 合格
    ref = [ev("H", "2026-07-09 05:10", 150), ev("L", "2026-07-09 11:40", 30),
           ev("H", "2026-07-09 17:42", 156)]
    pred = [ev("H", "2026-07-09 05:12", 149), ev("L", "2026-07-09 11:35", 31),
            ev("H", "2026-07-09 17:40", 155)]
    r = evaluate("t1", ref, pred, cfg, quiet=True)
    assert r["passed"] and r["ok"] == 3 and r["missing"] == 0 and r["extra"] == 0, r

    # 2) 時刻ずれ超過1件 → 2/3 で不合格
    pred2 = [ev("H", "2026-07-09 05:40", 149), ev("L", "2026-07-09 11:35", 31),
             ev("H", "2026-07-09 17:40", 155)]
    r = evaluate("t2", ref, pred2, cfg, quiet=True)
    assert not r["passed"] and r["ok"] == 2, r

    # 3) 参照に無い微小極値(extra)を挟んでも正しいペアを選ぶ(1手先読み)
    pred3 = [ev("H", "2026-07-09 03:00", 100), ev("H", "2026-07-09 05:12", 149),
             ev("L", "2026-07-09 11:35", 31), ev("H", "2026-07-09 17:40", 155)]
    r = evaluate("t3", ref, pred3, cfg, quiet=True)
    assert r["passed"] and r["ok"] == 3 and r["extra"] == 1, r

    # 4) 高さ超過 → 不合格判定に数える
    pred4 = [ev("H", "2026-07-09 05:12", 120), ev("L", "2026-07-09 11:35", 31),
             ev("H", "2026-07-09 17:40", 155)]
    r = evaluate("t4", ref, pred4, cfg, quiet=True)
    assert r["ok"] == 2 and not r["passed"], r

    # 5) missing は分母に残る
    pred5 = [ev("H", "2026-07-09 05:12", 149), ev("H", "2026-07-09 17:40", 155)]
    r = evaluate("t5", ref, pred5, cfg, quiet=True)
    assert r["missing"] == 1 and r["ok"] == 2 and not r["passed"], r

    # 6) exact モード + 数値order
    cfg_e = {"match": "exact", "group_by": [], "order_by": "idx",
             "order_tolerance": 0, "values": {"v": 0.5}, "pass_rate": 1.0}
    ref_e = [{"group": (), "order": ("n", 1.0), "raw_order": "1", "values": {"v": 10.0}},
             {"group": (), "order": ("n", 2.0), "raw_order": "2", "values": {"v": 20.0}}]
    pred_e = [{"group": (), "order": ("n", 1.0), "raw_order": "1", "values": {"v": 10.3}},
              {"group": (), "order": ("n", 2.0), "raw_order": "2", "values": {"v": 20.0}}]
    r = evaluate("t6", ref_e, pred_e, cfg_e, quiet=True)
    assert r["passed"] and r["ok"] == 2, r

    # 7) CSV読取の端到端(一時ファイル)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.csv"
        p.write_text("kind,time,h\nH,2026-07-09 05:10,150\n", encoding="utf-8")
        events = load_events(p, cfg)
        assert events[0]["group"] == ("H",) and events[0]["values"]["h"] == 150.0

    # 8) 参照0件は「全問正解」ではない。空の参照で合格させない
    r = evaluate("t8", [], [], cfg, quiet=True)
    assert not r["passed"] and r["empty"] and r["denom"] == 0, r
    r = evaluate("t8b", [], [ev("H", "2026-07-09 05:10", 150)], cfg, quiet=True)
    assert not r["passed"] and r["empty"], r

    # 9) 誤検出は precision で落とせる。
    #    正解3件をすべて当てているが、参照に無い予測を大量に出している。
    noisy = pred3 + [ev("L", f"2026-07-09 2{n}:00", 5) for n in range(4)]
    r = evaluate("t9", ref, noisy, cfg, quiet=True)
    assert r["ok"] == 3 and r["recall"] == 1.0, r
    assert r["passed"], "metrics 未設定なら従来どおり合格(後方互換)"
    strict = {**cfg, "metrics": {"recall_min": 0.95, "precision_min": 0.95}}
    r = evaluate("t9b", ref, noisy, strict, quiet=True)
    assert not r["passed"] and r["precision"] < 0.95, r

    # 10) precision の分母は予測全件。許容外のペアは FN かつ FP として効く
    r = evaluate("t10", ref, pred2, {**cfg, "metrics": {"recall_min": 0.0,
                                                        "precision_min": 0.9}}, quiet=True)
    assert r["ok"] == 2 and r["precision"] == 2 / 3 and not r["passed"], r

    # 11) f1_min を設定したときだけ F1 で判定する
    base = {**cfg, "metrics": {"recall_min": 0.0, "precision_min": 0.0}}
    assert evaluate("t11", ref, noisy, base, quiet=True)["passed"], "F1未設定なら効かない"
    r = evaluate("t11b", ref, noisy, {**base, "f1_min": 0.9}, quiet=True)
    assert r["passed"], "f1_min は metrics の中に置く"
    r = evaluate("t11c", ref, noisy,
                 {**cfg, "metrics": {"recall_min": 0.0, "precision_min": 0.0,
                                     "f1_min": 0.9}}, quiet=True)
    assert not r["passed"] and r["f1"] < 0.9, r

    print("selftest OK: 11ケース")
    return 0


def use_utf8() -> None:
    """自分の出力を UTF-8 に固定する。

    Windows の既定は cp932 で、日本語や — を含む出力が UnicodeEncodeError で
    落ちる。run_gates.py 経由なら子プロセスに PYTHONUTF8 が渡るが、この
    スクリプトは単体でも実行される(CLAUDE.md §4)。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    use_utf8()
    args = set(sys.argv[1:])
    if "--selftest" in args:
        return selftest()
    if "--gate" in args:
        return run_check(gate=True)
    if "--dry-run" in args:
        return run_check(gate=False)
    print("usage: validate_oracle.py --dry-run | --gate | --selftest")
    return 2


if __name__ == "__main__":
    sys.exit(main())
