"""check_project_config.py の回帰テスト。

いずれも実際に見つかった不具合か、レビューで指摘された穴に対応する。
"""
from conftest import out


def test_生成直後の設定は緑(project):
    assert project.run("check_project_config.py").returncode == 0


def test_v1の設定は移行を促して赤(project):
    project.config({
        "project": "x", "req_prefix": "SZN", "spec_glob": "docs/spec/*SPEC*.md",
        "layers": {"src": ["src"], "test": ["tests"]},
        "stack": {"ready_marker": "", "analyze": "ruff check .", "test": "pytest -q"},
        "gates": [{"id": "req-links", "cmd": "python scripts/check_req_links.py"}],
    })
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    text = out(r)
    for expected in ("schema_version", "req_prefix", "spec_glob", "cmd"):
        assert expected in text


def test_prefixは大文字英字2から5字(project):
    for bad in ("szn", "S", "ABCDEF", "A1", "アイウ"):
        project.config(requirements={"prefix": bad})
        assert project.run("check_project_config.py").returncode == 1, bad
    project.config(requirements={"prefix": "SZN"})
    assert project.run("check_project_config.py").returncode == 0


def test_active_specはL1の外を指せない(project):
    """docs/spec/../OUTSIDE.md は前方一致では通ってしまう。解決後で判定する。"""
    project.write("docs/OUTSIDE.md", "---\nstatus: active\n---\n")
    project.config(requirements={"active_spec": "docs/spec/../OUTSIDE.md"})
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "L1" in out(r)


def test_active_specはstatusがactiveでないと赤(project):
    project.write("docs/spec/S.md", "---\nstatus: draft\n---\n")
    project.config(requirements={"active_spec": "docs/spec/S.md"})
    assert project.run("check_project_config.py").returncode == 1
    project.write("docs/spec/S.md", "---\nstatus: active\n---\n")
    assert project.run("check_project_config.py").returncode == 0


def test_gatesはargv形式(project):
    project.config(gates=[{"id": "x", "cmd": "python scripts/x.py"}])
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "argv" in out(r)


def test_cutoverには期限が要る(project):
    project.config(gates=[{"id": "oracle", "argv": ["python", "x.py"],
                           "cutover": {"argv": ["python", "y.py"]}}])
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "by_task" in out(r)


# --- oracle ---------------------------------------------------------------

ORACLE = {
    "generate": ["python", "scripts/gen.py"],
    "reference_dir": "verification/reference",
    "predictions_dir": ".verification/predictions",
    "match": "ordered", "group_by": ["kind"], "order_by": "time",
    "order_tolerance": 10, "values": {"h": 15.0},
    "metrics": {"recall_min": 0.95, "precision_min": 0.95},
}


def test_oracleの正常系(project):
    project.replace("oracle", dict(ORACLE))
    assert project.run("check_project_config.py").returncode == 0


def test_matchの綴り違いは赤(project):
    """未知の値を黙って ordered に落としていた。"""
    project.replace("oracle", {**ORACLE, "match": "exatc"})
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "match" in out(r)


def test_generateが無いと赤(project):
    """再生成できないと、古い予測のまま合格しうる。"""
    cfg = dict(ORACLE)
    cfg.pop("generate")
    project.replace("oracle", cfg)
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "generate" in out(r)


def test_order_byとorder_toleranceは必須(project):
    """validate_oracle が無条件に参照する。欠けると照合時に KeyError で落ちる。"""
    for key in ("order_by", "order_tolerance"):
        cfg = dict(ORACLE)
        cfg.pop(key)
        project.replace("oracle", cfg)
        r = project.run("check_project_config.py")
        assert r.returncode == 1, key
        assert key in out(r)


def test_metricsの綴り違いはゲートを無効にするので赤(project):
    """recall_mim と書くと基準が 0 になり、TPが0でも合格していた。"""
    project.replace("oracle", {**ORACLE, "metrics": {"recall_mim": 0.95, "precision_mim": 0.95}})
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "recall_mim" in out(r)


def test_metrics未設定は警告だが赤にはしない(project):
    cfg = dict(ORACLE)
    cfg.pop("metrics")
    cfg["pass_rate"] = 0.95
    project.replace("oracle", cfg)
    r = project.run("check_project_config.py")
    assert r.returncode == 0
    assert "警告" in out(r)


def test_値域の外は赤(project):
    for key, value in (("pass_rate", 1.5), ("order_tolerance", -10)):
        project.replace("oracle", {**ORACLE, key: value})
        assert project.run("check_project_config.py").returncode == 1, key


def test_予測先が参照と同じなら赤(project):
    """再生成は predictions_dir の *.csv を消す。参照オラクルを消してしまう。"""
    project.replace("oracle", {**ORACLE, "predictions_dir": "verification/reference"})
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "reference_dir" in out(r)


def test_予測先が参照の入れ子でも赤(project):
    project.replace("oracle", {**ORACLE, "predictions_dir": "verification/reference/pred"})
    assert project.run("check_project_config.py").returncode == 1
