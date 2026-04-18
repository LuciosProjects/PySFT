# PySFT Holdings Acquisition Design and Implementation Instructions

## Branch context

Work against the current `Valtrix_Backend` branch.

You must preserve the current library capabilities and behavior. The existing fetching system already works and must continue to work after your changes. You may edit existing files where needed, but all edits must be additive, backward-compatible, and respectful of the current architecture.

Do not break or downgrade:
- current price fetching
- TASE handling
- YFinance handling
- current task scheduling / parallel execution behavior
- current public interfaces unless absolutely necessary

---

## Objective

Implement a new **holdings acquisition subsystem** for PySFT.

This subsystem is **not** the exposure engine.

Its responsibility is only to:

1. identify an input instrument correctly
2. determine the correct authoritative holdings data source family
3. fetch or prepare to fetch verified holdings data from that source
4. return structured and auditable holdings results

Exposure reasoning will come **after** holdings acquisition, using the resulting asset compositions.

---

## Key design principles

### 1. Preserve current library capabilities
The current PySFT behavior is not to be damaged.
Do not replace the main fetching pipeline.
Do not overload existing fetch code with holdings-specific assumptions.
Do not refactor large areas unless truly necessary.

### 2. Reuse and generalize, do not duplicate
Some current utilities and data structures are stitched specifically for the main fetching routine.
Open them up so they can serve **both**:
- the existing main data fetching routine
- the new holdings acquisition routine

This applies to:
- utilities
- request structures
- execution / task orchestration helpers
- identity-resolution helpers
- source-classification logic

When generalizing, do it carefully and incrementally.
Do not create a second parallel universe of utilities if the current ones can be extended cleanly.

### 3. Two-phase architecture
The holdings subsystem must be split into two explicit phases:

#### Phase 1: Instrument identification
Given a raw indicator, determine what the instrument actually is.

This phase should:
- normalize the input
- determine whether it is TASE-style or generic (Ticker-style)
- enrich identity from existing local and remote helpers
- resolve canonical fields such as symbol, ISIN, security id, jurisdiction, and wrapper status, most importantly - ISIN
- determine whether the instrument is a direct equity or a wrapper security

#### Phase 2: Source routing and acquisition
Use the identified instrument to determine which holdings source family should be used.

This phase should:
- map the instrument to one of the supported holdings source families
- construct the proper adapter call
- fetch holdings when an implementation exists
- otherwise return a structured, explicit "not yet implemented / not disclosed / unresolved" result

### 4. Focus on automatic source discovery
The core goal is an automatic subroutine that gets from a raw indicator to the correct holdings data source family.

This routing must work for:
- TASE numeric indicators
- generic symbols / non-TASE identifiers

Routing must be deterministic and auditable.

### 5. Keep holdings logic separate from exposure logic
These source families are primarily for obtaining holdings data of:
- ETFs
- funds
- structured wrapper products
- other assets that themselves hold portfolios of assets

Exposure is a later phase and must not be mixed into this implementation.

### 6. Preserve parallel execution policy
The new subsystem must support the same execution philosophy as the current fetching system.
Do not force everything into serial execution.
Follow the existing task creation and scheduling style so holdings routines can run under the same parallel execution policy.

---

## Supported source families

Design the routing system around the current holdings source families discovered so far.

### US source families
1. US issuer-hosted daily holdings pages / files
2. SEC Form N-PORT access path
3. SEC Form N-MFP access path
4. Other SEC periodic-report path for products that do not fit the N-PORT model cleanly

### Ireland / UCITS source families
5. UCITS issuer-hosted holdings endpoint / page / file
6. UCITS periodic or daily disclosure documents path

### Israel / TASE source families
7. TASE market / security mapping path
8. MAYA disclosure path
9. TASE Data Hub / official API infrastructure path

Important:
Some of these are final holdings endpoints, and some are discovery / mapping layers used to reach the final holdings disclosure.
Model them as source families anyway, because routing needs to know where to go and why.

---

## Implementation scope

Implement a new holdings subsystem under:

- `src/pysft/holdings/`

Suggested structure:

- `src/pysft/holdings/enums.py`
- `src/pysft/holdings/structures.py`
- `src/pysft/holdings/identity.py`
- `src/pysft/holdings/router.py`
- `src/pysft/holdings/service.py`
- `src/pysft/holdings/registry.py`
- `src/pysft/holdings/adapters/__init__.py`
- `src/pysft/holdings/adapters/tase_mapping.py`
- `src/pysft/holdings/adapters/tase_maya.py`
- `src/pysft/holdings/adapters/tase_datahub.py`
- `src/pysft/holdings/adapters/ucits_issuer.py`
- `src/pysft/holdings/adapters/ucits_documents.py`
- `src/pysft/holdings/adapters/us_issuer.py`
- `src/pysft/holdings/adapters/sec.py`

If a slightly different file split is cleaner, keep the same architectural idea.

---

## Required implementation behavior

## Phase 1: Instrument identification mechanism

Implement a canonical identification layer that works from a raw input indicator.

### Input types to support
- TASE numeric indicator
- TASE-like indicator starting with `126.`
- generic ticker / symbol

### Identification rules
1. If the raw indicator is digit-only or begins with `126.`, treat it as TASE-style input.
2. Reuse the current TASE DB / TASE helper logic already present in the repo wherever possible.
3. Resolve and store canonical fields such as:
   - raw indicator
   - normalized indicator
   - is_tase_input
   - security_id
   - symbol
   - ISIN
   - name
   - jurisdiction
   - instrument family
   - wrapper flag
   - foreign-wrapper-on-TASE flag
   - notes / reasoning
4. Infer jurisdiction from ISIN prefix when available.
5. Determine whether the instrument is:
   - direct company equity
   - ETF
   - fund
   - MTF
   - other wrapper / unknown
6. Keep the identification logic conservative and deterministic.
   Do not guess aggressively from names.

### Special emphasis
The identification mechanism should be reusable by:
- the current main fetching flow
- the new holdings flow

Do not bury it inside a holdings-only adapter if it can serve both subsystems.

---

## Phase 2: Source routing and data acquisition

Implement a routing mechanism that uses the identified instrument to choose the correct holdings source family automatically.

### Routing output
The router must return a structured route object containing:
- canonical instrument identity
- primary holdings source family
- fallback holdings source families
- routing reasoning
- optional source-specific hints or metadata

### Routing examples
The system should route the following correctly:

- `1183441` -> UCITS / Ireland path
- `1186063` -> UCITS / Ireland path
- `PHDG` -> US issuer path, with SEC fallback path
- `DBA` -> US issuer path, with alternate SEC periodic-report fallback
- direct stock symbols like `AAPL` -> direct equity / no recursive holdings path

### Important
The routing system must be based on **source families**, not on one-off issuer-specific hacks.
Small special-case overrides are allowed, but the main design must remain policy-based.

---

## Data structures

Generalize or extend existing structures where appropriate so the codebase supports both main fetching and holdings acquisition cleanly.

Create holdings-side structures such as:

- canonical instrument identity object
- holdings route object
- holdings line object
- holdings snapshot object

A holdings snapshot should preserve:
- portfolio/instrument identifier
- as-of date
- fetched-at date
- source family
- source locator or endpoint
- holdings lines
- warnings
- success / failure state
- fidelity / disclosure quality field if useful

A holdings line should support fields like:
- child indicator
- child symbol
- child ISIN
- child name
- weight
- quantity
- asset type
- source fidelity

Do not create fake completeness.
If a source does not disclose full holdings, return that explicitly.

---

## Utility and helper requirements

Refactor or extend helpers carefully so they can serve both:
- the current main fetch routine
- the new holdings routine

Potential shared responsibilities:
- indicator normalization
- TASE-vs-generic classification
- identity enrichment
- source classification
- retry helpers
- task creation
- batching / grouping logic
- result metadata helpers

Do not duplicate a helper just because the current one is slightly specialized.
Prefer extracting a shared lower-level helper and keeping old behavior intact on top of it.

---

## Adapter requirements

