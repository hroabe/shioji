"""check_lifecycle.py の回帰テスト。

段階と実体の食い違い。どちらの向きにも赤があることが要点。
"""
from conftest import UNARMED, out

NL = chr(10)


def check(project):
    return project.run("check_lifecycle.py")


def test_lifecycle節が無ければ未装備(project):
    project.replace("lifecycle", None)
    assert check(project).returncode == UNARMED


def test_未知の段階は赤(project):
    project.replace("lifecycle", {"phase": "いいかんじ"})
    r = check(project)
    assert r.returncode == 1
    assert "phase" in out(r)


# --- inception: 実装が始まっていたら赤 -------------------------------------

def test_インセプション中で実装が無ければ緑(project):
    project.replace("lifecycle", {"phase": "inception"})
    assert check(project).returncode == 0


def test_インセプション中に実装層のファイルがあれば赤(project):
    project.replace("lifecycle", {"phase": "inception"})
    project.write("src/app.py", "x = 1" + NL)
    r = check(project)
    assert r.returncode == 1
    assert "src/app.py" in out(r)


def test_インセプション中にマニフェストがあれば赤(project):
    project.replace("lifecycle", {"phase": "inception"})
    project.config(stack={"ready_marker": "pyproject.toml"})
    project.write("pyproject.toml", "")
    r = check(project)
    assert r.returncode == 1
    assert "pyproject.toml" in out(r)


# --- development: 仕様とスタックが要る -------------------------------------

def test_仕様が無いまま開発段階にできない(project):
    """段階だけ進めて、仕様もスタックも無いまま作り始めるのを止める。"""
    project.replace("lifecycle", {"phase": "development"})
    r = check(project)
    assert r.returncode == 1
    assert "active_spec" in out(r)


def test_スタックが無いまま開発段階にできない(project):
    project.write("docs/spec/S.md", "---" + NL + "status: active" + NL + "---" + NL)
    project.config(requirements={"active_spec": "docs/spec/S.md"})
    project.replace("lifecycle", {"phase": "development"})
    r = check(project)
    assert r.returncode == 1
    assert "ready_marker" in out(r)


def test_仕様とスタックが揃えば緑(project):
    project.write("docs/spec/S.md", "---" + NL + "status: active" + NL + "---" + NL)
    project.write("pyproject.toml", "")
    project.config(requirements={"active_spec": "docs/spec/S.md"},
                   stack={"ready_marker": "pyproject.toml"})
    project.replace("lifecycle", {"phase": "development"})
    assert check(project).returncode == 0


# --- 外れる経路を塞いでいるか（PROCESS.md §5-17 の点検表） -----------------

def test_組み込みなのでgates列から消せない(project):
    assert "lifecycle" not in [g["id"] for g in project.read_config()["gates"]]
    assert "== lifecycle" in out(project.gates())


def test_段階は保護節に入っている(project):
    """段階を進めるのは人間の判断。エージェントが勝手に進めない。"""
    assert "lifecycle" in project.read_config()["protected"]["keys"]


def test_必須節なので欠けたら設定検査が赤(project):
    project.replace("lifecycle", None)
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "migrate_config" in out(r)


def test_移行スクリプトが補う(project):
    project.replace("lifecycle", None)
    project.run("migrate_config.py", "--write")
    cfg = project.read_config()
    assert cfg["lifecycle"]["phase"] == "inception"
    assert "lifecycle" in cfg["protected"]["keys"]
