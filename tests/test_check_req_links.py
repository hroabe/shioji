"""check_req_links.py の回帰テスト。

仕様書の選び方と、REQ の整合。
"""
from conftest import UNARMED, out

SPEC = """---
doc: SAZANAMI_SPEC
layer: L1
status: active
---

# 仕様

- REQ-SZN-001 潮位を計算する
- REQ-SZN-002 図を描く
"""


def spec(project, name: str = "SAZANAMI_SPEC_v0.1.md", text: str = SPEC) -> str:
    project.write(f"docs/spec/{name}", text)
    project.config(requirements={"active_spec": f"docs/spec/{name}"})
    return f"docs/spec/{name}"


def test_active_spec未設定は未装備(project):
    """従来は「spec: 未作成 — skip」と出して黙って緑だった。"""
    r = project.run("check_req_links.py")
    assert r.returncode == UNARMED
    assert "未装備" in out(r)


def test_仕様があり参照が整合すれば緑(project):
    spec(project)
    project.write("src/tide.py", "# REQ-SZN-001\n")
    project.write("tests/test_tide.py", "# REQ-SZN-001\n")
    assert project.run("check_req_links.py").returncode == 0


def test_幽霊REQは赤(project):
    """仕様が無いのに REQ を参照している。"""
    project.write("src/tide.py", "# REQ-SZN-001\n")
    r = project.run("check_req_links.py")
    assert r.returncode == 1
    assert "幽霊REQ" in out(r)


def test_未定義REQは赤(project):
    spec(project)
    project.write("src/tide.py", "# REQ-SZN-999\n")
    project.write("tests/test_tide.py", "# REQ-SZN-999\n")
    r = project.run("check_req_links.py")
    assert r.returncode == 1
    assert "REQ-SZN-999" in out(r)


def test_実装のみでテストに無いREQは赤(project):
    spec(project)
    project.write("src/tide.py", "# REQ-SZN-001\n")
    r = project.run("check_req_links.py")
    assert r.returncode == 1
    assert "テスト未リンク" in out(r)


def test_廃止REQの参照は赤(project):
    spec(project)
    project.config(deprecated_reqs=[1])
    project.write("src/tide.py", "# REQ-SZN-001\n")
    project.write("tests/test_tide.py", "# REQ-SZN-001\n")
    r = project.run("check_req_links.py")
    assert r.returncode == 1
    assert "廃止REQ" in out(r)


def test_提案は検査から除く(project):
    """インセプション出力は下書きで、未定義・将来・却下のREQを含みうる。"""
    spec(project)
    project.write("docs/proposals/inception/draft.md", "REQ-SZN-777 を提案する\n")
    assert project.run("check_req_links.py").returncode == 0


def test_版はglobで自動選択しない(project):
    """文字列ソートでは v0.10 が v0.9 より前に並び、誤った版が選ばれていた。"""
    # 旧版も走査対象になるため、新版は旧版のREQを含む上位互換にする
    project.write("docs/spec/SAZANAMI_SPEC_v0.9.md", SPEC)
    project.write("docs/spec/SAZANAMI_SPEC_v0.10.md",
                  SPEC + "- REQ-SZN-003 凡例を出す" + chr(10))
    project.config(requirements={"active_spec": "docs/spec/SAZANAMI_SPEC_v0.10.md"})
    project.write("src/x.py", "# REQ-SZN-003\n")
    project.write("tests/test_x.py", "# REQ-SZN-003\n")
    # v0.10 を明示しているので REQ-SZN-003 は定義済みとして通る
    assert project.run("check_req_links.py").returncode == 0
    r = project.run("check_req_links.py")
    assert "SAZANAMI_SPEC_v0.10.md" in out(r)


def test_active_specが実在しなければ赤(project):
    project.config(requirements={"active_spec": "docs/spec/nope.md"})
    assert project.run("check_req_links.py").returncode != 0


def test_status語彙の違反は赤(project):
    spec(project)
    project.write("docs/spec/other.md", "---\nstatus: いいかんじ\n---\n")
    assert project.run("check_req_links.py").returncode == 1
