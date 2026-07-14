# Next Steps — Tiered Warehouse & NL Search Architecture

> Consolidated from prior design conversations. This document organizes the
> recommendations into a coherent implementation roadmap: how to scale
> PROSPECTIQ from the current ~497K local profiles to a tiered system over the
> full 51M-row dataset, and how to build the natural-language search agent on
> top of it.

> **Implementation status (2026-07-14):** Step 1 (partition the cold tier) is **done**
> — the 51.35M-row monolith was reshaped via Athena CTAS into
> `s3://sungchunn-linkedin-db/curated/usa_profiles/state=<state>/` (52 partitions).
> One deliberate deviation from Section 1: the partition key is **`state`**, not
> `country/industry` — profiling showed the data is 99.9% US (country useless as a
> key) and `Company Industry` is 49% null, while `Region`/state is 2.3% null with an
> even spread. Remaining steps (aggregates, hot-tier promote, query router, Redis
> cache, NL agent) are not started. Progress is logged in
> [../agents/HANDOFF.md](../agents/HANDOFF.md).

---

## 0. The big picture

The end-state is a **three-tier data system with a query router in front**:

```text
                    ┌─────────────────-────────────┐
   request  ──────► │        Query Router          │
                    └───────┬──────────┬───────────┘
        semantic / ranked   │          │   filtered browse / export
                            ▼          ▼
                   ┌──────────────┐  ┌────────────────────────-────┐
                   │  Postgres    │  │ Redis cache → DuckDB/Athena │
                   │  pgvector+FTS│  │  → partitioned Parquet (S3) │
                   │  (HOT, ~1M)  │  │  (COLD, 51M, pruned scans)  │
                   └──────────────┘  └──────────────────────-──────┘
                            ▲                     ▲
                            └──── ingest DAG ─────┘
              raw → dedup → partition+sort → promote slice → aggregates
```

Three tiers, each doing what it is good at:

| Tier | Storage | Serves | Latency |
| --- | --- | --- | --- |
| **Hot** | Postgres + pgvector HNSW + FTS GIN (~500K–1M curated) | Semantic / keyword / ranked "top N" search | sub-100ms |
| **Cold** | Partitioned Parquet on S3, queried by DuckDB/Athena | Filtered browse, export, analytics over full 51M | 1–3s |
| **Precomputed** | Small side-files (manifests, dropdowns, rollups) | `/countries`, `/industries`, `/stats` | instant |

The two steps that turn this from "a fast Parquet browser" into "a tiered
warehouse with a serving layer" are the **hot tier** and the **query router**.

---

## 1. Foundation: partition the cold tier

Everything downstream depends on this decision, so it comes first.

### Partition key rules

1. **Partition on what people filter by** — otherwise pruning never triggers.
2. **Moderate cardinality** — too few distinct values = no skipping; too many
   = the "small files problem" (millions of tiny files, each with fixed
   overhead, *slower* than the monolith).
3. **Roughly even sizes** — target ~100MB–1GB per file.
4. **Range/numeric filters → sort key, not partition key.**

### Applied to our schema

| Field | Verdict | Why |
| --- | --- | --- |
| **Location Country** | ✅ Primary partition | Most common filter, ~200 values, natural top-level split |
| **Industry** | ✅ Secondary partition | Common filter, ~150 values, splits big countries further |
| Region / State | ⚠️ Maybe, for skew | Only to break up an oversized `US` partition |
| Years Experience | ➡️ Sort key, not partition | Range filter → sorting enables row-group zone maps |
| Company Name / Job Title | ❌ Never | Millions of distinct values → small-files disaster |
| Skills | ❌ Never | Multi-valued; not a clean partition key |

**Recommendation:** partition by `country/industry`, sort each file by
`years_experience`.

### The one risk: skew

The data is US-heavy. `country=US/industry=Software` could be millions of rows
(fine — becomes several files), while `country=Malta/industry=Dairy` might be
40 rows (a wasteful tiny file). Two mitigations:

- Let the writer target a file size and split/merge automatically (Athena and
  DuckDB both do this).
- If US stays lumpy, add `region` as a **third level only under the big
  countries** — do not blanket-partition by region.

> Interview-ready framing: *"I partitioned on the two highest-selectivity
> filters and sorted on the range filter for zone-map pruning."*

