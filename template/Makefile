PY = $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || command -v python3 || echo python)
.PHONY: ci guard setup hooks
setup:
	@[ -d .venv ] || python3 -m venv .venv || python -m venv .venv
	@.venv/bin/python -m pip install -q -r requirements.txt
	@$(MAKE) --no-print-directory hooks
hooks:
	@if [ -d .git ]; then mkdir -p .git/hooks && cp scripts/hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit && echo "hooks: pre-commit(guard) installed"; else echo "hooks: .gitなし — スキップ"; fi
guard: setup
	$(PY) scripts/run_gates.py
ci: setup
	$(PY) scripts/run_gates.py --all
