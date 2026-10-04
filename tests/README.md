# PySFT test suite

The default suite is deterministic: it does not contact external providers and
it never writes to the SQLite databases stored under `src/pysft/data`.

## Structure

- `support/PySFTTestEnvironment` owns one temporary SQLite file per test.
- `support/DeterministicProviderGateway` replaces only the external provider
  boundary while leaving public APIs, routing, scheduling, caching, and output
  aggregation real.
- Scenario factories create readable yfinance and TASE outcomes.
- Test classes group public API, routing, normalization, cache, batch, and HTTP
  behavior without sharing mutable state.

## Commands

Use Python 3.11, matching CI. Install the project and test-only tools from
`uv.lock`:

```bash
# [Replit Agent] Install locked test tools on Python 3.11 to match CI.
uv sync --locked --group test --python 3.11
```

The `test` dependency group declares supported pytest and pytest-cov versions;
`uv.lock` pins their exact versions and transitive dependencies. `--locked`
fails if the dependency declarations and lockfile disagree instead of updating
the lockfile during a test run.

Run the default unit and deterministic E2E suite:

```bash
# [Replit Agent] Run deterministic tests with the locked test group.
uv run --locked --group test --python 3.11 pytest -m "not live"
```

Run live provider smoke tests explicitly:

```bash
# [Replit Agent] Keep live tests opt-in while using locked test tools.
uv run --locked --group test --python 3.11 pytest -m live --run-live
```

Record coverage:

```bash
# [Replit Agent] Record deterministic coverage using locked test tools.
uv run --locked --group test --python 3.11 pytest -m "not live" --cov=src/pysft --cov-report=term-missing
```

The initial deterministic coverage baseline is **60%**. This is recorded as a
baseline, not yet enforced as a minimum threshold.

HTTP E2E tests bind an ephemeral loopback port. Restricted sandboxes must allow
local socket binding; no external network access is used.

## Type checking

The separate `typing` dependency group contains mypy, pandas-stubs, and
types-psutil; their exact versions are recorded in `uv.lock`.

On a conventional local or CI environment:

```bash
uv run --locked --group typing --python 3.11 mypy src
```

On Replit, use the isolated tool runner to avoid the read-only base-interpreter
installation prefix (these direct tool versions match the current lockfile):

```bash
uvx --index-url "$PIP_INDEX_URL" \
  --from "mypy==2.4.0" \
  --with "pandas-stubs==2.3.3.260113" \
  --with "types-psutil==7.2.2.20260906" \
  mypy src
```

Missing typing metadata is exempted only for yfinance, exchange_calendars, and
the optional googletrans provider. PySFT source code remains checked; the optional
translation provider's existing import and fallback behavior is unchanged.