### How to run the reshape: Amazon Athena (optional, serverless path)

Athena is **SQL run directly on S3 files, no database, no server**. Same idea
as our DuckDB-over-S3 setup — *query the Parquet where it lives* — except the
compute is AWS's, spun up per query and thrown away.

- **Serverless** — no local compute or storage; the reshape runs entirely in AWS.
- **Understands Parquet + partitions natively** — same folder-pruning DuckDB does.
- **Pay-per-scan: ~$5/TB read.** Our dataset is a few GB, so queries cost cents.
  Partitioning matters twice: smaller scans are both faster *and* cheaper.
- **CTAS** (`CREATE TABLE AS SELECT`) reads the monolith and writes the
  partitioned output back to S3 in one statement — exactly the reshape job.

**Limits:** ~1–3s startup per query (not a low-latency serving layer — that
stays Postgres's job); no indexes/updates (rewrite files, don't `UPDATE`);
cost scales with sloppiness (a `SELECT *` with no partition filter scans
everything).

|  | Runs on | Always on? | Best for |
| --- | --- | --- | --- |
| **Postgres** | Our server | Yes | Fast serving, indexed lookups, updates |
| **DuckDB** | One machine | No | Local/single-node analytics on Parquet |
| **Athena** | AWS-managed fleet | No (per-query) | Serverless analytics + reshaping S3 files |

For the one-time "split the monolith into partitioned Parquet" job, Athena is
the least-effort path: define a table pointing at the big file, run one CTAS,
partitioned dataset appears in S3 — no machine of ours ever holds the data.

---

## 2. Build out the tiers (ordered steps)

**Step 1 — Precompute metadata & aggregates.**
As part of the same reshape job, emit small side-files: a partition manifest
(which country/industry combos exist, row counts), the `/countries` and
`/industries` dropdown lists, and the `/stats` rollups. Those endpoints then
read a 5KB file instead of scanning 51M rows. First thing that makes the app
feel fast.

