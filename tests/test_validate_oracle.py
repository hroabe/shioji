"""validate_oracle.py の回帰テスト。

古い予測・空の参照・誤検出で合格しないこと。いずれも実際に合格していた。
"""
import pytest

from conftest import UNARMED, out

ORACLE = {
    "generate": ["python", "scripts/gen.py"],
    "reference_dir": "verification/reference",
    "predictions_dir": ".verification/predictions",
    "match": "ordered", "group_by": ["kind"], "order_by": "time",
    "order_tolerance": 10, "order_window": 360, "values": {"h": 15.0},
    "metrics": {"recall_min": 0.95, "precision_min": 0.95},
}

REFERENCE = ("kind,time,h\n"
             "H,2026-07-09 05:10,150\n"
             "L,2026-07-09 11:40,30\n"
             "H,2026-07-09 17:42,156\n")

GOOD = ("H,2026-07-09 05:12,149\n"
        "L,2026-07-09 11:35,31\n"
        "H,2026-07-09 17:40,155\n")

BROKEN = "H,2026-07-09 09:00,149\n"

NOISY = GOOD + "".join(f"L,2026-07-09 2{n}:00,5\n" for n in range(4))

GENERATOR = '''import pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent / "{out}"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "tide.csv").write_text("kind,time,h\\n" + {rows!r}, encoding="utf-8")
'''


def setup_oracle(project, rows: str = GOOD, out_dir: str = ".verification/predictions",
                 oracle: dict = None, **over) -> None:
    """oracle を丸ごと差し替える。**over での上書きは既存キーを消せない。"""
    project.write("verification/reference/tide.csv", REFERENCE)
    project.write("scripts/gen.py", GENERATOR.format(out=out_dir, rows=rows))
    project.replace("oracle", oracle if oracle is not None else {**ORACLE, **over})


def test_dry_runは常に未装備(project):
    """dry-run は報告であって判定ではない。合格として数えさせない。"""
    setup_oracle(project)
    assert project.run("validate_oracle.py", "--dry-run").returncode == UNARMED


def test_正常なら合格(project):
    setup_oracle(project)
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 0
    assert "GATE OK" in out(r)


def test_古い予測では合格できない(project):
    """正しい実装で合格させたあと実装を壊しても、古い予測が残れば合格していた。"""
    setup_oracle(project)
    assert project.run("validate_oracle.py", "--gate").returncode == 0
    stale = project.root / ".verification" / "predictions" / "tide.csv"
    assert stale.exists()                              # 古い予測が残っている

    project.write("scripts/gen.py",
                  GENERATOR.format(out=".verification/predictions", rows=BROKEN))
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1                           # 再生成されて赤になる
    assert "GATE NG" in out(r)


def test_空の参照は合格にしない(project):
    """rate = ok/denom if denom else 1.0 で、ヘッダだけのCSVが100%合格だった。"""
    setup_oracle(project)
    project.write("verification/reference/tide.csv", "kind,time,h\n")
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1
    assert "0件" in out(r)


def test_参照ディレクトリが空なら未装備(project):
    setup_oracle(project)
    (project.root / "verification" / "reference" / "tide.csv").unlink()
    assert project.run("validate_oracle.py", "--dry-run").returncode == UNARMED
    assert project.run("validate_oracle.py", "--gate").returncode == 1


def test_誤検出はprecisionで落とせる(project):
    """extra は件数表示のみで、合否に影響していなかった。"""
    setup_oracle(project, rows=NOISY)
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1
    text = out(r)
    assert "recall 100.0%" in text          # 取りこぼしは無い
    assert "precision" in text              # それでも誤検出で落ちる


def test_metrics未設定なら従来どおり合格する(project):
    """後方互換。ただし設定検査が警告を出す。"""
    cfg = dict(ORACLE)
    cfg.pop("metrics")
    cfg["pass_rate"] = 0.95
    setup_oracle(project, rows=NOISY, oracle=cfg)
    assert project.run("validate_oracle.py", "--gate").returncode == 0


def test_生成の失敗は未装備でなく赤(project):
    """ハーネスが壊れている状態は「報告のみ」ではない。"""
    setup_oracle(project)
    project.write("scripts/gen.py", "import sys\nsys.exit(1)\n")
    assert project.run("validate_oracle.py", "--gate").returncode == 1
    assert project.run("validate_oracle.py", "--dry-run").returncode == 1


def test_generateが無ければ判定しない(project):
    cfg = dict(ORACLE)
    cfg.pop("generate")
    setup_oracle(project, oracle=cfg)
    assert project.run("validate_oracle.py", "--gate").returncode == 1
    assert project.run("validate_oracle.py", "--dry-run").returncode == UNARMED


