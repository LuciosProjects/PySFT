# PySFT Package Plan

## Goals
- Fetch market data for given securities (tickers, ISINs, etc.) from pluggable sources.
- Normalize, store, and analyze data using an LLM agent to produce insights.
- Provide a clean Python API and a simple CLI for common workflows.

## Users & Workflows
- Quant/analyst scripts: import `pysft` and call `fetch -> analyze -> report`.
- CLI users: `pysft fetch AAPL --source yahoo`; `pysft analyze data.csv --prompt ...`.
- Extenders: add new data sources or custom analysis prompts/pipelines.

## Architecture & Modules
```
pysft/
  __init__.py
  config.py           # App settings, env vars, secrets
  models.py           # Pydantic models (Security, Quote, Candle, AnalysisResult)
  data/
    base.py           # Abstract fetcher interface
    yahoo.py          # Example datasource (yfinance or REST)
    alpha_vantage.py  # Optional
    polygon.py        # Optional
  storage/
    io.py             # Read/write CSV/Parquet/JSON; cache
  llm/
    agent.py          # LLM analysis orchestration
    prompts/
      default.txt     # Default analysis prompt(s)
  cli/
    __init__.py
    main.py           # `pysft` entrypoint (Typer/Click)
  utils.py            # Shared helpers (logging, retry, time)
```

## Key Components
- Data Fetcher (`data.base.Fetcher`): `fetch_quotes(ticker, range)`, `fetch_candles(...)`.
- Normalization: map raw fields to `models.Quote`/`Candle` with UTC times.
- Storage: CSV/Parquet caching, simple local cache directory, optional SQLite.
- LLM Agent: given data + prompt, produce `AnalysisResult` (summary, metrics, risks).
- CLI: `fetch`, `analyze`, `report`, `cache` commands with sensible defaults.

## Public API
- `pysft.fetch(ticker: str, source: str = "yahoo", **kwargs) -> pd.DataFrame`
- `pysft.analyze(df: pd.DataFrame, prompt: str | None = None) -> AnalysisResult`
- `pysft.save(df: pd.DataFrame, path: str) -> None`
- `pysft.load(path: str) -> pd.DataFrame`

## Configuration
- Env vars: `PYSFT_DATA_DIR`, `PYSFT_DEFAULT_SOURCE`, `PYSFT_OPENAI_API_KEY`.
- File config: `pyproject.toml` `[tool.pysft]` or `pysft.yaml`.
- Secrets via env only; no checked-in keys.

## Dependencies
- Core: `pandas`, `pydantic`, `requests`, `python-dateutil`, `rich`, `typer`.
- LLM: `openai` (or alternative), optional extras: `yfinance`, `polars`.
- Testing: `pytest`, `pytest-mock`.

## CLI Outline (Typer)
- `pysft fetch TICKER [--source yahoo --start 2024-01-01 --end 2024-12-31 --interval 1d --out data/AAPL.csv]`
- `pysft analyze PATH [--prompt prompt.txt --model gpt-4.1]`
- `pysft report PATH [--format md|html]`
- `pysft cache clear`

## LLM Agent Flow
1. Validate/prepare data (downsample, compute indicators like SMA/EMA).
2. Build prompt: context + goals + constraints + user additions.
3. Call model provider; parse output to `AnalysisResult`.
4. Optional: persist analysis as Markdown with references.

## Testing Strategy
- Unit tests for `models`, `config`, `storage.io`.
- Mock HTTP for data sources (`responses` or `pytest-mock`).
- Golden tests for agent prompt parsing and result schema.

## Docs
- README: quickstart, CLI examples, API cheatsheet.
- `examples/` with small scripts.
- Inline docstrings; optional MkDocs later.

## Release & CI
- `pyproject.toml` with `setuptools`/`hatchling`.
- Versioning: SEMVER, `pysft.__version__`.
- CI: lint, tests, build; release job to PyPI (optional).

## Next Steps
- Scaffold package structure and minimal implementations.
- Add `pyproject.toml`, update `requirements.txt`.
- Implement Yahoo fetcher and simple LLM stub.
- Wire Typer CLI and a tiny end-to-end example.