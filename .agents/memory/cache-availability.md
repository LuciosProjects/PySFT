---
name: Cache availability decisions
description: Reasons for distinguishing absent data from zero and choosing conservative coverage.
---

Unavailable requested fields are retried, not negatively cached. Preserve explicit
provider zeroes, but never use model defaults as evidence that a field was fetched.

**Why:** The user required actual availability and freshness to determine reuse;
the previous default-based approach could conceal missing market data indefinitely.

**How to apply:** New provider adapters must distinguish absence from an observed
zero. Do not add negative-cache semantics without agreeing on expiration and the
public unavailable-data behavior.

Assignment tracking alone is not evidence of source availability: provider
adapters can assign invented fallback values. Test the production adapter with
raw controlled responses as well as testing the orchestration gateway.

**Why:** Boundary doubles demonstrated correct cache behavior while concealing
an adapter that manufactured absent fields, which then appeared explicitly supplied.

**How to apply:** Whenever adding or changing adapter assignments, verify the raw
source actually supplies the field or supports a valid calculation. An absent
comparison input cannot justify an invented zero or a copy from another field.

Treat provider route as fixed by ticker resolution, not a second cache identity.
When the instrument's trading calendar is not established, prefer extra provider
work to declaring unknown dates fully covered.

**Why:** The user explicitly excluded switching one ticker between providers, and
cross-market calendar guesses could silently omit requested history.

**How to apply:** Extend calendar support only from verified instrument/exchange
information; do not infer units, routing or full coverage from currency aliases,
numeric price magnitudes or the outermost cached dates.
