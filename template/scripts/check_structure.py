#!/usr/bin/env python3
"""構造検査(潮路キット)— コードの形が規範から外れていないか。

文書は L0-L3 で統治され、仕様と実装の対応も検査される。しかし**コードの形**
には規範が無かった。その空白では、1000行超の単一ファイルや、import した瞬間に
実行が始まるテスト不能なエントリポイントが、何の抵抗もなく生まれる。

規範の唯一の定義は project.yaml の structure 節である。散文で層やファイルサイズ
を語らない(CLAUDE.md §7)。閾値は protected.keys に入れ、エージェントが自分を
縛る値を緩められないようにする。

検査は3つ。いずれも決定論的で速い。

  1. 行数        言語非依存。max_file_lines / max_function_lines
  2. 層の依存方向 import 文の中に他層のディレクトリ名が現れるかを見る**発見的**な
                 検査。誤検出を避けるため、層が宣言されているときだけ働く
  3. 純粋性      import しただけで実行が始まらないこと(Python のみ・AST)

関数長と純粋性は Python の AST に依存する。他言語では対象外として報告する。
禁止ではなく「免除を明示的に書かせる」形にしてあり、書かれた免除は人間が
レビューで見られる。
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNARMED = 3                       # 未装備(run_gates.py が「緑」と区別して数える)

# import 行から対象を取り出す。**順番に意味がある。**
# JS/TS の `import x from '...'` を先に見ないと、汎用の `import 名前` が先に
# 当たって取り出す対象が 'x' になり、'../ui/page' を一度も見ないまま通る。
IMPORT_PATTERNS = (
    re.compile(r"""^\s*(?:import|export)\b.*?\bfrom\s*['"]([^'"]+)['"]"""),
    re.compile(r"""^\s*import\s*['"]([^'"]+)['"]"""),
    re.compile(r"""(?:require|use)\s*\(?\s*['"]([^'"]+)['"]"""),
    re.compile(r"^\s*from\s+([\w.]+)\s+import\b"),
    re.compile(r"^\s*import\s+([\w.]+)"),
)

# モジュール直下に置いてよい定義。式と代入は中身も見る(下の check_pure)。
PURE_DEFS = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
             ast.ClassDef)


def use_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def load_config() -> dict:
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("ERROR: pyyaml がない — 自己修復: python -m pip install -r requirements.txt (CLAUDE.md §8)")
    path = ROOT / "project.yaml"
    if not path.exists():
        sys.exit("ERROR: project.yaml がない(プロセス設定のSSoT)")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def to_regex(pattern: str) -> re.Pattern:
    """glob をパス用の正規表現へ。`**` はディレクトリ境界をまたぐ。"""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def sources(cfg: dict, structure: dict) -> list:
    """検査対象のファイル。layers.src / layers.test と scan_ext を使い回す。"""
    layers = cfg.get("layers") or {}
    dirs = [str(d) for d in (layers.get("src") or []) + (layers.get("test") or [])]
    exts = {str(e) for e in (cfg.get("scan_ext") or [])}
    skip = [to_regex(p) for p in (structure.get("exclude") or [])]
    out = []
    for name in dirs:
        base = ROOT / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or (exts and path.suffix not in exts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            if not any(rx.match(rel) for rx in skip):
                out.append(path)
    return out


def check_lines(path: str, text: str, limit: int, errs: list) -> None:
    count = len(text.splitlines())
    if count > limit:
        errs.append(f"{path}: {count}行 — 上限{limit}行を超えている"
                    "(分割するか、structure.exclude に理由付きで加える)")


def python_tree(text: str):
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def check_functions(path: str, tree, limit: int, errs: list) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", None)
        if end and end - node.lineno + 1 > limit:
            errs.append(f"{path}:{node.lineno}: 関数 {node.name} が"
                        f"{end - node.lineno + 1}行 — 上限{limit}行を超えている")


def dotted(node) -> str:
    """呼び出し先の名前を a.b.c の形で返す。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def calls_in(node) -> list:
    return [dotted(sub.func) for sub in ast.walk(node) if isinstance(sub, ast.Call)]


def check_pure(path: str, tree, allow: set, errs: list) -> None:
    """import しただけで実行が始まらないこと。

    定義(import / def / class)だけを無条件に認める。式と代入は中身を見る。
    `print(...)` は式、`CLIENT = connect()` は代入であり、どちらも import した
    瞬間に走る。種類だけで通すと、この2つが素通りする。

    代入の中の呼び出しは既定で赤。`Path(__file__)` のような定義時に済ませたい
    ものは structure.pure_allow_calls に明記する(免除を書かせる)。
    """
    for node in tree.body:
        if isinstance(node, PURE_DEFS):
            continue
        if isinstance(node, ast.Expr):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                continue                      # docstring は実行しても何も起きない
            errs.append(f"{path}:{node.lineno}: モジュール直下に式がある"
                        " — import しただけで実行が始まる")
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = getattr(node, "value", None)
            if value is None:
                continue
            bad = [name for name in calls_in(value)
                   if name not in allow and name.split(".")[-1] not in allow]
            if bad:
                errs.append(f"{path}:{node.lineno}: モジュール直下の代入が"
                            f" {bad[0]}() を呼んでいる — import しただけで実行が始まる"
                            "(定義時に必要なら structure.pure_allow_calls に明記する)")
            continue
        if isinstance(node, ast.If):
            test = node.test
            # if __name__ == "__main__": は入口として認める
            if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"):
                continue
        errs.append(f"{path}:{node.lineno}: モジュール直下に"
                    f"{type(node).__name__} がある — import しただけで実行が始まる")


def layer_of(rel: str, layers: list) -> dict | None:
    for layer in layers:
        if to_regex(str(layer.get("path", ""))).match(rel):
            return layer
    return None


def check_layers(rel: str, text: str, layers: list, errs: list) -> None:
    """層の依存方向。import の文字列に他層のディレクトリ名が現れるかを見る。

    発見的な検査である。層が宣言されていないときは何もしない。
    """
    here = layer_of(rel, layers)
    if here is None:
        return
    allowed = {str(x) for x in (here.get("may_import") or [])} | {here["name"]}
    # 層名 -> その層のパスに現れる特徴的なディレクトリ名
    marks = {str(other["name"]): str(other.get("path", "")).strip("*/").split("/")[-1]
             for other in layers}
    for lineno, line in enumerate(text.splitlines(), 1):
        target = ""
        for pattern in IMPORT_PATTERNS:
            m = pattern.match(line) or pattern.search(line)
            if m:
                target = m.group(1)
                break
        if not target:
            continue
        segments = set(re.split(r"[./\\]", target))
        for name, mark in marks.items():
            if name in allowed or not mark:
                continue
            if mark in segments:
                errs.append(f"{rel}:{lineno}: {here['name']} 層が {name} 層を"
                            f"import している — 許可は {sorted(allowed)}")
                break


def main() -> int:
    use_utf8()
    cfg = load_config()
    structure = cfg.get("structure") or {}
    if not structure:
        print("構造: 未装備(project.yaml の structure 節が無い)")
        return UNARMED

    max_file = structure.get("max_file_lines")
    max_func = structure.get("max_function_lines")
    layers = [dict(x) for x in (structure.get("layers") or [])]
    pure = [to_regex(p) for p in (structure.get("pure_modules") or [])]
    exempt = [to_regex(p) for p in (structure.get("pure_exempt") or [])]
    allow = {str(x) for x in (structure.get("pure_allow_calls") or [])}
    if not any((max_file, max_func, layers, pure)):
        print("構造: 未装備(structure に規範が1つも書かれていない)")
        return UNARMED

    files = sources(cfg, structure)
    if not files:
        print("構造: 未装備(検査対象のファイルが無い — layers.src / scan_ext を確認)")
        return UNARMED

    errs: list[str] = []
    checked_py = 0
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if max_file:
            check_lines(rel, text, int(max_file), errs)
        if layers:
            check_layers(rel, text, layers, errs)
        if path.suffix != ".py":
            continue
        tree = python_tree(text)
        if tree is None:
            continue
        checked_py += 1
        if max_func:
            check_functions(rel, tree, int(max_func), errs)
        if any(rx.match(rel) for rx in pure) and not any(rx.match(rel) for rx in exempt):
            check_pure(rel, tree, allow, errs)

    if errs:
        print(f"NG: 構造規範に反する箇所が{len(errs)}件", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        print("  規範の定義は project.yaml の structure 節。散文で層やサイズを語らない",
              file=sys.stderr)
        return 1
    print(f"OK: 構造規範 — {len(files)}ファイル(うちPython {checked_py})に違反なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
