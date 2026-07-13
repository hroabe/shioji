#!/usr/bin/env python3
"""REQトレーサビリティ検査(潮路キット汎用版)。設定は project.yaml(プロセス設定のSSoT)。

検査内容:
  1. リポジトリ内で参照される REQ-<PFX>-xxx が仕様書(L1)に定義されていること
  2. 廃止REQ(deprecated_reqs)が仕様書・L0文書以外から参照されていないこと
  3. src層で参照されるREQは test層にも最低1箇所現れること(実装⇔テストのリンク)
  4. docs/ front-matter の status / TASK_INDEX の status が許可語彙であること

仕様書が未作成(インセプション前)の間は、REQ参照がゼロである限り skip で緑。
REQ参照があるのに仕様書が無い状態は赤(幽霊REQの禁止)。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_STATUS_OK = {"draft", "active", "review", "accepted", "superseded", "deprecated"}
TASK_STATUS_OK = {"todo", "doing", "review", "done", "blocked"}

errors: list[str] = []


def load_config() -> dict:
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("ERROR: pyyaml がない — 自己修復: python -m pip install -r requirements.txt (CLAUDE.md §8)")
    path = ROOT / "project.yaml"
    if not path.exists():
        sys.exit("ERROR: project.yaml がない(プロセス設定のSSoT)")
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def refs_in(path: Path, req_re: re.Pattern) -> set[str]:
    try:
        return set(req_re.findall(path.read_text(encoding="utf-8")))
    except (UnicodeDecodeError, OSError):
        return set()


def iter_files(dirs: list[str], scan_ext: set[str], skip: set[Path],
               exclude_prefixes: tuple[str, ...] = ()) -> list[Path]:
    out = []
    for d in dirs:
        base = ROOT / d
        if not base.exists():
            continue
        it = base.rglob("*") if d != "." else base.glob("*")
        for p in it:
            if not (p.is_file() and p.suffix in scan_ext and p.resolve() not in skip):
                continue
            rel = p.relative_to(ROOT).as_posix()
            if any(rel == pre or rel.startswith(pre + "/") for pre in exclude_prefixes):
                continue
            out.append(p)
    return out


def check_status_vocab() -> None:
    fm_re = re.compile(r"^status:\s*(\S+)", re.M)
    docs = ROOT / "docs"
    for p in docs.rglob("*.md") if docs.exists() else []:
        m = fm_re.search(p.read_text(encoding="utf-8")[:400])
        if m and m.group(1) not in DOC_STATUS_OK:
            errors.append(f"[status語彙] {p.relative_to(ROOT)}: '{m.group(1)}'")
    ti = ROOT / "TASK_INDEX.md"
    if ti.exists():
        for i, line in enumerate(ti.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("| T-"):
                cell = line.rstrip("|").split("|")[-1].strip()
                if cell not in TASK_STATUS_OK:
                    errors.append(f"[status語彙] TASK_INDEX.md:{i}: '{cell}'")


def main() -> int:
    cfg = load_config()
    prefix = str(cfg.get("req_prefix", "")).strip()
    if not prefix:
        sys.exit("ERROR: project.yaml に req_prefix がない")
    req_re = re.compile(rf"REQ-{re.escape(prefix)}-\d{{3}}")
    deprecated = {f"REQ-{prefix}-{int(n):03d}" for n in cfg.get("deprecated_reqs") or []}
    layers = cfg.get("layers") or {}
    src_dirs = [str(d) for d in layers.get("src") or []]
    test_dirs = [str(d) for d in layers.get("test") or []]
    scan_ext = {str(e) for e in cfg.get("scan_ext") or [".py", ".md", ".yaml", ".yml"]}
    scan_dirs = [*src_dirs, *test_dirs, "scripts", "docs", "data", "."]
    # 提案(docs/proposals)は下書き — 未定義/将来/却下のREQを含み得るのでREQ検査から除外。
    # インセプション出力(docs/proposals/inception)が仕様適用前にREQ IDを提案できる根拠。
    exclude = tuple(str(x).strip("/") for x in (cfg.get("scan_exclude") or ["docs/proposals"]))

    specs = sorted(ROOT.glob(str(cfg.get("spec_glob", "docs/spec/*SPEC*.md"))))
    spec = specs[-1] if specs else None

    skip = {Path(__file__).resolve()} | {(ROOT / n).resolve() for n in cfg.get("l0_exempt") or []}
    if spec is not None:
        skip.add(spec.resolve())

    # 1&2: 全スキャン
    all_refs: dict[Path, set[str]] = {}
    for p in iter_files(scan_dirs, scan_ext, skip, exclude):
        found = refs_in(p, req_re)
        if found:
            all_refs[p] = found

    if spec is None:
        if all_refs:
            for p, reqs in sorted(all_refs.items()):
                for req in sorted(reqs):
                    errors.append(f"[幽霊REQ] {p.relative_to(ROOT)}: {req}(仕様書が未作成)")
        else:
            print("spec: 未作成(インセプション前)・REQ参照なし — skip")
    else:
        defined = refs_in(spec, req_re)
        print(f"spec: {spec.relative_to(ROOT)} / 定義REQ {len(defined)}件 / 廃止 {len(deprecated)}件")
        for p, reqs in sorted(all_refs.items()):
            for req in sorted(reqs):
                if req in deprecated:
                    errors.append(f"[廃止REQ参照] {p.relative_to(ROOT)}: {req}")
                elif req not in defined:
                    errors.append(f"[未定義REQ] {p.relative_to(ROOT)}: {req}")

        # 3: 実装⇔テストリンク(src層が存在するときのみ)
        src_refs: set[str] = set()
        for p in iter_files(src_dirs, scan_ext, skip):
            src_refs |= refs_in(p, req_re)
        if src_refs:
            test_refs: set[str] = set()
            for p in iter_files(test_dirs, scan_ext, skip):
                test_refs |= refs_in(p, req_re)
            for req in sorted(src_refs - test_refs - deprecated):
                errors.append(f"[テスト未リンク] src層が参照する {req} が test層に現れない")

    # 4: status語彙
    check_status_vocab()

    if errors:
        print(f"NG: {len(errors)}件")
        for e in errors:
            print("  " + e)
        return 1
    print("OK: REQ整合・status語彙とも問題なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
