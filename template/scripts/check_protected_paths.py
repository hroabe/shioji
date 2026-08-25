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


def changed_keys(base: str, keys: list) -> list:
    """project.yaml の人間専管の節が base から変わっているか。

    project.yaml はパス単位では保護できない。gates への行追加や stack の調整は
    エージェントの提案が認められている一方、oracle の許容値や protected の定義は
    人間専管だからである。エージェントが自分を縛る設定を緩められることが、
    ここで一番避けたい事態になる。
    """
    if not keys:
        return []
    old_text = git("show", f"{base}:project.yaml")
    if old_text is None:
        return []                      # base に project.yaml が無い — 比較しない
    try:
        import yaml
        old = yaml.safe_load(old_text) or {}
    except Exception:
        return []
    new = load_config()
    return [k for k in keys if old.get(k) != new.get(k)]


def main() -> int:
    use_utf8()
    argv = sys.argv[1:]
    protected = (load_config().get("protected") or {})
    patterns = [str(p) for p in (protected.get("paths") or [])]
    keys = [str(k) for k in (protected.get("keys") or [])]
    if not patterns:
        print("保護パス: 未装備(project.yaml の protected.paths が空)")
        return UNARMED

    if git("rev-parse", "--git-dir") is None:
        print("保護パス: 未装備(gitリポジトリではない)")
        return UNARMED
    base = base_ref(argv)
    if not base or git("rev-parse", "--verify", "--quiet", base) is None:
        print(f"保護パス: 未装備(比較元を決められない: {base or 'origin なし'})")
        print("    --base か PROTECTED_BASE で明示できる")
        return UNARMED

    commits = (git("log", "--format=%H", f"{base}..HEAD") or "").split()
    if not commits:
        print(f"保護パス: {base} からの新しいコミットなし — 対象なし")
        return 0

    matchers = [(p, to_regex(p)) for p in patterns]
    hits, human = [], []
    agent_touched_config = False
    for sha in commits:
        files = (git("diff-tree", "--no-commit-id", "--name-only", "-r", sha) or "").splitlines()
        message = git("log", "-1", "--format=%B", sha) or ""
        by_agent = bool(AGENT_TRAILER.search(message))
        if by_agent and "project.yaml" in files:
            agent_touched_config = True
        for path in files:
            for pattern, rx in matchers:
                if rx.match(path):
                    (hits if by_agent else human).append((sha[:7], path, pattern))
                    break

    if agent_touched_config:
        for key in changed_keys(base, keys):
            hits.append(("project.yaml", f"{key} 節", "protected.keys"))

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

    print(f"OK: 保護パス{len(patterns)}件 / {base}..HEAD の{len(commits)}コミットに"
          "エージェントによる変更なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
