#!/usr/bin/env python3
"""精度ゲート(潮路キット汎用版)— 参照オラクル照合ハーネス。

構造(PROCESS.md §5): verification/reference/(人間投入・エージェント改変禁止)と
verification/predictions/(決定論ハーネスの出力)を、project.yaml の oracle 節が宣言する
許容誤差で照合する。不合格の検出は成果であり、閾値・参照データ・テストの調整で
合格させることを禁ずる(CLAUDE.md §2-1)。oracle 節の許容値は人間確定後、変更禁止。

モード:
  --dry-run   常に exit 3(未装備)。参照があれば合否を表示するが、それは参考であって
              判定ではない。装備は --gate への切替(人間ゲート)をもって成立する。
  --gate      本判定。oracle未定義・参照不在・予測欠落・合格率未達は exit 1。切替は人間ゲート(CLAUDE.md §5)。
  --selftest  整列・判定ロジック自体の検査(CIで実行)。

照合(oracle.match):
  exact   : group_by + order_by の完全一致で対応付け、values を許容誤差で比較。
  ordered : group_by ごとに order_by(ISO8601日時または数値)で整列し、探索窓内で
            時系列順の一対一対応(貪欲・1手先読み・再利用禁止)。tsukishio 実証方式の基本形。
合否: 対応ペアが |Δorder|<=order_tolerance かつ 全values |Δ|<=許容 → 合格。
      合格率 = 合格ペア / 参照イベント数(missing を分母に含む)>= pass_rate。
      extra(参照に無い予測)は件数報告のみ(強化・分類は各プロジェクトの発展形 — PROCESS.md §9)。
CSVスキーマ: ヘッダ行必須。group_by / order_by / values に宣言した列を持つこと。
"""
import csv
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
    rate = ok / denom if denom else 1.0
    passed = rate >= float(cfg.get("pass_rate", 1.0))
    if not quiet:
        print(f"{name}: {ok}/{denom} ({rate:.1%}) — {'OK' if passed else 'FAIL'}"
              f"  missing {len(missing)} / extra {len(extra)}件"
              f"  [基準: Δorder<={tol_order} / {tols} / 合格率>={cfg.get('pass_rate', 1.0)}]")
        for r, p, d in fails[:5]:
            deltas = ", ".join(
                f"Δ{c}={abs(p['values'][c] - r['values'][c]):.1f}" for c in tols)
            print(f"  FAIL {r['raw_order']} {'/'.join(r['group']) or '-'}: Δorder={d:.1f} {deltas}")
        if len(fails) > 5:
            print(f"  … 他{len(fails) - 5}件")
    return {"passed": passed, "ok": ok, "denom": denom, "rate": rate,
            "missing": len(missing), "extra": len(extra)}


def run_check(gate: bool) -> int:
    cfg = load_oracle_config()
    if cfg is None:
        if gate:
            print("NG: project.yaml に oracle 節が無いまま --gate は実行できない(インセプションN1で確定)")
            return 1
        print("oracle: 未装備(インセプション N1 で project.yaml の oracle 節を確定すると有効化)")
        return UNARMED
    ref_dir = ROOT / str(cfg.get("reference_dir", "verification/reference"))
    pred_dir = ROOT / str(cfg.get("predictions_dir", "verification/predictions"))
    refs = sorted(ref_dir.glob("*.csv")) if ref_dir.exists() else []
    if not refs:
        if gate:
            print(f"NG: 参照データが無い({ref_dir.relative_to(ROOT)}/ — 投入は人間ゲート)")
            return 1
        print(f"oracle: 未装備(参照データ未投入: {ref_dir.relative_to(ROOT)}/)")
        return UNARMED
    all_passed = True
    for ref_path in refs:
        pred_path = pred_dir / ref_path.name
        if not pred_path.exists():
            print(f"{ref_path.stem}: 予測が無い({pred_path.relative_to(ROOT)})— {'NG' if gate else '未生成'}")
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

    print("selftest OK: 7ケース")
    return 0


def main() -> int:
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
