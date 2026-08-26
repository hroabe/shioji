#!/usr/bin/env python3
"""実機確認の痕跡(潮路キット)— done にしたタスクを人間が実機で確かめたか。

ゲートには原理的に見えないものがある。**新鮮で、非空で、しかし利用者に届く
ものとは別の対象を検証している**場合である。

  実例: 196件のテストがすべて緑のまま、機能3つが画面に一度も表示されていな
  かった。テストは毎回新しく生成された文字列を検証していたが、フレームワーク
  が実際に配信するのは別のオブジェクトだった。古くもなく、空でもなく、
  見ている対象そのものが違っていた。

これは機械では検出できない。できるのは「人間が実機を触った痕跡を要求する」
ことだけである。`docs/L3/PROGRESS.md` に確認の記録が無ければ、タスクを
`done` にできないようにする。

**確認の記録は、人間のコミットで入ったことを求める。** 記録は自由記入の
文字列なので、エージェント自身が書けてしまう。確認状態がそのタスクについて
成立した(無い→有る)コミットが `Agent:` トレーラを持たないことを、
コミット履歴から確かめる。エージェントが3行記帳し、人間が確認の行だけを
**別コミットで**足す、という分担になる。

限界: トレーラを書かないエージェントは人間として通る。これは早期検出であり
紙の契約である(§3.5-6.5 と同じ)。最終的にはレビューが担う。

対象は **base..HEAD で done になったタスク**に限る。過去に完了したタスクを
遡って責めない。比較元が決められないときは未装備として報告する。
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNARMED = 3                       # 未装備(run_gates.py が「緑」と区別して数える)
NEWLINE = chr(10)

# 表の行: | T-001 | タスク | REQ | 依存 | 担当 | status |
TASK_ROW = re.compile(r"^\|\s*(T-\d+)\s*\|.*\|\s*([A-Za-z]+)\s*\|\s*$")
TASK_ID = re.compile(r"T-\d+")
AGENT_TRAILER = re.compile(r"^Agent:\s*\S", re.MULTILINE)


def use_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def git(*args) -> str | None:
    try:
        proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def load_config() -> dict:
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("ERROR: pyyaml がない — 自己修復: python -m pip install -r requirements.txt (CLAUDE.md §8)")
    path = ROOT / "project.yaml"
    if not path.exists():
        sys.exit("ERROR: project.yaml がない(プロセス設定のSSoT)")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def base_ref(argv: list) -> str | None:
    if "--base" in argv:
        return argv[argv.index("--base") + 1]
    for env in ("PROTECTED_BASE", "GITHUB_BASE_REF"):
        value = os.environ.get(env)
        if value:
            return value if env == "PROTECTED_BASE" else f"origin/{value}"
    head = git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if head:
        return head.strip().replace("refs/remotes/", "")
    for candidate in ("origin/main", "origin/master"):
        if git("rev-parse", "--verify", "--quiet", candidate):
            return candidate
    return None


def confirmed_in(text: str, marker: str) -> set:
    """このテキストで確認済みとみなせるタスクID。

    PROGRESS は「## 見出し + 3行以内の本文」で1エントリ。タスクIDと標識が
    同じ**エントリ**にあることを求める(同じ行に限ると書式と噛み合わず、
    文書全体で見ると別のタスクの確認で代用できる)。IDは語として照合する
    (部分一致だと T-001 が T-0010 の記録で通る)。
    """
    out: set = set()
    for block in sections(text):
        if marker in block:
            out |= set(TASK_ID.findall(block))
    return out


def sections(text: str) -> list:
    """`## ` 見出しごとの塊に分ける。見出しの前の文字列も1つの塊とする。"""
    out, current = [], []
    for line in text.splitlines():
        if line.startswith("## ") and current:
            out.append(NEWLINE.join(current))
            current = []
        current.append(line)
    if current:
        out.append(NEWLINE.join(current))
    return out


def statuses(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        m = TASK_ROW.match(line.rstrip())
        if m:
            out[m.group(1)] = m.group(2).lower()
    return out


def main() -> int:
    use_utf8()
    argv = sys.argv[1:]
    cfg = (load_config().get("progress") or {})
    if not cfg:
        print("実機確認: 未装備(project.yaml の progress 節が無い)")
        return UNARMED

    index = ROOT / str(cfg.get("task_index", "TASK_INDEX.md"))
    log = ROOT / str(cfg.get("file", "docs/L3/PROGRESS.md"))
    marker = str(cfg.get("marker", "確認:"))
    exempt = {str(t) for t in (cfg.get("exempt") or [])}
    if not index.exists():
        print(f"実機確認: 未装備(タスク表が無い: {index.name})")
        return UNARMED

    if git("rev-parse", "--git-dir") is None:
        print("実機確認: 未装備(gitリポジトリではない)")
        return UNARMED
    base = base_ref(argv)
    if not base or git("rev-parse", "--verify", "--quiet", base) is None:
        print(f"実機確認: 未装備(比較元を決められない: {base or 'origin なし'})")
        print("    --base か PROTECTED_BASE で明示できる")
        return UNARMED

    old_text = git("show", f"{base}:{index.relative_to(ROOT).as_posix()}")
    before = statuses(old_text) if old_text is not None else {}
    after = statuses(index.read_text(encoding="utf-8"))
    # base で done でなかったものが done になった分だけを見る。
    # 過去に完了したタスクを遡って責めない。
    newly = sorted(t for t, s in after.items()
                   if s == "done" and before.get(t) != "done" and t not in exempt)
    if not newly:
        print(f"実機確認: {base}..HEAD で done になったタスクなし — 対象なし")
        return 0

    # 確認の記録は「どの版のファイルにあるか」ではなく「誰のコミットで
    # 入ったか」で判定する。作業ツリーの文字列だけを見ると、エージェントが
    # 自分で「確認:」と書いて通れる。無い→有るの遷移が Agent: トレーラの
    # 無いコミットで起きたタスクだけを、人間が確認したものと認める。
    rel = log.relative_to(ROOT).as_posix()
    human_confirmed: set = set()
    agent_confirmed: set = set()
    for sha in (git("log", "--format=%H", "--", rel) or "").split():
        after_text = git("show", f"{sha}:{rel}") or ""
        parent = git("rev-parse", "--verify", "--quiet", f"{sha}^")
        before_text = (git("show", f"{parent.strip()}:{rel}") or "") if parent else ""
        gained = confirmed_in(after_text, marker) - confirmed_in(before_text, marker)
        if not gained:
            continue
        message = git("log", "-1", "--format=%B", sha) or ""
        if AGENT_TRAILER.search(message):
            agent_confirmed |= gained
        else:
            human_confirmed |= gained
    # 帰属は履歴で、存在は現在のファイルで見る。履歴だけだと、人間の確認を
    # 後から削除しても集合に残り続け、記録が無いのに通ってしまう。
    current = confirmed_in(log.read_text(encoding="utf-8") if log.exists() else "",
                           marker)
    missing = [t for t in newly
               if t not in human_confirmed or t not in current]

    for task in newly:
        mark = "×" if task in missing else "○"
        print(f"  {mark} {task}")
    if missing:
        print(f"NG: done にしたのに実機確認の記録が無いタスクが{len(missing)}件",
              file=sys.stderr)
        for task in missing:
            if task in human_confirmed and task not in current:
                why = "人間の確認はあったが、記録が後から削除されている"
            elif task in agent_confirmed and task in current:
                why = "確認の記録がエージェントのコミットで追加されている"
            else:
                why = f"「{marker}」を含むエントリが(コミット済みの履歴に)無い"
            print(f"  - {task}: {rel} — {why}", file=sys.stderr)
        if set(missing) & agent_confirmed:
            print("  確認の記帳は Agent: トレーラの無いコミットで行う"
                  "(エージェントが3行記帳し、人間が確認の行を別コミットで足す)",
                  file=sys.stderr)
        print("  ゲートは、利用者に届くものと別の対象を検証していても緑になりうる。"
              "人間が実機で確かめた痕跡を残すこと", file=sys.stderr)
        return 1
    print(f"OK: {base}..HEAD で done になった{len(newly)}件すべてに実機確認の記録あり")
    return 0


if __name__ == "__main__":
    sys.exit(main())
