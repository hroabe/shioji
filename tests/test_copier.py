"""copier.yml の入力検査と、テンプレートの描画。

copier 本体を使わず、copier と同じ Jinja2 設定で描画して確かめる。
validator も「描画結果が空なら合格」という同じ規則で判定される。
"""
import pytest
import yaml

from conftest import KIT

jinja2 = pytest.importorskip("jinja2")

ENV = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
COPIER = yaml.safe_load((KIT / "copier.yml").read_text(encoding="utf-8"))

STACKS = ["manual", "flutter", "node", "python"]


def validate(question: str, value: str) -> str:
    """copier の validator を描画する。空文字なら合格。"""
    return ENV.from_string(COPIER[question]["validator"]).render(**{question: value}).strip()


@pytest.mark.parametrize("name", ["foo", "foo-bar", "foo2", "foo2-bar3", "tsukishio"])
def test_正しいプロジェクト名は通る(name):
    assert validate("project_name", name) == ""


@pytest.mark.parametrize("name", [
    "foo_bar", "foo.bar", "foo/bar", "FOO", "Foo-bar", "a b", "日本語",
    "", "-foo", "foo-", "foo--bar",
])
def test_説明どおりに弾く(name):
    """実装は lower 比較だけで、記号も全角も通っていた。"""
    assert validate("project_name", name) != ""


@pytest.mark.parametrize("prefix", ["APP", "TSU", "AB", "ABCDE"])
def test_正しい接頭辞は通る(prefix):
    assert validate("req_prefix", prefix) == ""


@pytest.mark.parametrize("prefix", ["A", "ABCDEF", "abc", "A1", "A_B", "アイウ"])
def test_接頭辞は大文字英字2から5字(prefix):
    assert validate("req_prefix", prefix) != ""


def test_spec_slugは質問しない():
    """project_name から決定的に導出できる値を人間に尋ねない。"""
    assert COPIER["spec_slug"].get("when") is False


def render(rel: str, **ctx) -> str:
    text = (KIT / "template" / rel).read_text(encoding="utf-8")
    base = {"project_name": "sazanami", "req_prefix": "SZN",
            "spec_slug": "SAZANAMI", "stack": "manual"}
    return ENV.from_string(text).render(**{**base, **ctx})


@pytest.mark.parametrize("stack", STACKS)
def test_project_yamlが有効なYAMLとして描画される(stack):
    cfg = yaml.safe_load(render("project.yaml.jinja", stack=stack))
    assert cfg["schema_version"] == 2
    assert cfg["requirements"]["prefix"] == "SZN"
    # 設定検査と保護パス検査は組み込みなので gates には出ない
    assert [g["id"] for g in cfg["gates"]] == ["req-links", "oracle"]
    assert cfg["protected"]["paths"]
    for gate in cfg["gates"]:
        assert isinstance(gate["argv"], list)


@pytest.mark.parametrize("stack", STACKS)
def test_ci_ymlが有効なYAMLとして描画される(stack):
    doc = yaml.safe_load(render(".github/workflows/ci.yml.jinja", stack=stack))
    assert "guardrails" in doc["jobs"]
    checkout = doc["jobs"]["guardrails"]["steps"][0]
    assert checkout["with"]["fetch-depth"] == 0     # 保護パス検査に全履歴が要る
    if stack != "manual":
        assert "stack" in doc["jobs"]


def test_生成CIにGitHubの式を書かない():
    """`${{ }}` は Jinja2 が先に解釈して描画そのものが失敗する。"""
    text = (KIT / "template/.github/workflows/ci.yml.jinja").read_text(encoding="utf-8")
    assert "${{" not in text


@pytest.mark.parametrize("value", ["no", "yes", "on", "off", "null"])
def test_YAMLで真偽値になる名前も文字列のまま(value):
    """validator を通る NO / ON / NULL が PyYAML では真偽値・null になる。"""
    cfg = yaml.safe_load(render("project.yaml.jinja",
                                project_name=value, req_prefix=value.upper()))
    assert isinstance(cfg["project"], str)
    assert isinstance(cfg["requirements"]["prefix"], str)


@pytest.mark.parametrize("stack", STACKS)
def test_未展開のプレースホルダが残らない(stack):
    for rel in ("project.yaml.jinja", ".github/workflows/ci.yml.jinja"):
        assert "{{" not in render(rel, stack=stack)
