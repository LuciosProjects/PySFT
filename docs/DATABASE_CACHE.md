# Fetch cache contract

PySFT's SQLite fetch cache is keyed by the caller's ticker. Its provider route
is fixed by ticker resolution, not a second cache identity. The public fetch
API and `info`, `price`, and `all` presets are unchanged.

## Stored data and availability

- `indicator_attributes` stores one JSON scalar per ticker/attribute, with its
  fetch timestamp, price-normalization version when applicable, and
  `availability_version`.
- `price_history` stores date-aligned OHLC, volume and change percentage,
  normalization version, row timestamp and `field_fetched_at` JSON timestamps.
- Schema additions are additive. Existing rows and the independent security
  lookup database are not deleted or converted.
- Only explicitly supplied usable provider values are persisted. Dataclass
  defaults, nulls, NaNs, empty strings and unavailable sentinel strings are not
  proof of a successful fetch. A provider's explicit numeric zero is valid.
- Old scalar zeroes without availability provenance cannot prove completeness:
  the previous writer stored model defaults as if providers had returned them.
  Missing immutable values are not persisted, and unavailable legacy immutable
  values can be replaced by an actual value.

The internal data model tracks constructor-supplied fields and assignments.
Provider adapters must assign fields only when actually available; absent
provider keys must not be replaced with synthetic zeroes or default currencies.
The tracking set is internal and is not an added public output attribute.
Bizportal fund graphs provide closing NAVs, not intraday open/high/low; those
unavailable fields are not fabricated or cached. Their legacy copied OHLC cells
without field provenance are also excluded. Change percentages without an
observed comparison price remain unavailable rather than becoming zero.

## Freshness and normalization

`indicator`, `name`, `ISIN`, `inceptionDate` and `quoteType` are immutable.
Other scalars expire after 15 minutes. Historical cells are immutable, except
today's cells, which expire after 15 minutes. A partial refresh of today's
close does **not** refresh the timestamp of its unfetched open or volume.

Only fresh scalars are returned. Failed refreshes preserve stored rows but do
not return stale scalar values. Compatible, fresh cached fields and historical
dates remain available even if another part of the refresh fails.

Numeric TASE mutual-fund prices, including unknown numeric quote types, require
the current normalization version. Currency aliases and price magnitude are
not evidence of correct units. Legacy/obsolete prices are excluded; metadata
fetches never certify or overwrite price history. When a row's normalization
version changes, old unfetched cells are not given the new version.

## Reuse and fetching

The manager checks only the requested fields, regardless of the mode that
originally populated them. Compatible `info` plus `price` data can satisfy an
`all` request. Unavailable requested fields remain missing and are retried,
rather than negatively cached or silently synthesized.

Coverage is checked per date **and requested field**, not inferred from the
first and last stored rows. Exact ranges and single-day requests do not require
surrounding cache rows. Native TASE requests and resolved Yahoo `.TA` symbols
use the TASE calendar; Yahoo instruments with verified US exchange metadata use
XNYS. Original TASE identifiers that resolve to non-TASE Yahoo symbols do not
inherit TASE holidays. For Yahoo instruments whose exchange calendar is not
established (including price-only responses without exchange metadata),
coverage is deliberately conservative:
all requested calendar dates must be present, otherwise a refresh is attempted.

If prices are complete but metadata is missing/stale, only the metadata path
is used. If metadata is complete but prices are missing, only prices are
requested. Yahoo supports bounded downloads: the manager sends the envelope of
missing sessions, batching only requests with the same mode and bounds.
Disjoint gaps may therefore fetch intervening dates as well; the underlying
Yahoo fetcher also retains its existing retry/look-around padding. TASE graph
endpoints do not support date-bounded downloads, so that route fetches and
merges the required range safely.

Fresh and cached values are merged by attribute and date. Partial provider
responses do not erase valid cached cells. Explicit date-range results are
clipped to the request, sorted and deduplicated, and contain only requested
attributes plus the existing `dates` envelope. Unavailable requested values
are `None`, not fabricated zeroes. `last` is derived from the final returned
close, including historical requests.

## Configuration and verification

`DB_ENABLED`, `DB_PATH` and `TTL_MINUTES` are defined in
`pysft.core.constants`. `DatabaseManager(path)` supports an explicit database
path. `clear_cache()` clears fetched scalars/history but preserves the schema.

Tests use `pysft_env` (a temporary SQLite file outside the repository) and
`provider_gateway` (fixed-route provider doubles), with external networking
blocked. The session database guard checks content, size and modification time
of both bundled databases. No test uses them as writable fetch caches.

```bash
python -m pytest tests/e2e/test_cache_reuse_contract.py -q
python -m pytest -m "not live" -q
```

Pytest explicitly prioritizes `src`, so an older installed PySFT wheel cannot
accidentally stand in for the implementation under test.

### Characterization before implementation

The initial seven cross-mode contract cases were run against the original
production logic: **2 passed, 5 failed**. Expanded/overlapping range examples
passed. Both fixed routes exposed fabricated scalar defaults and redundant
price work during metadata refresh; missing-field selection exposed a
fabricated beta zero. Production cache changes were made only after that run.
The contract suite now also covers full presets in both directions, exact
range hits, single-day slicing, missing interior cells, partial responses,
failed expansions, valid zeroes and per-cell current-day freshness.

The normalization regression fixture explicitly supplies its zero change
percentages: a fixture with omitted values no longer represents complete
history, just as an actual provider omission does not.
