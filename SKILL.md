# SKILL.md - Custom Skills for Ramify Development

## Skill: Verify Ramify Sandbox Isolation
This skill runs an integration test to verify that `ramify` correctly isolates file changes and cleans up Docker resources upon branch termination.

```bash
uv run pytest tests/test_sandbox_isolation.py -vv
```

## Skill: Check Code Quality
Runs linting, formatting check, and strict type checks across the codebase.

```Bash
uv run ruff check src/ tests/ && uv run mypy src/
```

## Skill: Execute Command via Ramify Concept (Smoke Test)
A quick smoke test snippet that Claude Code can run using Python interactive mode to ensure ramify is functional in the local environment.


```Python
python -c "
import ramify
sh = ramify.init('./')
sandbox = sh.branch('smoke_test')
res = sandbox.run('echo hello from ramify branch')
print(res.to_llm_json())
sandbox.close()
"
```