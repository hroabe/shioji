#!/usr/bin/env python3
"""ゲート実行器(潮路キット)— project.yaml の gates 列を順に実行する。

make guard / pre-commit フック / CI guardrails の三箇所が本スクリプトを共有し、
ローカルとCIの乖離を作らない(PROCESS.md §5-4)。

  引数なし : gates 列のみ(= guard)
  --all    : gates + スタック検証(stack.analyze / stack.test)。
             stack.ready_marker が未設定・不在の間は未装備扱い(0日目から緑の原則)。
  --strict : 未装備を赤とする。main / リリースで使う。

「未装備」と「合格」を分けて報告する:
  検証していないことと、検証して合格したことを、同じ緑にしてはならない。
  ゲートは終了コード 3 で「実行したが装備されていない」を自己申告できる。
  未装備には project.yaml の by_task で期限を持たせる。期限のタスクが done に
  なったのに装備されていなければ赤にする(カットオーバー忘れをCIが検出する)。
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNARMED = 3                       # ゲートが「未装備」を自己申告する終了コード
STATUS_PATH = ROOT / "verification" / "gate_status.json"
CONFIG_CHECK = ROOT / "scripts" / "check_project_config.py"
PROTECTED_CHECK = ROOT / "scripts" / "check_protected_paths.py"
STRUCTURE_CHECK = ROOT / "scripts" / "check_structure.py"
TASK_INDEX = ROOT / "TASK_INDEX.md"

# 表の行: | T-001 | タスク | REQ | 依存 | 担当 | status |
TASK_ROW = re.compile(r"^\|\s*(T-\d+)\s*\|.*\|\s*([A-Za-z]+)\s*\|\s*$")


def utf8_io() -> dict:
    """自分と子プロセスの入出力を UTF-8 に固定する。

    Windows の既定は cp932 で、日本語を含むゲート出力が UnicodeEncodeError で
    落ちる。pre-commit フックが PYTHONUTF8 を立てているのと同じ理由だが、
    make guard / CI から直接呼ばれる経路は保護されていなかった。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def load_config() -> dict:
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("ERROR: pyyaml がない — 自己修復: python -m pip install -r requirements.txt (CLAUDE.md §8)")
    path = ROOT / "project.yaml"
    if not path.exists():
        sys.exit("ERROR: project.yaml がない(プロセス設定のSSoT)")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def task_status(task_id: str | None) -> str | None:
    """TASK_INDEX.md から当該タスクの status を読む。表に無ければ None。"""
    if not task_id or not TASK_INDEX.exists():
        return None
    for line in TASK_INDEX.read_text(encoding="utf-8").splitlines():
        m = TASK_ROW.match(line.rstrip())
        if m and m.group(1) == task_id:
            return m.group(2).lower()
    return None


def run(label: str, argv: list, protocol: bool = True) -> bool:
    """ゲートを1件実行する。装備済みで合格なら True、未装備なら False。

    赤ならその場で終了する。

    argv 形式・shell=False で実行する。project.yaml はエージェントが編集
    できるため、そこに書かれた文字列をシェルに解釈させない。複雑な処理は
    シェルの一行ではなく scripts/*.py へ置く。

    protocol=False は、この規約を知らない任意のコマンド(stack.analyze /
    stack.test など)向け。終了コード 3 を未装備と解釈してはならない。
    pytest は exit 3 を internal error として使う — 規約を押し付けると
    クラッシュが緑になる。
    """
    argv = [str(a) for a in argv]
    # "python" は現在のインタプリタ(venv/CI)へ差し替え、環境差を作らない
    if argv and argv[0] == "python":
        argv[0] = sys.executable
    print(f"== {label}: {' '.join(argv)}", flush=True)
    try:
        proc = subprocess.run(argv, cwd=ROOT, env=utf8_io())
    except OSError as error:
        # shell を経由しないため、実行ファイルが PATH に無いと例外になる。
        # shell=True のときは非ゼロ終了で赤になっていた。トレースバックではなく
        # ゲートの赤として扱う。
        sys.exit("\n".join([
            f"NG: ゲート '{label}' のコマンドを実行できない: {argv[0]}",
            f"    {error}",
            "    実行ファイルが PATH にあるか、project.yaml の argv を確認すること",
        ]))
    if protocol and proc.returncode == UNARMED:
        return False
    if proc.returncode != 0:
        sys.exit(f"NG: ゲート '{label}' が赤 (exit {proc.returncode})")
    return True


def check_deadline(label: str, by_task: str | None) -> None:
    """未装備のまま期限のタスクが done になっていたら赤にする。"""
    if by_task and task_status(by_task) == "done":
        sys.exit(
            f"NG: ゲート '{label}' が未装備のまま {by_task} が done になっている。\n"
            f"    装備するか、{by_task} を done から戻すこと。"
        )


