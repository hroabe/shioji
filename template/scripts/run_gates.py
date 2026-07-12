#!/usr/bin/env python3
"""ゲート実行器(潮路キット)— project.yaml の gates 列を順に実行する。

make guard / pre-commit フック / CI guardrails の三箇所が本スクリプトを共有し、
ローカルとCIの乖離を作らない(PROCESS.md §5-4)。

  引数なし : gates 列のみ(= guard)
  --all    : gates + スタック検証(stack.analyze / stack.test)。
             stack.ready_marker が未設定・不在の間は自動skip(0日目から緑の原則)。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("ERROR: pyyaml がない — 自己修復: python -m pip install -r requirements.txt (CLAUDE.md §8)")
    path = ROOT / "project.yaml"
    if not path.exists():
        sys.exit("ERROR: project.yaml がない(プロセス設定のSSoT)")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run(label: str, cmd: str) -> None:
    # gates の "python ..." は現在のインタプリタ(venv/CI)で実行し、環境差を作らない
    if cmd.startswith("python "):
        cmd = f'"{sys.executable}" ' + cmd[len("python "):]
    print(f"== {label}: {cmd}", flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, shell=True)
    if proc.returncode != 0:
        sys.exit(f"NG: ゲート '{label}' が赤 (exit {proc.returncode})")


def main() -> int:
    cfg = load_config()
    for gate in cfg.get("gates") or []:
        run(str(gate.get("id", "?")), str(gate["cmd"]))
    if "--all" in sys.argv[1:]:
        stack = cfg.get("stack") or {}
        marker = str(stack.get("ready_marker") or "").strip()
        if not marker or not (ROOT / marker).exists():
            print(f"stack: 未初期化(ready_marker: {marker or '未設定'})— skip")
        else:
            for key in ("analyze", "test"):
                cmd = str(stack.get(key) or "").strip()
                if cmd:
                    run(f"stack.{key}", cmd)
    print("OK: 全ゲート緑")
    return 0


if __name__ == "__main__":
    sys.exit(main())
