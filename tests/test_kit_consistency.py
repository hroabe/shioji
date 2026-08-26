"""キット自身の一貫性。

生成先に同梱する写しや、キットが要求する節の一覧が、原本とずれていないか。
"""
from conftest import KIT

SNAPSHOT = KIT / "template/docs/process/SHIOJI_PROCESS.md"


def test_同梱のプロセス定義が原本と一致する():
    """生成先を自己完結させるための写し。ずれたら気づけるようにする。

    二重管理そのものは避けられないので、機械で照合する形にしてある。
    """
    assert SNAPSHOT.exists(), "template/docs/process/SHIOJI_PROCESS.md が無い"
    assert SNAPSHOT.read_bytes() == (KIT / "PROCESS.md").read_bytes(), (
        "PROCESS.md を変えたら template/docs/process/SHIOJI_PROCESS.md へ写すこと")


def test_組み込みゲートと必須節の一覧が揃っている():
    """run_gates の BUILTIN と migrate_config の REQUIRED_SECTIONS のずれを防ぐ。"""
    import re
    run_gates = (KIT / "template/scripts/run_gates.py").read_text(encoding="utf-8")
    migrate = (KIT / "template/scripts/migrate_config.py").read_text(encoding="utf-8")
    sections = set(re.findall(r'Builtin\("[\w-]+", "[\w.]+", "(\w+)"\)', run_gates))
    required = set(re.findall(r'^    "(\w+)": \{', migrate, re.MULTILINE))
    assert sections <= required | {""}, (
        f"BUILTIN が読む節 {sections - required} が REQUIRED_SECTIONS に無い"
        " — copier update で入らず、期限も持たないまま緑になる")


def test_組み込みゲートのスクリプトが実在する():
    import re
    run_gates = (KIT / "template/scripts/run_gates.py").read_text(encoding="utf-8")
    for script in re.findall(r'Builtin\("[\w-]+", "([\w.]+)"', run_gates):
        assert (KIT / "template/scripts" / script).exists(), script


def test_pythonの版が固定されている():
    """CI の pin と手元がずれないようにする。"""
    for path in (KIT / ".python-version", KIT / "template/.python-version"):
        assert path.exists(), path
        assert path.read_text(encoding="utf-8").strip() == "3.12"
