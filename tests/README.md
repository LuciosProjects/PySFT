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

Run the default unit and deterministic E2E suite:

```bash
pytest -m "not live"
```

Run live provider smoke tests explicitly:

```bash
pytest -m live --run-live
```

Record coverage:

```bash
pytest -m "not live" --cov=src/pysft --cov-report=term-missing
```

The initial deterministic coverage baseline is **60%**. This is recorded as a
baseline, not yet enforced as a minimum threshold.

HTTP E2E tests bind an ephemeral loopback port. Restricted sandboxes must allow
local socket binding; no external network access is used.
