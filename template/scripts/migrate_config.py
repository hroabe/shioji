#!/usr/bin/env python3
"""project.yaml を v1 から v2 へ移行する(潮路キット)。

project.yaml は「生成後プロジェクト側の所有物」で copier update が上書き
しないため、schema_version を上げても既存プロジェクトは自動では移行しない。
移行手段を用意しないと、v1 のまま取り残される。

v1 -> v2 の差分:
  req_prefix          -> requirements.prefix
  spec_glob           -> requirements.active_spec(1件に明示指定)
  gates[].cmd         -> gates[].argv(shell を経由しない)
  gates[].cutover.cmd -> gates[].cutover.argv
  stack.analyze/test  -> argv のリスト
  (追加) schema_version: 2 / stack.by_task
  (除去) gates 内の設定検査・保護パス検査 — run_gates.py の組み込みになったため

  引数なし : 変換結果を標準出力に出す(ファイルは変更しない)
  --write  : project.yaml を上書きする
"""
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "project.yaml"


def to_argv(value) -> list:
    """文字列コマンドを argv へ。既に argv ならそのまま。"""
    if isinstance(value, list):
        return [str(x) for x in value]
    return shlex.split(str(value))


def resolve_spec(glob: str, notes: list) -> str:
    """spec_glob から active_spec を決める。1件に定まらなければ空にする。"""
    hits = sorted(ROOT.glob(glob))
    if len(hits) == 1:
        return hits[0].relative_to(ROOT).as_posix()
    if not hits:
        notes.append(f"spec_glob({glob})に一致する仕様書が無い — active_spec は空にした")
        return ""
    names = ", ".join(h.name for h in hits)
    notes.append(f"spec_glob({glob})に{len(hits)}件が一致した({names})。"
                 "どれが有効かは人間が決める — active_spec を手で埋めること")
    return ""


# v1 で使い、v2 で別の場所へ移したキー。これ以外は素通しする。
DROPPED = {"schema_version", "req_prefix", "spec_glob"}


def migrate(cfg: dict, notes: list) -> dict:
    """v1 の設定を v2 へ。**既知のキーだけを拾い直さない。**

    project.yaml は生成後プロジェクトの所有物で、独自ゲートのための固有の節を
    持ちうる。ホワイトリストで組み直すと、そうした節が黙って消え、残ったゲートが
    設定を失ったまま走る。v1 のキーだけを変換し、他はそのまま残す。
    """
    out: dict = {"schema_version": 2}
    out.update({k: v for k, v in cfg.items() if k not in DROPPED})

    req = dict(out.get("requirements") or {})
    req.setdefault("prefix", cfg.get("req_prefix", ""))
    if "active_spec" not in req:
        glob = str(cfg.get("spec_glob") or "")
        req["active_spec"] = resolve_spec(glob, notes) if glob else ""
    out["requirements"] = req

    stack = dict(out.get("stack") or {})
    stack.setdefault("by_task", "T-001")
    for key in ("analyze", "test"):
        value = stack.get(key)
        if value in (None, "", []):
            stack[key] = []
        elif isinstance(value, str):
            # `a && b` は2コマンドとして分ける。shell を経由しないため。
            stack[key] = [to_argv(part) for part in value.split("&&") if part.strip()]
        elif value and not isinstance(value[0], list):
            stack[key] = [to_argv(value)]
    out["stack"] = stack

    gates = []
    for gate in out.get("gates") or []:
        g = dict(gate)
        if "cmd" in g:
            g["argv"] = to_argv(g.pop("cmd"))
        cut = g.get("cutover")
        if isinstance(cut, dict) and "cmd" in cut:
            cut = dict(cut)
            cut["argv"] = to_argv(cut.pop("cmd"))
            if not cut.get("by_task"):
                cut["by_task"] = "T-003"
                notes.append("cutover.by_task が無いので T-003 を仮置きした — "
                             "TASK_INDEX の実在タスクに合わせること")
            g["cutover"] = cut
        gates.append(g)
    # 設定検査は run_gates.py の組み込みになったので gates 列には入れない。
    # v1 で明示的に置かれていた場合は取り除く(二重実行を避ける)。
    builtin = ("check_project_config.py", "check_protected_paths.py")
    gates = [g for g in gates
             if not any(b in str(a) for a in (g.get("argv") or []) for b in builtin)]
    out["gates"] = gates
    return out


def use_utf8() -> None:
    """自分の出力を UTF-8 に固定する。

    Windows の既定は cp932 で、日本語や — を含む出力が UnicodeEncodeError で
    落ちる。run_gates.py 経由なら子プロセスに PYTHONUTF8 が渡るが、この
    スクリプトは単体でも実行される(CLAUDE.md §4)。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    use_utf8()
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("ERROR: pyyaml がない — python -m pip install -r requirements.txt")
    if not CONFIG.exists():
        sys.exit("ERROR: project.yaml がない")

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    if cfg.get("schema_version") == 2:
        print("project.yaml は既に v2 — 移行するものはない")
        return 0

    notes: list[str] = []
    out = migrate(cfg, notes)
    text = yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=100)

    if "--write" in sys.argv[1:]:
        CONFIG.write_text(text, encoding="utf-8")
        print(f"project.yaml を v2 へ書き換えた({CONFIG.relative_to(ROOT)})")
        print("注意: コメントは失われる。編集規則のコメントを書き戻すこと")
    else:
        print(text)
        print("# --- 上は変換結果。ファイルは変更していない。"
              "適用するなら --write（コメントは失われる）", file=sys.stderr)

    for note in notes:
        print(f"  要確認: {note}", file=sys.stderr)
    print("  移行後は python scripts/check_project_config.py で検査すること",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
