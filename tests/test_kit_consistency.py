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


def test_未使用のimportが無い():
    """kit-ci の ruff(F401)と同じことを手元でも見る。

    ruff が入っていない環境で作業すると、CI を1往復するまで気づけない。
    完全な代替ではない。**スコープを区別しない**ため、同じファイルの別の関数で
    同名を使っていると関数内の未使用importを見逃す（実際に見逃した）。
    最終的な判定は kit-ci の ruff。ここは往復を減らすための粗い網である。
    """
    import ast
    bad = []
    for directory in ("template/scripts", "tests"):
        for path in sorted((KIT / directory).glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported[alias.asname or alias.name] = node.lineno
            used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            bad += [f"{path.name}:{line} {name}"
                    for name, line in imported.items() if name not in used]
    assert not bad, bad


def test_生成先の契約が同梱の写しを指す():
    """生成先に PROCESS.md は出ない。生成元を参照させない。"""
    claude = (KIT / "template/CLAUDE.md.jinja").read_text(encoding="utf-8")
    assert "docs/process/SHIOJI_PROCESS.md" in claude
    assert "生成元の PROCESS.md" not in claude
    assert not (KIT / "template/PROCESS.md").exists()


def test_自走ブランチ名の規則が1つに揃っている():
    """同じ文書の中で古い形式が残ると、そちらに従われる。"""
    claude = (KIT / "template/CLAUDE.md.jinja").read_text(encoding="utf-8")
    for line in claude.splitlines():
        if "autopilot/<" in line:
            assert "識別子" in line or "§3.5-1" in line, line
