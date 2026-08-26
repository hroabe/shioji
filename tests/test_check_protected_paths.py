"""check_protected_paths.py の回帰テスト。

人間専管のファイルと設定節を、エージェントのコミットが変更していないか。
方針そのものを弱められないことが要点。
"""
from conftest import UNARMED, out

ORACLE = {
    "generate": ["python", "scripts/gen.py"],
    "reference_dir": "verification/reference",
    "predictions_dir": ".verification/predictions",
    "match": "ordered", "order_by": "time", "order_tolerance": 10,
    "values": {"h": 1.0}, "metrics": {"recall_min": 0.9},
}


def check(project, *args):
    return project.run("check_protected_paths.py", *args)


def test_gitでなければ未装備(project):
    assert check(project).returncode == UNARMED


def test_比較元が無ければ未装備(project):
    """origin が無いと、何が新しい変更かを決められない。"""
    project.git_init()
    r = check(project)
    assert r.returncode == UNARMED
    assert "未装備" in out(r)


def test_人間のコミットは報告のみ(project):
    project.git_init()
    project.write("CLAUDE.md", "# 人間が直した\n")
    project.commit("L0を更新", human=True)
    r = check(project, "--base", "base")
    assert r.returncode == 0
    assert "人間のコミット" in out(r)


def test_エージェントのコミットは赤(project):
    project.git_init()
    project.write("CLAUDE.md", "# エージェントが直した\n")
    project.commit("L0を書き換える")
    r = check(project, "--base", "base")
    assert r.returncode == 1
    assert "CLAUDE.md" in out(r)


def test_保護対象外なら通る(project):
    project.git_init()
    project.write("src/app.py", "x = 1\n")
    project.commit("実装を足す")
    assert check(project, "--base", "base").returncode == 0


def test_ゴールデン基準の追加は赤(project):
    """検証の正解を、検証される側が作ってはならない。"""
    project.git_init()
    project.write("test/golden/home.png", "fake\n")
    project.commit("ゴールデン初回生成")
    r = check(project, "--base", "base")
    assert r.returncode == 1
    assert "test/golden" in out(r)


def test_依存台帳への追記は赤(project):
    project.git_init()
    project.write("requirements.txt", "pyyaml==6.0.2\nrequets\n")
    project.commit("依存を足す")
    assert check(project, "--base", "base").returncode == 1


def test_保護節の変更は赤(project):
    """project.yaml はパス単位で保護しない。節単位で守る。"""
    project.git_init()
    project.config(oracle=dict(ORACLE))
    project.commit("oracleを設定する")
    r = check(project, "--base", "base")
    assert r.returncode == 1
    assert "oracle" in out(r)


def test_保護対象でない節の変更は通る(project):
    """gates への行追加・stack の調整はエージェントの提案が認められている。"""
    project.git_init()
    project.config(stack={"ready_marker": "pyproject.toml"})
    project.commit("stackを調整する")
    assert check(project, "--base", "base").returncode == 0


def test_方針を弱めても弱めた側で検査されない(project):
    """現在の設定から方針を読むと、弱めるコミット自身が緑になる。"""
    project.git_init()
    project.config(protected={"paths": ["AGENTS.md"], "keys": []})
    project.write("CLAUDE.md", "# 保護から外して書き換えた\n")
    project.commit("保護を緩めつつL0を書き換える")
    r = check(project, "--base", "base")
    assert r.returncode == 1
    text = out(r)
    assert "CLAUDE.md" in text          # base の方針で見ている
    assert "protected" in text          # 方針を変えたこと自体も咎める


def test_人間の節変更をエージェントの違反として数えない(project):
    """base から最終形をまとめて比べると、人間の変更が巻き込まれる。"""
    project.git_init()
    project.config(oracle=dict(ORACLE))
    project.commit("人間が oracle を設定する", human=True)
    project.config(stack={"ready_marker": "pyproject.toml"})
    project.commit("エージェントが stack を調整する")
    assert check(project, "--base", "base").returncode == 0


def test_glob二連星はディレクトリ境界をまたぐ(project):
    project.git_init()
    project.write("docs/spec/sub/deep.md", "x\n")
    project.commit("深い階層の仕様を足す")
    assert check(project, "--base", "base").returncode == 1


def test_環境変数でも比較元を渡せる(project):
    project.git_init()
    project.write("CLAUDE.md", "# 書き換えた\n")
    project.commit("L0を書き換える")
    assert project.run("check_protected_paths.py",
                       env={"PROTECTED_BASE": "base"}).returncode == 1
