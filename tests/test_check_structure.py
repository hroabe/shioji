"""check_structure.py の回帰テスト。

コードの形の規範。文書は L0-L3 で統治されているのに、コードの形には
規範が無かった領域。
"""
from conftest import UNARMED, out

STRUCTURE = {
    "by_task": "T-005",
    "max_file_lines": 20,
    "max_function_lines": 5,
    "exclude": ["**/*_generated.*"],
    "layers": [],
    "pure_modules": [],
    "pure_exempt": [],
}


def setup(project, structure: dict = None) -> None:
    project.replace("structure", structure if structure is not None else dict(STRUCTURE))


def check(project):
    return project.run("check_structure.py")


def test_structure節が無ければ未装備(project):
    project.replace("structure", None)
    assert check(project).returncode == UNARMED


def test_規範が空なら未装備(project):
    setup(project, {"by_task": "T-005", "layers": [], "pure_modules": []})
    assert check(project).returncode == UNARMED


def test_対象ファイルが無ければ未装備(project):
    """0件で緑にしない。検査していないことと合格は別。"""
    setup(project)
    r = check(project)
    assert r.returncode == UNARMED
    assert "検査対象" in out(r)


def test_規範に収まるファイルは緑(project):
    setup(project)
    project.write("src/ok.py", "def f():\n    return 1\n")
    assert check(project).returncode == 0


# --- 行数 -----------------------------------------------------------------

def test_ファイル行数の上限を超えたら赤(project):
    setup(project)
    project.write("src/big.py", "x = 1\n" * 30)
    r = check(project)
    assert r.returncode == 1
    assert "30行" in out(r)


def test_除外に書けば対象外(project):
    """禁止ではなく、免除を明示的に書かせる。"""
    setup(project)
    project.write("src/ok.py", "x = 1" + chr(10))
    project.write("src/big_generated.py", "x = 1\n" * 30)
    assert check(project).returncode == 0


def test_関数行数の上限を超えたら赤(project):
    setup(project)
    body = "\n".join(f"    a{n} = {n}" for n in range(10))
    project.write("src/long.py", f"def f():\n{body}\n")
    r = check(project)
    assert r.returncode == 1
    assert "関数 f" in out(r)


# --- 純粋性 ---------------------------------------------------------------

PURE = {**STRUCTURE, "max_file_lines": 400, "max_function_lines": 200,
        "pure_modules": ["src/**/*.py"]}


def test_import時に実行が始まるモジュールは赤(project):
    """テスト不能なエントリポイントを、書けてしまう状態にしない。"""
    setup(project, PURE)
    project.write("src/app.py",
                  "import os\nprint('副作用')\nfor x in range(3):\n    pass\n")
    r = check(project)
    assert r.returncode == 1
    assert "実行が始まる" in out(r)


def test_定数と関数定義だけなら通る(project):
    setup(project, PURE)
    project.write("src/app.py",
                  "import os\nNAME = 'x'\n\n\ndef main():\n    return NAME\n")
    assert check(project).returncode == 0


def test_name_main_の入口は認める(project):
    setup(project, PURE)
    project.write("src/app.py",
                  "def main():\n    return 1\n\n\nif __name__ == '__main__':\n    main()\n")
    assert check(project).returncode == 0


def test_免除に書けば対象外(project):
    """Streamlit のようにトップレベル実行が前提の枠組みもある。"""
    setup(project, {**PURE, "pure_exempt": ["src/app.py"]})
    project.write("src/app.py", "import os\nprint('副作用')\nfor x in range(3):\n    pass\n")
    assert check(project).returncode == 0


# --- 層の依存方向 ---------------------------------------------------------

LAYERED = {**STRUCTURE, "max_file_lines": 400, "max_function_lines": 200,
           "layers": [
               {"name": "ui", "path": "src/ui/**", "may_import": ["domain", "shared"]},
               {"name": "domain", "path": "src/domain/**", "may_import": ["shared"]},
               {"name": "shared", "path": "src/shared/**", "may_import": []},
           ]}


def test_許可された向きは通る(project):
    setup(project, LAYERED)
    project.write("src/ui/page.py", "from src.domain import calc\n")
    project.write("src/domain/calc.py", "from src.shared import util\n")
    project.write("src/shared/util.py", "x = 1\n")
    assert check(project).returncode == 0


def test_逆流は赤(project):
    setup(project, LAYERED)
    project.write("src/shared/util.py", "from src.ui import page\n")
    r = check(project)
    assert r.returncode == 1
    assert "shared 層が ui 層を" in out(r)


def test_層をまたぐ飛び越しも赤(project):
    setup(project, LAYERED)
    project.write("src/domain/calc.py", "from src.ui import page\n")
    assert check(project).returncode == 1


def test_層が宣言されていなければ何もしない(project):
    """発見的な検査なので、宣言が無いときに推測で動かさない。"""
    setup(project, {**STRUCTURE, "max_file_lines": 400, "max_function_lines": 200})
    project.write("src/shared/util.py", "from src.ui import page\n")
    assert check(project).returncode == 0


# --- 設定検査との連携 -----------------------------------------------------

def test_未知の層名を許可に書いたら赤(project):
    """綴り違いは許可として効かない。黙って無視しない。"""
    project.replace("structure", {**LAYERED, "layers": [
        {"name": "ui", "path": "src/ui/**", "may_import": ["domian"]},
        {"name": "domain", "path": "src/domain/**", "may_import": []},
    ]})
    r = project.run("check_project_config.py")
    assert r.returncode == 1
    assert "domian" in out(r)


def test_層名の重複は赤(project):
    project.replace("structure", {**LAYERED, "layers": [
        {"name": "ui", "path": "src/a/**"},
        {"name": "ui", "path": "src/b/**"},
    ]})
    assert project.run("check_project_config.py").returncode == 1


def test_閾値は保護節に入っている(project):
    """エージェントが自分を縛る値を緩められない。"""
    assert "structure" in project.read_config()["protected"]["keys"]


def test_構造検査はgates列から消せない(project):
    assert "structure" not in [g["id"] for g in project.read_config()["gates"]]
    assert "== structure" in out(project.gates())


def test_期限のタスクがdoneなら未装備は赤(project):
    """規範が空のまま T-005 を done にできない。"""
    setup(project, {"by_task": "T-005", "layers": [], "pure_modules": []})
    project.task("T-005", "done")
    r = project.gates()
    assert r.returncode == 1
    assert "T-005" in out(r)


def test_節ごと消せば期限も消えるが保護ゲートが見る(project):
    """期限は節の中にある。節を消せば期限も消える。

    人間が消すのは判断だが、エージェントには許さない。structure は
    protected.keys に入っているので、削除もエージェントの違反として捕まる。
    """
    project.git_init()
    project.replace("structure", None)
    project.commit("構造規範を消す")
    r = project.run("check_protected_paths.py", "--base", "base")
    assert r.returncode == 1
    assert "structure" in out(r)
