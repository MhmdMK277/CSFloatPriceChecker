# Contributing

Thanks for helping make CSFloat Tracker better. The codebase is small and
deliberate — you can read all of `src/csfloat_tracker/core` in one sitting.

## Setup

```bash
make setup          # uv venv + editable install + npm install
make dev            # backend :8422 (reload) + frontend :5180 (HMR)
make test           # pytest with coverage
make lint           # ruff + tsc
```

No `make` (plain Windows)? Each target is 1–3 commands — open the `Makefile`
and run them directly.

## Ground rules

- **Tests accompany code.** New core logic gets unit tests; new endpoints get
  API tests (`tests/test_api.py` shows the pattern — in-process ASGI client,
  CSFloat mocked with respx). CI enforces ≥ 70 % coverage.
- **Conventional commits.** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:` — scoped like `feat(server): …` when useful.
- **Prices are integer cents** everywhere except the UI render layer.
- **Errors are `CSFloatError` subclasses** with user-presentable messages.
  Never let a raw exception reach a route response.
- **Respect the rate limiter.** Anything that talks to CSFloat goes through
  `CSFloatClient` — no bare httpx calls to csfloat.com.
- **Frontend styling uses the tokens.** New CSS references
  `var(--color-*)` / `var(--space-*)` / `var(--font-*)` from `tokens.css`;
  no inline hex colors, no new font families.
- **Keep files under ~500 lines.** Split modules rather than growing them.

## Pre-commit hooks (optional but recommended)

```bash
pip install pre-commit
pre-commit install
```

## Where things go

| Change | Where |
| --- | --- |
| New CSFloat endpoint | `core/client.py` + tests in `test_client.py` |
| New catalog data | `core/schema_parser.py` + `test_schema_parser.py` |
| New REST endpoint | `server/routes/` + `test_api.py` |
| New background job | `server/worker.py` + `test_worker.py` |
| New page/component | `frontend/src/pages` / `frontend/src/components` |
| CLI command | `cli.py` |

## Releases

Maintainers: bump `version` in `pyproject.toml` and
`frontend/package.json`, update `CHANGELOG.md`, tag `vX.Y.Z`, push the tag.
Before a release, refresh the shipped catalog:
`python scripts/generate_itemdb.py`.
