#!/usr/bin/env python3
"""設定検査(潮路キット)— project.yaml 自体を検証する。

project.yaml はプロセス設定のSSoTだが、これまで誰も検査していなかった。
run_gates.py は safe_load して即実行するため、誤設定は重い検査の後半まで
検出されないか、黙って別の意味で解釈される(例: match: exatc は ordered に
フォールバックしていた)。

ゲート列の先頭に置き、fail-fast させる。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "docs" / "spec"
SCHEMA_VERSION = 2

PREFIX_RE = re.compile(r"^[A-Z]{2,5}$")
MATCH_KINDS = {"exact", "ordered"}

# v1 -> v2 で置き換えたキー。残っていたら移行を促して止める。
LEGACY = {
    "req_prefix": "requirements.prefix",
    "spec_glob": "requirements.active_spec(明示指定)",
}


def load() -> dict:
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("ERROR: pyyaml がない — 自己修復: python -m pip install -r requirements.txt (CLAUDE.md §8)")
    path = ROOT / "project.yaml"
    if not path.exists():
        sys.exit("ERROR: project.yaml がない(プロセス設定のSSoT)")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        sys.exit(f"ERROR: project.yaml を解釈できない: {error}")


def is_argv(value) -> bool:
    """argv 形式(非空の文字列リスト)か。"""
    return (isinstance(value, list) and value
            and all(isinstance(x, str) and x.strip() for x in value))


def num_in(errs: list, key: str, value, lo: float, hi: float | None) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errs.append(f"{key}: 数値でない({value!r})")
        return
    if value < lo or (hi is not None and value > hi):
        span = f"{lo}以上" if hi is None else f"{lo}〜{hi}"
        errs.append(f"{key}: {span}にする({value})")


def check_spec(errs: list, spec: str) -> None:
    """active_spec は L1 の実在ファイルで、status: active であること。

    包含判定は解決後のパスで行う。文字列の前方一致では
    docs/spec/../../../PROCESS.md のような指定が通ってしまい、L1 の外にある
    文書(status: active を持つ)が正典の仕様書として扱われる。
    resolve() はシンボリックリンクも辿るため、リンクによる脱出も塞がる。
    """
    path = ROOT / spec
    if not path.exists():
        errs.append(f"requirements.active_spec: ファイルが無い({spec})")
        return
    resolved = path.resolve()
    if not resolved.is_relative_to(SPEC_DIR.resolve()):
        errs.append(f"requirements.active_spec: L1(docs/spec/)の外を指している"
                    f"({spec} → {resolved})")
        return
    head = path.read_text(encoding="utf-8")[:800]
    status = re.search(r"^status:\s*(\S+)\s*$", head, re.MULTILINE)
    if not status:
        errs.append(f"requirements.active_spec: front-matter に status が無い({spec})")
    elif status.group(1) != "active":
        errs.append(f"requirements.active_spec: status が active でない"
                    f"({status.group(1)} — 改版したら active_spec を差し替える)")


def check_gates(errs: list, gates) -> None:
    if not isinstance(gates, list) or not gates:
        errs.append("gates: 非空のリストにする")
        return
    for i, gate in enumerate(gates):
        at = f"gates[{i}]"
        if not isinstance(gate, dict):
            errs.append(f"{at}: マッピングにする")
            continue
        if not str(gate.get("id", "")).strip():
            errs.append(f"{at}.id: 必須")
        if "cmd" in gate:
            errs.append(f"{at}.cmd: v2 では argv 形式にする"
                        f"(例: argv: [python, scripts/xxx.py])。shell を経由しない")
        if not is_argv(gate.get("argv")):
            errs.append(f"{at}.argv: 非空の文字列リストにする")
        cut = gate.get("cutover")
        if cut is None:
            continue
        if not isinstance(cut, dict):
            errs.append(f"{at}.cutover: マッピングにする")
            continue
        if "cmd" in cut:
            errs.append(f"{at}.cutover.cmd: v2 では argv 形式にする")
        if not is_argv(cut.get("argv")):
            errs.append(f"{at}.cutover.argv: 非空の文字列リストにする")
        if not str(cut.get("by_task", "")).strip():
            errs.append(f"{at}.cutover.by_task: 必須"
                        f"(期限が無いと、未装備のまま忘れられる)")


def check_stack(errs: list, stack) -> None:
    if not isinstance(stack, dict):
        errs.append("stack: マッピングにする")
        return
    for key in ("app_manifest", "ready_marker"):
        if not isinstance(stack.get(key, ""), str):
            errs.append(f"stack.{key}: 文字列にする(未設定は空文字)")
    for key in ("analyze", "test"):
        value = stack.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, str):
            errs.append(f"stack.{key}: v2 では argv のリストにする"
                        f"(例: [[ruff, check, .]])。shell を経由しない")
            continue
        if not isinstance(value, list) or not all(is_argv(v) for v in value):
            errs.append(f"stack.{key}: argv のリストにする(例: [[cmd, arg], [cmd2, arg2]])")


def check_structure(errs: list, warns: list, structure) -> None:
    if not isinstance(structure, dict):
        errs.append("structure: マッピングにする")
        return
    for key in ("max_file_lines", "max_function_lines"):
        if key in structure:
            num_in(errs, f"structure.{key}", structure[key], 1, None)
    for key in ("exclude", "pure_modules", "pure_exempt"):
        value = structure.get(key)
        if value is not None and (not isinstance(value, list) or not all(
                isinstance(x, str) for x in value)):
            errs.append(f"structure.{key}: 文字列リストにする")
    layers = structure.get("layers")
    if layers is None:
        layers = []
    if not isinstance(layers, list):
        errs.append("structure.layers: リストにする")
        return
    names = set()
    for i, layer in enumerate(layers):
        at = f"structure.layers[{i}]"
        if not isinstance(layer, dict):
            errs.append(f"{at}: マッピングにする(name / path / may_import)")
            continue
        name = str(layer.get("name", "")).strip()
        if not name:
            errs.append(f"{at}.name: 必須")
        elif name in names:
            errs.append(f"{at}.name: 重複している({name})")
        names.add(name)
        if not str(layer.get("path", "")).strip():
            errs.append(f"{at}.path: 必須(glob)")
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        for target in (layer.get("may_import") or []):
            if str(target) not in names:
                errs.append(f"structure.layers[{i}].may_import: 未知の層 {target!r}"
                            " — 綴りを確認する(未知の層は許可として効かない)")
    if not any(structure.get(k) for k in
               ("max_file_lines", "max_function_lines", "layers", "pure_modules")):
        warns.append("structure に規範が1つも書かれていない — 構造検査は未装備のまま")


def check_protected(errs: list, warns: list, protected) -> None:
    if not isinstance(protected, dict):
        errs.append("protected: マッピングにする(paths / keys / by_task)")
        return
    paths = protected.get("paths")
    if paths in (None, []):
        warns.append("protected.paths が空 — 人間専管のファイルが機械的に守られない")
    elif not isinstance(paths, list) or not all(
            isinstance(x, str) and x.strip() for x in paths):
        errs.append("protected.paths: 非空の文字列リストにする")
    keys = protected.get("keys")
    if keys is not None and (not isinstance(keys, list) or not all(
            isinstance(x, str) for x in keys)):
        errs.append("protected.keys: 文字列リストにする(project.yaml の節名)")
    if "by_task" in protected and not str(protected["by_task"]).strip():
        errs.append("protected.by_task: 空にしない(未装備の期限)")


def check_oracle(errs: list, warns: list, oracle) -> None:
    if not isinstance(oracle, dict):
        errs.append("oracle: マッピングにする")
        return
    if oracle.get("enabled") is False:
        return
    kind = oracle.get("match", "exact")
    if kind not in MATCH_KINDS:
        errs.append(f"oracle.match: {sorted(MATCH_KINDS)} のいずれかにする({kind!r})"
                    f" — 未知の値を黙って ordered に落とさない")
    for key in ("reference_dir", "predictions_dir"):
        if not str(oracle.get(key, "")).strip():
            errs.append(f"oracle.{key}: 必須")
    # 予測の再生成は predictions_dir の *.csv を消してから行う。
    # そこが参照オラクルと同じ・入れ子だと、人間専管の参照データを消したうえで
    # 同じファイルを参照とも予測とも読むことになり、必ず一致して緑になる。
    ref_dir, pred_dir = (str(oracle.get(k, "")).strip()
                         for k in ("reference_dir", "predictions_dir"))
    if ref_dir and pred_dir:
        r, p = (ROOT / ref_dir).resolve(), (ROOT / pred_dir).resolve()
        if r == p or p.is_relative_to(r) or r.is_relative_to(p):
            errs.append("oracle.predictions_dir: reference_dir と同じ・入れ子にしない"
                        f"({pred_dir} / {ref_dir}) — 予測の再生成が参照オラクルを消し、"
                        "同じファイルを参照と予測の両方として読んで必ず緑になる")
    # 予測を毎回作り直せないと、実装を壊しても古い予測のまま合格しうる。
    if not is_argv(oracle.get("generate")):
        errs.append("oracle.generate: 必須(argv 形式)。現在のコードから予測を"
                    "再生成する手順が無いと、古い予測のまま合格しうる")
    # validate_oracle.py が無条件に参照するキー。欠けていると、参照CSVを
    # 投入した時点で KeyError で落ちる。設定検査の時点で必須にする。
    if not str(oracle.get("order_by", "")).strip():
        errs.append("oracle.order_by: 必須(整列に使う列。欠けると照合時に落ちる)")
    if "order_tolerance" not in oracle:
        errs.append("oracle.order_tolerance: 必須(order_by の許容。欠けると照合時に落ちる)")
    if "pass_rate" in oracle:
        num_in(errs, "oracle.pass_rate", oracle["pass_rate"], 0, 1)
    if "order_tolerance" in oracle:
        num_in(errs, "oracle.order_tolerance", oracle["order_tolerance"], 0, None)
    if "order_window" in oracle:
        num_in(errs, "oracle.order_window", oracle["order_window"], 0, None)
    values = oracle.get("values")
    if values is not None and (not isinstance(values, dict) or not values):
        errs.append("oracle.values: 非空のマッピングにする(値列 → 絶対許容誤差)")
    for key in ("f1_min",):
        if key in oracle:
            errs.append(f"oracle.{key}: oracle.metrics の中に置く")
    metrics = oracle.get("metrics")
    if metrics is None:
        warns.append("oracle.metrics が未設定 — pass_rate を recall として使い、"
                     "precision は無制限になる(誤検出を何件出しても合格しうる)。"
                     "metrics.recall_min / precision_min の設定を検討すること")
        return
    if not isinstance(metrics, dict) or not metrics:
        errs.append("oracle.metrics: 非空のマッピングにする")
        return
    # 綴り違いを黙って無視しない。metrics が非空であれば thresholds() は
    # そちらを採用し、認識できないキーしか無い場合は基準が 0 になる。
    # つまり recall_mim と書いた瞬間、TPが0でも合格する状態になる。
    known = {"recall_min", "precision_min", "f1_min"}
    unknown = sorted(set(metrics) - known)
    if unknown:
        errs.append(f"oracle.metrics: 未知のキー {unknown} — 綴りを確認する"
                    "(認識されないキーは判定に効かず、ゲートが無効になる)")
    if not (set(metrics) & known):
        errs.append(f"oracle.metrics: {sorted(known)} のいずれかを設定する")
    for key in sorted(known):
        if key in metrics:
            num_in(errs, f"oracle.metrics.{key}", metrics[key], 0, 1)


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

    cfg = load()
    errs: list[str] = []
    warns: list[str] = []

    version = cfg.get("schema_version")
    if version != SCHEMA_VERSION:
        errs.append(f"schema_version: {SCHEMA_VERSION} にする(現在: {version!r})"
                    f" — 移行は scripts/migrate_config.py を参照")
    for old, new in LEGACY.items():
        if old in cfg:
            errs.append(f"{old}: v2 では {new} を使う。古いキーは削除する")

    if not str(cfg.get("project", "")).strip():
        errs.append("project: 必須")

    req = cfg.get("requirements")
    if not isinstance(req, dict):
        errs.append("requirements: マッピングにする(prefix / active_spec)")
    else:
        prefix = str(req.get("prefix", "")).strip()
        if not PREFIX_RE.match(prefix):
            errs.append(f"requirements.prefix: 大文字英字2〜5字にする({prefix!r})")
        spec = str(req.get("active_spec", "")).strip()
        if spec:
            check_spec(errs, spec)

    layers = cfg.get("layers")
    if not isinstance(layers, dict):
        errs.append("layers: マッピングにする(src / test)")
    else:
        for key in ("src", "test"):
            value = layers.get(key)
            if not isinstance(value, list) or not value:
                errs.append(f"layers.{key}: 非空のリストにする")

    check_gates(errs, cfg.get("gates"))
    if cfg.get("protected") is not None:
        check_protected(errs, warns, cfg["protected"])
    if cfg.get("structure") is not None:
        check_structure(errs, warns, cfg["structure"])
    check_stack(errs, cfg.get("stack"))
    if cfg.get("oracle") is not None:
        check_oracle(errs, warns, cfg["oracle"])

    for w in warns:
        print(f"  警告: {w}")
    if errs:
        print("NG: project.yaml の設定に問題がある", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("OK: project.yaml の設定に問題なし"
          + (f"(警告 {len(warns)}件)" if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
