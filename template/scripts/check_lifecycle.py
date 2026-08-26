#!/usr/bin/env python3
"""ライフサイクル検査(潮路キット)— 段階と実体が食い違っていないか。

「インセプションが終わるまで実装を始めない」は文書に書いてあるだけで、
機械的には何も止めていなかった。逆に、実装が始まっているのに段階が
`inception` のままだと、仕様もスタックも無いことが正当化され続ける。

段階は `project.yaml` の `lifecycle.phase` が持つ。人間が進める。

  inception    仕様を決める段階。実装が始まっていたら赤
  development  作る段階。仕様とスタックが決まっていなければ赤

どちらの向きにも赤があるのが要点で、片方だけだと「段階を進めない」または
「段階だけ進める」で回避できてしまう。

**実装の検出は設定に依存させない。** `layers.src` を別の場所へ向ける、
`scan_ext` を狭める、`stack.ready_marker` を存在しないパスにする、のいずれでも
実装が見えなくなる。設定はエージェントが提案できる（`stack` の調整は
CLAUDE.md §4 で認められている）ため、検出方針を設定から読むと、
弱めるコミット自身が弱めたあとの方針で検査される（PROCESS.md §5-17 の2）。
固定のディレクトリ名とマニフェスト名を併せて見る。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNARMED = 3                       # 未装備(run_gates.py が「緑」と区別して数える)
PHASES = ("inception", "development")

# 実装が始まったことを示す固定の手がかり。設定で狭められないようにする。
SOURCE_DIRS = ("src", "lib", "app")
MANIFESTS = ("pubspec.yaml", "package.json", "pyproject.toml", "setup.py",
             "Cargo.toml", "go.mod", "build.gradle", "build.gradle.kts")
IGNORED = {".gitkeep", ".gitignore"}


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


def source_files(cfg: dict) -> list:
    """実装が始まっていることを示すファイル。

    設定の layers.src だけを見ると、そこを別の場所へ向けるだけで実装が
    見えなくなる。固定のディレクトリ名を併せて見る。拡張子でも絞らない
    （scan_ext を狭めれば同じ回避ができるため）。
    """
    layers = cfg.get("layers") or {}
    names = {str(n) for n in (layers.get("src") or [])} | set(SOURCE_DIRS)
    out = []
    for name in sorted(names):
        base = ROOT / name
        if not base.is_dir():
            continue
        out += [p for p in base.rglob("*")
                if p.is_file() and p.name not in IGNORED
                and not p.name.startswith(".")
                and "__pycache__" not in p.parts]
    return out


def manifests(cfg: dict) -> list:
    """依存台帳。設定の ready_marker だけでなく、既知の名前も見る。"""
    marker = str((cfg.get("stack") or {}).get("ready_marker") or "").strip()
    names = set(MANIFESTS) | ({marker} if marker else set())
    return sorted(n for n in names if (ROOT / n).exists())


def check_inception(cfg: dict, errs: list) -> None:
    """仕様を決める段階。実装が始まっていたら赤。"""
    found = manifests(cfg)
    if found:
        errs.append(f"インセプション中に依存台帳がある({', '.join(found)}) —"
                    " スタックの初期化はインセプション完了後"
                    "(lifecycle.phase を development にする)")
    files = source_files(cfg)
    if files:
        sample = ", ".join(p.relative_to(ROOT).as_posix() for p in files[:3])
        errs.append(f"インセプション中に実装層のファイルが{len(files)}件ある({sample}) —"
                    " 仕様を決めてから実装を始める")


def check_development(cfg: dict, errs: list) -> None:
    """作る段階。仕様とスタックが決まっていなければ赤。"""
    if not str((cfg.get("requirements") or {}).get("active_spec") or "").strip():
        errs.append("development なのに requirements.active_spec が空 —"
                    " インセプションの成果物(仕様書)が無い")
    if not str((cfg.get("stack") or {}).get("ready_marker") or "").strip():
        errs.append("development なのに stack.ready_marker が空 —"
                    " スタックが決まっておらず、静的解析もテストも走らない(T-001)")


def main() -> int:
    use_utf8()
    cfg = load_config()
    lifecycle = cfg.get("lifecycle") or {}
    if not lifecycle:
        print("ライフサイクル: 未装備(project.yaml の lifecycle 節が無い)")
        return UNARMED

    phase = str(lifecycle.get("phase", "")).strip()
    if phase not in PHASES:
        print(f"NG: lifecycle.phase は {list(PHASES)} のいずれかにする({phase!r})",
              file=sys.stderr)
        return 1

    errs: list[str] = []
    if phase == "inception":
        check_inception(cfg, errs)
    else:
        check_development(cfg, errs)

    if errs:
        print(f"NG: 段階({phase})と実体が食い違っている", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        print("  段階を進めるのは人間の判断。lifecycle.phase は protected.keys が守る",
              file=sys.stderr)
        return 1
    print(f"OK: 段階は {phase} — 実体と食い違いなし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