def report(results: list, strict: bool) -> int:
    green = [r for r in results if r["state"] == "pass"]
    unarmed = [r for r in results if r["state"] == "unarmed"]

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps({"strict": strict, "green": len(green),
                    "unarmed": len(unarmed), "gates": results},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    names = ", ".join(r["id"] for r in unarmed)
    summary = f"緑{len(green)}件 / 未装備{len(unarmed)}件" + (f" — {names}" if unarmed else "")

    # CI では PR 画面に未装備を出す。緑のチェックマークだけで判断させない。
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        rows = [f"| {r['id']} | {'緑' if r['state'] == 'pass' else '**未装備**'} | {r['note']} |"
                for r in results]
        with open(step_summary, "a", encoding="utf-8") as fp:
            fp.write("\n".join([f"### ゲート: {summary}", "",
                                "| ゲート | 状態 | 備考 |", "|---|---|---|", *rows]) + "\n")

    if unarmed and strict:
        print(f"NG: --strict では未装備を赤とする — {names}", file=sys.stderr)
        return 1
    print(f"OK: {summary}")
    return 0


def main() -> int:
    utf8_io()
    argv = sys.argv[1:]
    strict = "--strict" in argv
    cfg = load_config()
    results: list = []

    # 設定検査は gates 列に依存させない。
    # gates 自体が project.yaml の中にあるため、「設定を検査するゲート」を
    # 設定から消す・改名する・壊れたゲートの後ろへ移す、のどれでも強制が外れる。
    # 自分を検査する仕組みを、自分が編集できる場所に置かない。
    if not CONFIG_CHECK.exists():
        sys.exit("NG: scripts/check_project_config.py が無い(設定検査は必須)")
    run("config", ["python", CONFIG_CHECK.relative_to(ROOT).as_posix()])
    results.append({"id": "config", "state": "pass",
                    "note": "組み込み(gates 列に依存しない)"})

    # 保護パス検査も同じ理由で組み込みにする。gates 列に置くと、その行を消す
    # コミット自身が検査を素通りし、同じコミットで保護パスを書き換えられる。
    if not PROTECTED_CHECK.exists():
        sys.exit("NG: scripts/check_protected_paths.py が無い(保護パス検査は必須)")
    by_task = (cfg.get("protected") or {}).get("by_task")
    if run("protected", ["python", PROTECTED_CHECK.relative_to(ROOT).as_posix()]):
        results.append({"id": "protected", "state": "pass",
                        "note": "組み込み(gates 列に依存しない)"})
    else:
        check_deadline("protected", by_task)
        results.append({"id": "protected", "state": "unarmed",
                        "note": f"期限 {by_task}" if by_task else "期限なし"})

    # 構造検査も同じ理由で組み込みにする。閾値は protected.keys が守る。
    if not STRUCTURE_CHECK.exists():
        sys.exit("NG: scripts/check_structure.py が無い(構造検査は必須)")
    by_task = (cfg.get("structure") or {}).get("by_task")
    if run("structure", ["python", STRUCTURE_CHECK.relative_to(ROOT).as_posix()]):
        results.append({"id": "structure", "state": "pass",
                        "note": "組み込み(gates 列に依存しない)"})
    else:
        check_deadline("structure", by_task)
        results.append({"id": "structure", "state": "unarmed",
                        "note": f"期限 {by_task}" if by_task else "期限なし"})

    for gate in cfg.get("gates") or []:
        label = str(gate.get("id", "?"))
        builtin = ("check_project_config.py", "check_protected_paths.py",
                   "check_structure.py")
        if any(b in str(a) for a in (gate.get("argv") or []) for b in builtin):
            continue                      # 組み込みで実行済み
        if not gate.get("argv"):
            sys.exit(f"NG: ゲート '{label}' に argv がない。"
                     "v2 では cmd ではなく argv を使う"
                     "(python scripts/check_project_config.py で詳細が出る)")
        cmd = list(gate["argv"])
        cutover = gate.get("cutover") or {}
        by_task = cutover.get("by_task")

        # カットオーバー: 期限のタスクが done になったら装備側のコマンドへ切り替える。
        # 「--dry-run のまま忘れられる」を人間の記憶に頼らない。
        if by_task and task_status(by_task) == "done" and cutover.get("argv"):
            cmd = list(cutover["argv"])

        if run(label, cmd):
            results.append({"id": label, "state": "pass", "note": ""})
        else:
            check_deadline(label, by_task)
            results.append({"id": label, "state": "unarmed",
                            "note": f"期限 {by_task}" if by_task else "期限なし"})

    # 期限の検査は --all の有無に関わらず行う。
    # 「スタック検証を実行するか」と「期限を過ぎていないか」は別の問題であり、
    # guardrails(--all なし)でも期限切れは検出されなければならない。
    stack = cfg.get("stack") or {}
    marker = str(stack.get("ready_marker") or "").strip()
    ready = bool(marker) and (ROOT / marker).exists()
    if not ready:
        check_deadline("stack", stack.get("by_task"))

    if "--all" in argv:
        if not ready:
            note = f"ready_marker: {marker or '未設定'}"
            print(f"== stack: 未装備({note})", flush=True)
            results.append({"id": "stack", "state": "unarmed", "note": note})
        else:
            for key in ("analyze", "test"):
                cmds = stack.get(key) or []
                for n, cmd in enumerate(cmds, 1):
                    label = f"stack.{key}" if len(cmds) == 1 else f"stack.{key}#{n}"
                    # 任意のコマンドなので exit 3 も赤。protocol=False。
                    run(label, cmd, protocol=False)
                    results.append({"id": label, "state": "pass", "note": ""})

    return report(results, strict)


if __name__ == "__main__":
    sys.exit(main())
