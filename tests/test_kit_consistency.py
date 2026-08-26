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


def test_セミコロン複文が無い():
    """kit-ci の ruff(E702)と同じことを手元でも見る。

    v0.1 の還流#3(validate_oracle の E702)と同じ轍を v0.2.2 の作業で
    また踏んだ。手元に ruff が無い環境では CI を1往復するまで気づけない。
    このコードベースにセミコロン複文の正当な用例は無いので、単純一致で足りる。
    """
    semi = chr(59)                # ";" を直書きすると、この検査が自分に当たる
    for directory in ("template/scripts", "tests"):
        for path in sorted((KIT / directory).glob("*.py")):
            for lineno, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split(chr(35))[0]
                bad = (semi + " ") in code or code.rstrip().endswith(semi)
                assert not bad, (
                    f"{path.name}:{lineno}: セミコロン複文(E702) — 行を分ける")


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


def template_docs():
    return sorted((KIT / "template").glob("*.jinja")) +            sorted((KIT / "template").glob("*.md"))


def test_自走ブランチ名の規則が全文書で揃っている():
    """CLAUDE だけ見ていて INITIAL_PROMPT の3箇所目を取りこぼした。

    規則の原本は §3.5-1。他の文書は識別子込みの形式か、§3.5-1 への参照を持つ。
    """
    for path in template_docs():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "autopilot/" in line:
                assert "識別子" in line or "§3.5-1" in line, f"{path.name}: {line}"


def test_契約と矛盾するWIPコミット指示が残っていない():
    """§3.5-6.5 は素性不明の変更のコミットを禁じるが、INITIAL_PROMPT が
    「wip: としてコミット」を指示したまま残っていた。"""
    for path in template_docs():
        text = path.read_text(encoding="utf-8")
        assert "wip:" not in text, f"{path.name} に WIP コミット指示が残っている"


def test_規範番号が表と見出しで食い違わない():
    """v0.2.0 で実際に起きた。表は N6=商業倫理 を定義済みなのに、
    構造規範の見出しが N6 を名乗り、同じ §6 に別内容の N6 が2つ並んだ。

    表の番号は一意であること。見出し(### Nx 名前)は、表の同じ番号の行と
    名前が一致すること(見出しは表の項目の詳説である)。
    """
    import re
    text = (KIT / "PROCESS.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (N\d+) \| (\S+) \|", text, re.MULTILINE)
    numbers = [n for n, _ in rows]
    assert len(numbers) == len(set(numbers)), f"表の番号が重複: {numbers}"
    table = dict(rows)
    for number, name in re.findall(r"^### (N\d+) (\S+)", text, re.MULTILINE):
        assert number in table, f"見出し {number} {name} が表に無い"
        assert table[number] == name, (
            f"見出し {number} {name} と表の {number} {table[number]} が食い違う")


def test_生成元参照の変種も残っていない():
    """「生成元の PROCESS.md」は塞いだが「生成元 PROCESS.md §6」(の抜き)が
    S2スロットに残っていた。表記ゆれごと検査する。
    """
    import re
    for path in template_docs():
        text = path.read_text(encoding="utf-8")
        # `.` は既定で改行に一致しないので、同一行内の近接だけを見る
        assert not re.search(r"生成元.{0,12}PROCESS\.md", text), path.name


def test_テンプレート依存はすべて固定されている():
    """再現性を要求する側が固定していない、を繰り返さない(P1-14)。"""
    for line in (KIT / "template/requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            assert "==" in line, f"固定されていない: {line}"


def test_既定の保護集合がゲート本体を覆う():
    """run_gates の BUILTIN・フック・CI・写しが protected.paths に入っている。

    check_project_config.KIT_CORE との三者(テンプレート既定・KIT_CORE・BUILTIN)
    のずれをここで検出する。
    """
    import re
    template = (KIT / "template/project.yaml.jinja").read_text(encoding="utf-8")
    core = (KIT / "template/scripts/check_project_config.py").read_text(encoding="utf-8")
    run_gates = (KIT / "template/scripts/run_gates.py").read_text(encoding="utf-8")
    kit_core = re.findall(r'^    "([^"]+)",$', core[core.index("KIT_CORE"):core.index("def glob_to_regex")], re.MULTILINE)
    assert kit_core, "KIT_CORE を読めない"
    for entry in kit_core:
        assert f"- {entry}" in template, f"テンプレート既定に {entry} が無い"
    for script in re.findall(r'Builtin\("[\w-]+", "([\w.]+)"', run_gates):
        assert f"scripts/{script}" in kit_core, f"BUILTIN の {script} が KIT_CORE に無い"
    for must in ("scripts/hooks/pre-commit", ".github/workflows/ci.yml",
                 "docs/process/SHIOJI_PROCESS.md", "Makefile"):
        assert must in kit_core, must


def test_最新タグの版がCHANGELOGに見出しを持つ():
    """「タグ済みなのに未リリース」を v0.2.0 / v0.2.1 で2回やった。機械で見る。"""
    import subprocess
    import pytest
    proc = subprocess.run(["git", "tag", "--list", "v*", "--sort=-v:refname"],
                          cwd=KIT, capture_output=True, text=True, encoding="utf-8")
    tags = [t for t in (proc.stdout or "").split() if t]
    if proc.returncode != 0 or not tags:
        pytest.skip("タグを取得できない(浅いcloneなど)")
    latest = tags[0]
    changelog = (KIT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{latest[1:]}]" in changelog, (
        f"タグ {latest} があるのに CHANGELOG に ## [{latest[1:]}] が無い"
        " — タグ済みの内容を「未リリース」の下に置いたままにしない")


def test_ゴールデンREADMEが同梱されている():
    """CLAUDE.md が test/golden/README.md を参照する。宙に浮かせない。"""
    readme = KIT / "template/test/golden/README.md"
    assert readme.exists()
    text = readme.read_text(encoding="utf-8")
    assert "人間ゲート" in text and "blocked" in text
