"""run_gates.py の回帰テスト。

中心は「未装備」と「合格」を混ぜないこと。緑の意味が曖昧になる形は
すべてここで固定する。
"""
from conftest import UNARMED, out


def test_0日目は緑だが内訳が出る(project):
    r = project.gates("--all")
    assert r.returncode == 0
    text = out(r)
    assert "未装備" in text
    assert "全ゲート緑" not in text        # 何も検証していないのに全部緑と言わない
    for gate in ("req-links", "oracle", "stack"):
        assert gate in text


def test_strictは未装備を赤にする(project):
    assert project.gates("--all", "--strict").returncode == 1


def test_gate_statusが機械可読で残る(project):
    import json
    project.gates("--all")
    data = json.loads((project.root / "verification" / "gate_status.json").read_text(encoding="utf-8"))
    states = {g["id"]: g["state"] for g in data["gates"]}
    assert states["config"] == "pass"
    assert states["oracle"] == "unarmed"
    assert data["green"] >= 1 and data["unarmed"] >= 1


def test_設定検査はgates列から消せない(project):
    """gates は project.yaml の中にある。そこに置くと設定から消せてしまう。"""
    project.config(gates=[])
    project.config(requirements={"prefix": "szn"})     # 設定を壊す
    r = project.gates()
    assert r.returncode == 1
    assert "config" in out(r)


def test_保護パス検査もgates列から消せない(project):
    """既定の gates に protected は無い。それでも組み込みで走る。"""
    assert "protected" not in [g["id"] for g in project.read_config()["gates"]]
    assert "== protected" in out(project.gates())


def test_gatesに書き足しても二重実行しない(project):
    cfg = project.read_config()
    cfg["gates"].append({"id": "protected",
                         "argv": ["python", "scripts/check_protected_paths.py"]})
    project.config(cfg)
    assert out(project.gates()).count("== protected") == 1


def test_期限のタスクがdoneなら未装備は赤(project):
    project.task("T-001", "done")            # stack の期限
    r = project.gates("--all")
    assert r.returncode == 1
    assert "T-001" in out(r)


def test_期限はall指定なしでも評価する(project):
    """実行するかどうかと、期限を過ぎたかどうかは別の問題。"""
    project.task("T-001", "done")
    assert project.gates().returncode == 1


def test_カットオーバーは期限のタスクで自動的に切り替わる(project):
    project.task("T-003", "done")
    r = project.gates()
    assert "--gate" in out(r)                # dry-run から切り替わっている
    assert r.returncode == 1                 # oracle 未設定なので赤


def test_ゲートは終了コード3で未装備を申告できる(project):
    project.write("scripts/unarmed.py", "import sys\nsys.exit(3)\n")
    cfg = project.read_config()
    cfg["gates"] = [{"id": "u", "argv": ["python", "scripts/unarmed.py"]}]
    project.config(cfg)
    r = project.gates()
    assert r.returncode == 0
    text = out(r)
    assert "未装備" in text and "u" in text


def test_スタックコマンドの終了コード3は赤(project):
    """pytest は exit 3 を internal error に使う。規約を押し付けない。"""
    project.develop()
    project.write("scripts/boom.py", "import sys\nsys.exit(3)\n")
    project.config(stack={"test": [["python", "scripts/boom.py"]]})
    r = project.gates("--all")
    assert r.returncode == 1
    assert "stack.test" in out(r)


def test_argvはシェルを経由しない(project):
    """project.yaml はエージェントが編集できる。メタ文字を解釈させない。"""
    project.write("scripts/echo_arg.py",
                  "import sys\nprint('ARG=' + sys.argv[1])\n")
    cfg = project.read_config()
    cfg["gates"] = [{"id": "e", "argv": ["python", "scripts/echo_arg.py",
                                         "x && echo PWNED > pwned.txt"]}]
    project.config(cfg)
    r = project.gates()
    assert r.returncode == 0
    assert "ARG=x && echo PWNED > pwned.txt" in out(r)
    assert not (project.root / "pwned.txt").exists()


def test_argvが無いゲートは赤(project):
    cfg = project.read_config()
    cfg["gates"] = [{"id": "x", "cmd": "python scripts/x.py"}]
    project.config(cfg)
    assert project.gates().returncode == 1


def test_実行できないコマンドは例外でなく赤(project):
    """shell=False にしたことで FileNotFoundError が素通りしていた。"""
    project.develop()
    project.config(stack={"test": [["definitely-not-a-real-command-xyz"]]})
    r = project.gates("--all")
    assert r.returncode == 1
    text = out(r)
    assert "Traceback" not in text
    assert "実行できない" in text


def test_gate_statusは作業ツリーを汚さない(project):
    """毎回の guard でリポジトリが dirty になると、未コミット0の規約と衝突する。"""
    ignore = (project.root / ".gitignore")
    ignore.write_text("verification/gate_status.json\n.verification/\n", encoding="utf-8")
    project.git_init()
    project.gates("--all")
    assert project.git("status", "--porcelain").stdout.strip() == ""


def test_未装備の終了コードは3で固定(project):
    """他のスクリプトと規約を共有する。"""
    assert project.run("validate_oracle.py", "--dry-run").returncode == UNARMED
    assert project.run("check_req_links.py").returncode == UNARMED
