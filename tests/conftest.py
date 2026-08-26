"""テンプレート同梱スクリプトの回帰テスト用の足場。

対象は `template/scripts/*.py`。生成先プロジェクトと同じ配置（ルートに
project.yaml と TASK_INDEX.md、scripts/ にスクリプト）を一時ディレクトリへ
作り、サブプロセスとして実行して終了コードと出力を見る。

スクリプトは ROOT を `Path(__file__).parent.parent` として解決するため、
import ではなく実行して確かめる。ゲートの契約は「終了コード」であり、
そこを直接検査するのが正しい。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

KIT = Path(__file__).resolve().parent.parent
SCRIPTS = KIT / "template" / "scripts"

UNARMED = 3

# 生成直後（stack=manual）と同じ内容。gates に設定検査・保護パス検査を
# 置かないのは、それらが run_gates.py の組み込みだから。
BASE_CONFIG = {
    "schema_version": 2,
    "project": "sazanami",
    "lifecycle": {"phase": "inception"},
    "requirements": {"prefix": "SZN", "active_spec": ""},
    "deprecated_reqs": [],
    "layers": {"src": ["src"], "test": ["tests"]},
    "scan_ext": [".py", ".md", ".ts", ".dart"],
    "l0_exempt": ["CLAUDE.md", "AGENTS.md"],
    "scan_exclude": ["docs/proposals"],
    "stack": {"by_task": "T-001", "app_manifest": "", "ready_marker": "",
              "analyze": [], "test": []},
    "gates": [
        {"id": "req-links", "argv": ["python", "scripts/check_req_links.py"]},
        {"id": "oracle",
         "argv": ["python", "scripts/validate_oracle.py", "--dry-run"],
         "cutover": {"argv": ["python", "scripts/validate_oracle.py", "--gate"],
                     "by_task": "T-003"}},
    ],
    "progress": {
        "by_task": "T-004",
        "file": "docs/L3/PROGRESS.md", "task_index": "TASK_INDEX.md",
        "marker": "確認:", "exempt": [],
    },
    "structure": {
        "by_task": "T-005",
        "max_file_lines": 400, "max_function_lines": 60,
        "exclude": ["**/*_generated.*"],
        "layers": [], "pure_modules": [], "pure_exempt": [],
    },
    "protected": {
        "by_task": "T-004",
        "paths": ["CLAUDE.md", "AGENTS.md", "docs/spec/**",
                  "verification/reference/**", "test/golden/**", "requirements.txt"],
        "keys": ["lifecycle", "oracle", "protected", "structure", "progress"],
    },
}

TASK_INDEX = """# TASK_INDEX

| ID | タスク | REQ | 依存 | 担当 | status |
|---|---|---|---|---|---|
| T-001 | スタック初期化 | — | — | A | todo |
| T-003 | 精度ゲートの装備 | — | — | H | todo |
| T-004 | 保護の配線 | — | — | H | todo |
| T-005 | 構造規範の確定 | — | — | H | todo |
"""


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        if value is None:
            out.pop(key, None)
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Project:
    """生成先プロジェクトを模した一時ディレクトリ。"""

    def __init__(self, root: Path):
        self.root = root
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        for name in ("docs/spec", "verification/reference", "test/golden", "src", "tests"):
            (root / name).mkdir(parents=True, exist_ok=True)
        for script in SCRIPTS.glob("*.py"):
            (root / "scripts" / script.name).write_bytes(script.read_bytes())
        hooks = root / "scripts" / "hooks"
        hooks.mkdir(exist_ok=True)
        (hooks / "pre-commit").write_bytes((SCRIPTS / "hooks" / "pre-commit").read_bytes())
        self.write("TASK_INDEX.md", TASK_INDEX)
        self.write("CLAUDE.md", "# CLAUDE.md\n")
        self.write("AGENTS.md", "# AGENTS.md\n")
        self.write("requirements.txt", "pyyaml==6.0.2\n")
        self.config(BASE_CONFIG)

    # --- ファイル ---

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def read_config(self) -> dict:
        return yaml.safe_load((self.root / "project.yaml").read_text(encoding="utf-8"))

    def config(self, cfg: dict = None, **over) -> dict:
        """設定を書く。cfg 省略時は現在の設定へ over を深くマージする。"""
        base = cfg if cfg is not None else self.read_config()
        merged = deep_merge(base, over) if over else dict(base)
        (self.root / "project.yaml").write_text(
            yaml.safe_dump(merged, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return merged

    def replace(self, key: str, value) -> dict:
        """節を丸ごと差し替える。deep_merge では消したキーが復活してしまう。"""
        cfg = self.read_config()
        if value is None:
            cfg.pop(key, None)
        else:
            cfg[key] = value
        return self.config(cfg)

    def develop(self, marker: str = "pyproject.toml") -> None:
        """開発段階として成立する状態にする（仕様 + スタック + phase）。

        lifecycle ゲートは inception 中の実装を赤にするため、スタック検証を
        使うテストはここを通す必要がある。
        """
        self.write("docs/spec/S.md", "---" + chr(10) + "status: active"
                   + chr(10) + "---" + chr(10))
        self.write(marker, "")
        self.config(requirements={"active_spec": "docs/spec/S.md"},
                    stack={"ready_marker": marker},
                    lifecycle={"phase": "development"})

    def task(self, task_id: str, status: str) -> None:
        path = self.root / "TASK_INDEX.md"
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"| {task_id} "):
                head, _, _ = line.rstrip().rpartition("|")
                head, _, _ = head.rstrip().rpartition("|")
                line = f"{head}| {status} |"
            out.append(line)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")

    # --- 実行 ---

    def run(self, script: str, *args: str, env: dict = None):
        environ = dict(os.environ)
        environ.setdefault("PYTHONUTF8", "1")
        if env:
            environ.update(env)
        return subprocess.run(
            [sys.executable, f"scripts/{script}", *args],
            cwd=self.root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=environ)

    def gates(self, *args: str, env: dict = None):
        return self.run("run_gates.py", *args, env=env)

    # --- git ---

    def git(self, *args: str):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")

    def git_init(self) -> None:
        self.git("init", "-q", "-b", "main")
        self.commit("初期", human=True)
        self.git("branch", "-q", "base")

    def commit(self, message: str, human: bool = False) -> str:
        """human=False ならエージェントのコミット(Agent: トレーラ付き)。"""
        body = message if human else f"{message}\n\nAgent: claude"
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com",
                 "commit", "-q", "-m", body)
        return self.git("rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path / "p")


def out(result) -> str:
    """終了コードの判定を助けるため、標準出力と標準エラーを合わせて返す。"""
    return (result.stdout or "") + (result.stderr or "")