def test_予測先が参照と同じなら何も消さずに中止する(project):
    """設定検査を迂回して単体実行されても、参照オラクルを消させない。"""
    setup_oracle(project, out_dir="verification/reference",
                 oracle={**ORACLE, "predictions_dir": "verification/reference"})
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1
    assert (project.root / "verification" / "reference" / "tide.csv").exists()
    assert "中止" in out(r)


def test_selftestが通る(project):
    r = project.run("validate_oracle.py", "--selftest")
    assert r.returncode == 0
    assert "selftest OK" in out(r)


@pytest.mark.parametrize("encoding", ["cp1252", "ascii"])
def test_非UTF8ロケールでも落ちない(project, encoding):
    """Windows の既定ロケールで日本語出力が UnicodeEncodeError になっていた。"""
    setup_oracle(project)
    r = project.run("validate_oracle.py", "--gate",
                    env={"PYTHONIOENCODING": encoding, "PYTHONUTF8": "0"})
    assert r.returncode == 0
    assert "Traceback" not in out(r)


# --- 削除先の封じ込め（v0.2.2 §2: 設定検査を迂回しても消させない） ---------

def sentinel(project, rel: str = "../outside_oracle"):
    """リポジトリ外の目印CSV。消えたら封じ込めの失敗。"""
    outside = (project.root / rel).resolve()
    outside.mkdir(parents=True, exist_ok=True)
    path = outside / "keep.csv"
    path.write_text("sentinel" + chr(10), encoding="utf-8")
    return path


def test_外の相対パスでは何も消さずに赤(project):
    keep = sentinel(project)
    setup_oracle(project, oracle={**ORACLE, "predictions_dir": "../outside_oracle"})
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1
    assert keep.exists(), "リポジトリ外のCSVが削除された"
    assert "外" in out(r)
    assert project.run("validate_oracle.py", "--dry-run").returncode == 1


def test_絶対パスでは何も消さずに赤(project):
    keep = sentinel(project)
    setup_oracle(project, oracle={**ORACLE,
                                  "predictions_dir": str(keep.parent)})
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1
    assert keep.exists()
    assert "絶対パス" in out(r)


def test_ルートそのものは削除対象にできない(project):
    (project.root / "root_level.csv").write_text("x" + chr(10), encoding="utf-8")
    setup_oracle(project, oracle={**ORACLE, "predictions_dir": "."})
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1
    assert (project.root / "root_level.csv").exists()


def test_参照が外なら読まずに赤(project):
    sentinel(project)
    setup_oracle(project, oracle={**ORACLE, "reference_dir": "../outside_oracle"})
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1
    assert "reference_dir" in out(r)


def test_シンボリックリンク経由でも外に出られない(project):
    import os
    keep = sentinel(project)
    link = project.root / ".verification" / "predictions"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(keep.parent, link, target_is_directory=True)
    except OSError:
        import pytest
        pytest.skip("シンボリックリンクを作る権限が無い(Windows既定)")
    setup_oracle(project)          # predictions_dir は既定の .verification/predictions
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 1
    assert keep.exists(), "リンク先(リポジトリ外)のCSVが削除された"


# --- ordered照合の全体最適（v0.2.2 目標5） ---------------------------------

def test_貪欲が取りこぼす系列でも全対応を見つける(project):
    """旧実装(貪欲+1手先読み)は先読みで p0 を extra へ送り、1対応で終わった。"""
    NL = chr(10)
    ref = "kind,t,h" + NL + "H,0,10" + NL + "H,2,10" + NL
    pred = "kind,t,h" + NL + "H,-1,10" + NL + "H,0,10" + NL
    project.write("verification/reference/seq.csv", ref)
    gen = (
        "import pathlib" + NL
        + "OUT = pathlib.Path(__file__).resolve().parent.parent"
          " / '.verification' / 'predictions'" + NL
        + "OUT.mkdir(parents=True, exist_ok=True)" + NL
        + f"(OUT / 'seq.csv').write_text({pred!r}, encoding='utf-8')" + NL
    )
    project.write("scripts/gen.py", gen)
    project.replace("oracle", {
        "generate": ["python", "scripts/gen.py"],
        "reference_dir": "verification/reference",
        "predictions_dir": ".verification/predictions",
        "match": "ordered", "group_by": ["kind"], "order_by": "t",
        "order_tolerance": 2, "order_window": 2, "values": {"h": 100.0},
        "metrics": {"recall_min": 1.0, "precision_min": 1.0},
    })
    r = project.run("validate_oracle.py", "--gate")
    assert r.returncode == 0, out(r)
    assert "recall 100.0%" in out(r)
