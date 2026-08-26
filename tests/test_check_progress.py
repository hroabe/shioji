"""check_progress.py の回帰テスト。

ゲートには原理的に見えないものがある。人間が実機を触った痕跡を要求する。
"""
from conftest import UNARMED, out

NL = chr(10)

LOG = "docs/L3/PROGRESS.md"


def check(project, *args):
    return project.run("check_progress.py", *args)


def entry(task: str, text: str = "画面で操作して確かめた") -> str:
    return f"## 2026-08-26 {task}{NL}- 確認: {text}{NL}{NL}"


def test_progress節が無ければ未装備(project):
    project.replace("progress", None)
    assert check(project).returncode == UNARMED


def test_gitでなければ未装備(project):
    assert check(project).returncode == UNARMED


def test_比較元が無ければ未装備(project):
    project.git_init()
    r = check(project)
    assert r.returncode == UNARMED
    assert "未装備" in out(r)


def test_doneになったタスクが無ければ対象なし(project):
    project.git_init()
    project.write("src/x.py", "x = 1" + NL)
    project.commit("実装を足す")
    r = check(project, "--base", "base")
    assert r.returncode == 0
    assert "対象なし" in out(r)


def test_確認の記録が無ければ赤(project):
    """テストが全部緑でも、利用者に届くものを見ていないことがある。"""
    project.git_init()
    project.task("T-001", "done")
    project.commit("T-001 を完了にする")
    r = check(project, "--base", "base")
    assert r.returncode == 1
    assert "T-001" in out(r)


def test_確認の記録があれば緑(project):
    project.git_init()
    project.task("T-001", "done")
    project.write(LOG, entry("T-001"))
    project.commit("T-001 を完了にする")
    r = check(project, "--base", "base")
    assert r.returncode == 0
    assert "T-001" in out(r)


def test_別のエントリの確認では代用できない(project):
    """文書全体で見ると、別のタスクの確認で通ってしまう。"""
    project.git_init()
    project.task("T-001", "done")
    project.write(LOG, f"## T-009 の作業{NL}- 確認: 別のタスクを見た{NL}{NL}"
                       f"## T-001 の作業{NL}- 実装した{NL}")
    project.commit("T-001 を完了にする")
    assert check(project, "--base", "base").returncode == 1


def test_同じエントリの中にあればよい(project):
    """PROGRESS は見出し + 3行以内。同じ行に限ると書式と噛み合わない。"""
    project.git_init()
    project.task("T-001", "done")
    project.write(LOG, f"## 2026-08-26 T-001 を完了{NL}- 実装した{NL}"
                       f"- 確認: 画面で操作して確かめた{NL}")
    project.commit("T-001 を完了にする")
    assert check(project, "--base", "base").returncode == 0


def test_過去にdoneだったタスクは遡って責めない(project):
    """規範を後から入れたとき、過去の完了を全部赤にしない。"""
    project.task("T-001", "done")
    project.git_init()                       # base の時点で既に done
    project.write("src/x.py", "x = 1" + NL)
    project.commit("実装を足す")
    assert check(project, "--base", "base").returncode == 0


def test_複数のタスクを一度に完了しても全部見る(project):
    project.git_init()
    project.task("T-001", "done")
    project.task("T-003", "done")
    project.write(LOG, entry("T-001"))
    project.commit("2件を完了にする")
    r = check(project, "--base", "base")
    assert r.returncode == 1
    text = out(r)
    assert "T-003" in text


def test_免除に書けば対象外(project):
    """人間しか触れないタスクなど。理由は DECISIONS に残す。"""
    project.git_init()
    project.task("T-001", "done")
    project.config(progress={"exempt": ["T-001"]})
    project.commit("T-001 を完了にする")
    assert check(project, "--base", "base").returncode == 0


def test_免除があると設定検査が警告する(project):
    project.config(progress={"exempt": ["T-001"]})
    r = project.run("check_project_config.py")
    assert r.returncode == 0
    assert "DECISIONS" in out(r)


def test_標識は設定で変えられる(project):
    project.git_init()
    project.config(progress={"marker": "verified:"})
    project.task("T-001", "done")
    project.write(LOG, f"## T-001{NL}- verified: 画面で見た{NL}")
    project.commit("T-001 を完了にする")
    assert check(project, "--base", "base").returncode == 0


def test_組み込みなのでgates列から消せない(project):
    assert "progress" not in [g["id"] for g in project.read_config()["gates"]]
    assert "== progress" in out(project.gates())


def test_設定は保護節に入っている(project):
    """エージェントが実機確認の要求を外せない。"""
    assert "progress" in project.read_config()["protected"]["keys"]


def test_期限のタスクがdoneなら未装備は赤(project):
    project.task("T-004", "done")            # progress の期限も T-004
    r = project.gates()
    assert r.returncode == 1
    assert "T-004" in out(r)


def test_タスクIDは語として照合する(project):
    """T-001 が T-0010 の記録で通ってしまう部分一致を防ぐ。"""
    project.git_init()
    project.task("T-001", "done")
    project.write(LOG, f"## T-0010 の作業{NL}- 確認: 別のタスクを見た{NL}")
    project.commit("T-001 を完了にする")
    assert check(project, "--base", "base").returncode == 1