Implement source-family adapters.
Each adapter should have a clean interface and return structured results.
If a real endpoint is not fully implemented yet, the adapter must still return a structured, explicit placeholder result.

### Adapters to implement
- TASE mapping adapter
- MAYA adapter
- TASE Data Hub adapter
- UCITS issuer adapter
- UCITS documents adapter
- US issuer adapter
- SEC adapter

### SEC adapter
Split internally if useful:
- N-PORT path
- N-MFP path
- other SEC periodic-report path

### UCITS adapters
Keep issuer-hosted and documents-based approaches separate.

### TASE adapters
Keep mapping, MAYA, and Data Hub concerns separated enough that routing remains clear.

---

## Parallel execution policy

The holdings subsystem must support the same parallel execution style used elsewhere in PySFT.

Requirements:
- integrate with the existing task execution philosophy
- do not create a second incompatible scheduler if the current one can be reused or extended
- holdings tasks should be schedulable similarly to current fetch tasks
- preserve batching and grouping patterns where reasonable
- keep network-bound adapters compatible with future parallel execution

If shared task abstractions need to be generalized, do so carefully and without breaking current fetch routines.

---

## Testing requirements

Write tests for:
1. instrument identification
2. source routing
3. each source-family branch

### Important testing rule
Write tests for each source-family routine branch so that every routing branch is exercised.

This does **not** mean every test must hit the live internet.
Prefer deterministic unit tests with fixtures, mocks, and structured sample payloads where possible.

### At minimum, add tests for:
- TASE identification branch
- generic symbol identification branch
- TASE -> MAYA path
- TASE -> Data Hub path
- TASE -> mapping path
- UCITS issuer path
- UCITS documents path
- US issuer path
- SEC N-PORT path
- SEC N-MFP path
- SEC other-report path
- direct-equity / no-wrapper path
- unknown / unresolved path

### Required sample routing tests
- `1183441`
- `1186063`
- `PHDG`
- `DBA`
- `AAPL`
- at least one unknown indicator

### Required adapter tests
Each adapter must have at least one test proving:
- it can be selected by the router
- it returns a valid structured snapshot/result object
- it reports unimplemented or undisclosed states explicitly when real data retrieval is not yet wired

---

## Backward compatibility requirements

This is critical.

You must preserve current PySFT capabilities.

That means:
- existing fetch workflows must continue to function
- existing public APIs should remain valid unless there is a compelling reason otherwise
- existing enums should not be repurposed recklessly
- existing data structures should not be broken
- current TASE behavior must remain intact
- current YFinance behavior must remain intact

If you need new enums or structures for holdings, add them instead of overloading current ones incorrectly.

You may edit existing implementations, but only in a way that preserves current behavior.

---

## Suggested implementation strategy

Implement in two controlled passes.

### Pass 1
Build:
- holdings enums
- holdings structures
- instrument identification mechanism
- source routing mechanism
- routing registry / source family registry
- tests for identification and routing

### Pass 2
Build:
- source-family adapters
- holdings service orchestration
- task integration / parallel-execution compatibility
- adapter tests

Do not jump straight into endpoint-heavy code before the identification and routing layers are stable.

---

## Deliverables

Provide:
1. the new file tree
2. a short explanation of the identification phase
3. a short explanation of the source-routing phase
4. a short explanation of how parallel execution compatibility was preserved
5. a summary of any shared utilities that were generalized
6. a summary of any existing structures that were extended for dual use
7. a list of which source-family adapters are fully implemented vs placeholder-returning
8. the test matrix showing coverage across all source-family branches

---

## Things you must NOT do

Do not:
- implement exposure inference
- implement sector or geography logic
- invent holdings where only proxies exist
- silently substitute benchmark composition for true holdings
- break current PySFT functionality
- create a disconnected duplicate framework if the current utilities can be generalized
- turn the router into a scraping function
- make the system depend on AI or heuristic guessing for source routing

---

## Final note

This work is about **holdings acquisition architecture**.

The desired end state is:
- identify the instrument correctly
- route it automatically to the right holdings source family
- fetch or attempt to fetch verified holdings data
- preserve a clean path for later exposure analysis based on the resulting holdings composition