**Step 2 — Build the hot serving tier (Postgres).**
The cold tier is wrong for low-latency and for semantic/keyword search (a
partition filter can't help an `ILIKE '%python%'`). Promote a curated slice —
top ~500K–1M profiles — into Postgres with the pgvector HNSW index + full-text
GIN index. This is where fast ranked search lives.

**Step 3 — Add the query router in the API.**
The piece that ties the tiers together — the intellectual core. One function
decides, per request:

- Semantic / keyword / "top N ranked" → **Postgres hot tier** (indexed, sub-100ms)
- Filtered browse / export / analytics over 51M → **DuckDB/Athena cold tier** (pruned)
- Aggregates / dropdowns → **precomputed files** from Step 1

**Step 4 — Wire Redis as a read-through cache** in front of the cold path
(the `cache.py` already written but never connected to the DuckDB app). Key on
a hash of query + filters. Repeated browses stop hitting S3.

**Step 5 — Make ingest a real pipeline.** Turn the pile of scripts into a small
DAG: `raw → dedup/validate → partitioned+sorted curated (cold) → promote
curated slice to Postgres (hot) → refresh aggregates`, with a data-quality gate
(row counts, null rates, dup rate) that fails the run if numbers look wrong.
Lets it re-run monthly instead of by hand.

---

## 3. The natural-language search agent

The trap most people fall into: "hand the LLM the schema, let it write any SQL,
run it." That's a cost bomb, a security hole, and unreliable at once. The design
below survives real users.

### Reframe: NL search is two problems, mapped to the two tiers

**Mode 1 — Find people** (*"senior backend engineers at fintech startups in
Singapore who know Go"*):

- **Hard structured filters** → `country=Singapore`, `industry≈financial
  services`, `years_experience≥8`, `skills contains Go`. SQL `WHERE` clauses,
  partition-prunable.
- **Fuzzy semantic intent** → *"backend engineer at a startup"* — wants **vector
  similarity**, not `ILIKE`.
- → Compiles to **one hybrid query on the Postgres hot tier**:
  `WHERE <structured filters> ORDER BY <vector distance> LIMIT n`.
  Template-fillable → the safe path.

**Mode 2 — Analytical** (*"average years of experience by industry for US
software companies"*):

- Real aggregation — `GROUP BY`, `AVG`, `COUNT` → **text-to-SQL against the cold
  tier**. Needs freer SQL generation → where guardrails must be strongest.

The first agent step is a **classifier**: which mode? That decision picks the
tier, the dialect, and how much freedom the SQL generator gets.

### The pipeline

```text
NL query
   ▼
1. Classifier — "find people" vs "analytical" vs "chit-chat/reject" (cheap fast model)
   ▼
2. Structured extraction (LLM → JSON)
     {filters:{country, industry, min_exp, skills[]}, semantic_text, aggregation:{group_by, metric}}
   ▼
3. Compile, don't free-write
     Mode 1 → fill a parameterized hybrid template (Postgres)
     Mode 2 → generate SQL (DuckDB) then VALIDATE
   ▼
4. Guardrail gate (deterministic, no LLM)
     • parse AST: SELECT-only, single statement
     • table/column allowlist
     • force LIMIT, inject partition predicate
     • EXPLAIN / bytes-scanned cap
   ▼
5. Execute (read-only) ──error?──► 6. Self-correct (feed error back, max 2 attempts)
   ▼
7. Return: rows + NL summary + the SQL
```

### The key choice: structured intent → compile, don't free-write

Have the LLM emit **structured JSON**, and let deterministic code turn it into
SQL — rather than the LLM emitting SQL strings directly. For Mode 1 this is
almost entirely achievable and kills a class of failures:

- No hallucinated columns (the compiler only knows real ones).
- No dialect confusion (our code emits DuckDB *or* Postgres correctly).
- Trivially parameterized → SQL injection gone.
- Testable: unit-test `JSON → SQL` with zero LLM calls.

The LLM's job shrinks to what it's good at: mapping messy phrasing to a clean
schema (`"fintech" → industry IN ('Financial Services','Banking')`, `"senior"
→ min_years_experience: 8`). Semantic normalization, not code generation.
Genuine free-form text-to-SQL is only needed for Mode 2 — and *that's* where the
guardrail budget goes.

### Guardrails (demo vs product)

Every generated SQL passes a **deterministic gate before execution** — no LLM:

1. **Parse the AST** (e.g. `sqlglot`). Reject anything not a single `SELECT`.
   No `INSERT/UPDATE/DELETE/DROP/COPY/ATTACH`, no multiple statements, no
   comments hiding a second query.
2. **Allowlist tables and columns** by walking the AST.
3. **Force a `LIMIT`** and a statement **timeout**.
4. **Partition-awareness for the cold tier:** if a DuckDB/Athena query has no
   `country`/`industry` predicate, it full-scans 51M rows. Inject a required
   predicate, reject with a clarifying question, or route to the hot tier.
5. **Cost ceiling.** On Athena set the workgroup's `BytesScannedCutoffPerQuery`
   (hard cap that kills any query scanning >~1GB) — the circuit breaker against
   a runaway query. DuckDB path: run `EXPLAIN`, check estimated cardinality.
6. **Read-only everywhere:** a `SELECT`-only Postgres role; DuckDB opened
   `read_only=True`. Defense in depth.

### Self-correction loop

SQL fails ~10–20% of the time on first try. Don't surface the error — feed
`{failed SQL, DB error}` back and ask the model to fix, **bounded to ~2
retries**. Most self-heal on attempt two. After that, fall back to a safe
template or ask the user to rephrase. Hard cap so it can't loop forever burning
tokens.

### Concrete stack choices

- **Models:** small/fast (Haiku-class) for the classifier + JSON extraction
  (run on every query). Reserve a stronger model (Sonnet/Opus) for Mode 2
  free-form SQL and the self-correction retry, where reasoning matters.
- **Schema in the prompt:** not raw columns — a curated **semantic layer**:
  friendly descriptions, allowed values for low-cardinality fields (the
  precomputed `/industries`, `/countries` lists!), 3–5 few-shot NL→JSON
  examples. Feed the *partition columns explicitly* so it learns to always
  filter on them.
- **Cache the parse.** Identical/similar NL → cache the JSON intent (and the
  embedding) in Redis. Repeated searches skip the LLM entirely.
- **Embedding for Mode 1:** the extracted `semantic_text` is embedded once, then
  feeds the pgvector `ORDER BY`. Same embedding model as ingest.

### What comes back to the user — three things, not one

1. The **rows** (structured results).
2. A one-line **NL summary** ("Found 240 senior Go engineers in Singapore
   fintech; showing top 50 by relevance").
3. The **generated SQL**, shown/expandable — builds trust, makes wrong answers
   debuggable, and demos well ("here's the SQL the agent wrote from your English").

### Proving it works

Keep a **golden set** of ~30–50 `NL → expected SQL / result-shape` pairs and run
them as a test suite. Text-to-SQL silently regresses when a prompt changes;
without an eval set you won't notice. Also the artifact that makes the project
credible — *"I measured 88% execution accuracy on my eval set."*

---

## 4. Performance: steps ≠ API calls

A "step" is a logical stage; an "API call" is a network round-trip. They are not
1:1. In a search box, every serial call is latency the user feels. Two levers:
**collapse steps into one call**, and **skip calls entirely**.

### Collapse: multiple steps, one call

Classifier (step 1) and structured extraction (step 2) are one prompt. A single
call returns everything:

```json
{
  "mode": "find_people",
  "filters": { "country": "Singapore", "industry": ["Financial Services"],
               "min_years_experience": 8, "skills": ["Go"] },
  "semantic_text": "backend engineer at a startup",
  "aggregation": null
}
```

The "classification" is just the `mode` field. For Mode 2, that same call can
also emit candidate SQL in another field.

### Skip: not every step needs a model

- **Compile (Mode 1)** — deterministic. Zero calls.
- **Guardrail gate** — deterministic. Zero calls.
- **Execute** — the database. Zero calls.
- **NL summary** — template it: `"Found {n} results for {filters}; showing top
  {k} by relevance."` Zero calls. Only spend a call if you want prose.
- **Self-correction** — only fires on execution error (~10–20%); each retry is
  one call. Happy path: zero.
- **Embedding (Mode 1)** — a round-trip, but to the cheap embeddings endpoint,
  and cacheable.

### Real per-query count

|  | Naive (1 call/step) | Optimized |
| --- | --- | --- |
| Mode 1 (find people), happy path | ~4 LLM calls | **1 reasoning call + 1 embedding** |
| Mode 2 (analytical), happy path | ~4 LLM calls | **1 reasoning call** (extract + emit SQL) |
| On SQL error | +1 per step | +1 per retry (max 2) |
| Cache hit (repeat query) | — | **0 calls** |

Steady state with a warm cache: most queries cost **one reasoning call** —
sometimes zero.

### Pipeline vs. agent loop (the axis underneath)

- **Agentic loop** — give the model tools (`run_sql`, `search_vector`) and let
  *it* decide when to call them. Flexible, but calls are **variable**, latency
  unpredictable, harder to test and cost-cap.
- **Fixed pipeline** — *we* orchestrate in code. Model called at known points →
  calls **bounded and predictable**. Cheaper, faster, testable.

**Build it as a fixed pipeline, not an open agent loop.** The only place the
model loops autonomously is the self-correction retry — and even that is bounded
to 2. Intelligence exactly where it helps (understanding the query, fixing
broken SQL); round-trips paid for only there.

> The mental shift: don't think "one call per step." Think **"one call per
> genuinely-hard decision,"** and make everything between deterministic. For this
> feature there are only two hard decisions — *what does the user mean* (one
> call) and, if it breaks, *fix the SQL* (conditional call). Everything else is
> plumbing written once and run for free.

---

## 5. Suggested implementation order

1. **Partition the cold tier** — `country/industry` partition, `years_experience`
   sort. Reshape via DuckDB or Athena CTAS. *(Section 1)*
2. **Precompute aggregates** — manifest, dropdown lists, stats side-files. *(Step 1)*
3. **Build the hot tier** — promote curated ~1M slice into Postgres with
   pgvector HNSW + FTS GIN. *(Step 2)*
4. **Query router** — the function that picks tier per request. *(Step 3)*
5. **Redis read-through cache** on the cold path. *(Step 4)*
6. **NL search agent** — fixed pipeline: combined extract call → compile →
   guardrail gate → execute read-only → bounded self-correct → rows + summary +
   SQL. *(Sections 3–4)*
7. **Golden eval set** — 30–50 NL→SQL pairs as a regression suite. *(Section 3)*
8. **Ingest DAG** — wrap the above into a re-runnable pipeline with a
   data-quality gate. *(Step 5)*
