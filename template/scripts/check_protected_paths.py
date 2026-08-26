#!/usr/bin/env python3
"""保護パス検査(潮路キット)— 人間専管のファイルをエージェントが変更していないか。

L0/L1 文書、参照オラクル、ゴールデン基準、依存台帳は人間専管である。しかし
「編集しない」と書いてあるだけで、機械的には何も止めていなかった。

検出できること・できないこと:
  できる   コミットが保護パスを変更したか
  できる   そのコミットがエージェントのものか(CLAUDE.md §3 の `Agent:` トレーラ)
  できない 変更者が本当に人間かどうか。トレーラを書かなければ回避できる

したがってこれは**早期検出**であり、最終的な強制ではない。強制は GitHub 側の
CODEOWNERS + 必須レビューが担う(PROCESS.md §8)。両方を置くこと。

  引数なし          origin の既定ブランチからの差分を見る
  --base <ref>      比較元を明示する
  環境変数          PROTECTED_BASE / GITHUB_BASE_REF も見る
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNARMED = 3                       # 未装備(run_gates.py が「緑」と区別して数える)

# CLAUDE.md §3 が要求するコミットトレーラ。エージェントの自己申告。
AGENT_TRAILER = re.compile(r"^Agent:\s*\S", re.MULTILINE)


def use_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def git(*args) -> str | None:
    """git を実行して標準出力を返す。失敗なら None。"""
    try:
        proc = subprocess.run(["git", *args], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8")
    except (OSError, ValueError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


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
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def base_ref(argv: list) -> str | None:
    """比較元を決める。決められなければ None(未装備)。"""
    if "--base" in argv:
        return argv[argv.index("--base") + 1]
    for env in ("PROTECTED_BASE", "GITHUB_BASE_REF"):
        value = os.environ.get(env)
        if value:
            return value if env == "PROTECTED_BASE" else f"origin/{value}"
    head = git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if head:
        return head.replace("refs/remotes/", "")
    for candidate in ("origin/main", "origin/master"):
        if git("rev-parse", "--verify", "--quiet", candidate):
            return candidate
    return None


def config_at(ref: str) -> dict | None:
    """指定の版の project.yaml を読む。無ければ None。"""
    text = git("show", f"{ref}:project.yaml")
    if text is None:
        return None
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except Exception:
        return None


def policy(base: str) -> tuple[list, list, str]:
    """保護方針は base(信頼できる版)から読む。

    現在の project.yaml から読むと、方針を弱めるコミット自身が、弱めたあとの
    方針で検査されてしまう。paths を1つ消し keys を空にすれば、その変更を含めて
    緑になる。方針を base に固定すれば、弱めても当のコミットは弾かれる。

    base に protected が無い場合(方針の新規導入)だけ、現在の値を使う。
    """
    cfg = config_at(base) or {}
    old = cfg.get("protected") or {}
    if old.get("paths"):
        return ([str(x) for x in old["paths"]],
                [str(k) for k in (old.get("keys") or [])],
                f"{base} の方針")
    cur = load_config().get("protected") or {}
    return ([str(x) for x in (cur.get("paths") or [])],
            [str(k) for k in (cur.get("keys") or [])],
            "現在の方針(base に protected が無い — 新規導入)")


def changed_keys(sha: str, keys: list) -> list:
    """このコミット単体で、人間専管の節が変わったか。

    base から最終形をまとめて比べると、人間が oracle を直しエージェントが stack を
    直しただけで、人間の変更をエージェントの違反として数えてしまう。
    コミットとその親を比べ、そのコミットが変えたものだけを見る。
    """
    if not keys:
        return []
    parent = git("rev-parse", "--verify", "--quiet", f"{sha}^")
    new = config_at(sha)
    if new is None or parent is None:
        return []
    old = config_at(parent) or {}
    return [k for k in keys if old.get(k) != new.get(k)]


def main() -> int:
    use_utf8()
    argv = sys.argv[1:]
    if git("rev-parse", "--git-dir") is None:
        print("保護パス: 未装備(gitリポジトリではない)")
        return UNARMED
    base = base_ref(argv)
    if not base or git("rev-parse", "--verify", "--quiet", base) is None:
        print(f"保護パス: 未装備(比較元を決められない: {base or 'origin なし'})")
        print("    --base か PROTECTED_BASE で明示できる")
        return UNARMED

    patterns, keys, source = policy(base)
    if not patterns:
        print("保護パス: 未装備(protected.paths が空)")
        return UNARMED

    commits = (git("log", "--format=%H", f"{base}..HEAD") or "").split()
    if not commits:
        print(f"保護パス: {base} からの新しいコミットなし — 対象なし")
        return 0

    matchers = [(p, to_regex(p)) for p in patterns]
    hits, human = [], []
    for sha in commits:
        files = (git("diff-tree", "--no-commit-id", "--name-only", "-r", sha) or "").splitlines()
        message = git("log", "-1", "--format=%B", sha) or ""
        by_agent = bool(AGENT_TRAILER.search(message))
        for path in files:
            for pattern, rx in matchers:
                if rx.match(path):
                    (hits if by_agent else human).append((sha[:7], path, pattern))
                    break
        if by_agent and "project.yaml" in files:
            for key in changed_keys(sha, keys):
                hits.append((sha[:7], f"project.yaml の {key} 節", "protected.keys"))

    for sha, path, pattern in human:
        print(f"  人間のコミット {sha}: {path}(保護 {pattern})")
    if human:
        print(f"保護パスの変更 {len(human)}件 — `Agent:` トレーラが無いため人間の変更として扱う",
              flush=True)

    if hits:
        print(f"NG: エージェントのコミットが保護パスを変更している({len(hits)}件)",
              file=sys.stderr)
        for sha, path, pattern in hits:
            print(f"  - {sha}: {path}(保護 {pattern})", file=sys.stderr)
        print("  これらは人間専管である。提案は docs/proposals/ へ置き、"
              "反映は人間が行うこと(CLAUDE.md §5)", file=sys.stderr)
        return 1

    print(f"OK: 保護パス{len(patterns)}件({source}) / {base}..HEAD の"
          f"{len(commits)}コミットにエージェントによる変更なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
