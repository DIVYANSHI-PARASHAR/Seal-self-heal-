# Logistics capability expansion plan

**Status:** Proposed
**Goal:** demonstrate a credible self-evolution cycle in a realistic logistics
domain: the baseline harness honestly refuses a shipment-cohort question, a
trusted supervisor turns that observation into a frozen evaluation, and a
generated harness tool later answers the original and unseen variations.

## The product claim

The initial inventory limitation is mostly a page-budget limitation. This plan
adds a more meaningful capability gap:

> How many customers sent more than 15 shipments from warehouse 3 yesterday?

The baseline does not have a shipment aggregation capability, so it must return
an explicit unsupported result. It must not guess, return zero, or attempt an
unbounded database query.

After the protected data contract, oracle, and evaluation inputs exist, the
evolution workflow may generate a reusable harness tool. It can read bounded
shipment pages, count shipments per customer locally, apply a threshold, and
return the number of qualifying customers. Promotion requires the tool to work
on the original incident and private variations, while preserving the inventory
behaviour that already works.

## Important scope decision

Use a **logistics dataset bundle** rather than putting every entity into the
existing single-table inventory dataset.

A bundle is one immutable scenario snapshot containing related logical tables:

~~~text
logistics dataset bundle
  customers
  warehouses
  shipments
~~~

The current inventory store is intentionally single-schema: every row in
analyst_rows has the same inventory fields and a dataset has one schema. Do not
put shipments, customers, and warehouses into it with nullable fields or alter
existing immutable inventory documents in place.

For the first implementation, add logistics-specific collections alongside the
existing analyst_datasets and analyst_rows collections. Keep existing inventory
runs and regressions working. Introduce a shared input-router abstraction so
the runner can distinguish an inventory table from a logistics bundle. A later,
separate migration can unify both storage implementations if it is worth the
complexity.

## Exact v1 question semantics

The natural-language question maps to this protected structured task:

~~~json
{
  "operation": "count_customers_with_shipment_count_gt",
  "warehouse_number": 3,
  "relative_day": "yesterday",
  "threshold": 15
}
~~~

It returns:

~~~json
{"value": 2}
~~~

The semantics must be frozen before any candidate is generated:

- Count distinct sender_customer_id values, not shipment records.
- Include only shipments whose status is sent.
- Include only shipments originating from the warehouse whose warehouse_number
  is 3.
- Resolve yesterday as the previous calendar day in the bundle's frozen
  reporting timezone, relative to its frozen reference instant. Never use the
  host clock during an evaluation.
- Include sent_at values in the half-open interval [start, end).
- Apply a strict greater-than threshold: 15 shipments does not qualify; 16
  shipments does.

This first question is a shipment aggregation, not a true customer join:
customer IDs already live on shipment documents. Customers and warehouses are
still needed as validated reference data. A later, separate capability can
demonstrate a real join, for example: “How many active enterprise customers
sent more than 15 shipments from Northeast warehouses yesterday?”

## Target MongoDB model

Each scenario gets a separate immutable logistics bundle. All entity documents
include dataset_id, so public, private-validation, and final-evaluation
snapshots cannot be mixed.

### logistics_datasets

One document per bundle:

~~~json
{
  "_id": "logistics-shipment-threshold-public-v1",
  "status": "ready",
  "domain": "logistics",
  "schema_version": "logistics-snapshot-v1",
  "reference_instant": "2026-09-26T16:00:00Z",
  "reporting_timezone": "America/New_York",
  "relations": {
    "customers": {"row_count": 8, "content_hash": "..."},
    "warehouses": {"row_count": 3, "content_hash": "..."},
    "shipments": {"row_count": 74, "content_hash": "..."}
  },
  "content_hash": "..."
}
~~~

The bundle hash covers the temporal context, every relation schema, and every
ordered relation hash.

### logistics_customers

~~~text
dataset_id             string, bundle reference
position               integer, deterministic order
customer_id            string, bundle-local primary key
segment                optional synthetic enum for later join scenarios
status                 optional synthetic enum
~~~

Use synthetic IDs and attributes only; no customer PII belongs in demo fixtures.

### logistics_warehouses

~~~text
dataset_id             string, bundle reference
position               integer, deterministic order
warehouse_id           string, bundle-local primary key
warehouse_number       integer, unique within a bundle
timezone               IANA timezone name
~~~

### logistics_shipments

~~~text
dataset_id             string, bundle reference
position               integer, deterministic order
shipment_id            string, bundle-local primary key
sender_customer_id     string, references logistics_customers.customer_id
origin_warehouse_id    string, references logistics_warehouses.warehouse_id
status                 enum such as created, sent, cancelled
sent_at                timezone-aware BSON Date stored in UTC
~~~

Each document represents one outbound shipment, not a shipment-event stream.
The v1 question therefore counts shipment documents whose current status is
sent; it does not attempt to reconstruct lifecycle transitions.

### Required validation and indexes

- Reject duplicate customer, warehouse, or shipment IDs within a bundle.
- Reject an orphan shipment customer or warehouse reference.
- Reject naive timestamps, invalid timezone names, invalid statuses, and
  malformed rows.
- Require every foreign-key target to exist in the same bundle, contiguous
  positions for deterministic hashing, and sent_at values no later than the
  bundle reference instant.
- Create unique indexes for each relation's dataset_id plus its business ID,
  and for each relation's dataset_id plus position.
- Add a bounded-scan index for shipments beginning with dataset_id,
  origin_warehouse_id, status, and sent_at.
- Publish atomically: write pending metadata and all relation rows, verify
  relation and bundle hashes, then mark the bundle ready. Published bundles are
  immutable from the application's perspective.

## Safe capability boundary

The evolving harness must never receive Atlas credentials, a PyMongo client, a
collection name supplied by the model, or an arbitrary MongoDB filter,
aggregation pipeline, lookup, sort, or JavaScript expression.

The trusted logistics session should expose only a small, typed capability:

~~~text
inspect_catalog()
inspect_relation(relation)
read_shipments(warehouse_number, relative_day, cursor, limit)
~~~

The session resolves warehouse identity and the frozen time window itself. It
allows only the assigned bundle, canonical filter values, opaque
filter-bound cursors, and fixed page/byte/time budgets. The host tracks every
page and byte read.

The baseline harness does not register an aggregation tool. A Phase 4
candidate may add a model-facing tool such as
count_customers_over_shipment_threshold. Its implementation loops through
allowed shipment pages, groups sender_customer_id values locally, and applies a
variable threshold. This is a real generated capability, but not a generated
database privilege.

For candidate execution, use a trusted host-side RPC or stdio bridge instead of
passing an introspectable in-process session object. The Docker candidate gets
only its editable harness source, the task, and that narrow bridge. It gets no
Atlas, LangSmith, Docker-socket, network, oracle, private-fixture, or full
repository access.

## Changes by project phase

### Phase 1 — data foundation and honest baseline

This phase is currently inventory-only. Extend it as follows:

1. Add a protected LogisticsDatasetStore and a typed DatasetBundleInfo/input
   router. Keep the existing inventory table store backward-compatible.
2. Add the four logistics collections and materialization/hash validation
   described above.
3. Replace the single global data schema assumption in settings with a
   protected domain-schema registry and task-contract registry. Keep
   inventory-totals-v1 and add logistics-shipment-threshold-v1.
4. Extend the CLI and local UI to show an input kind, domain, bundle ID, and
   relation counts. A user must explicitly select a logistics bundle; do not
   silently run a logistics question against the inventory demo table.
5. Make harness messages and tool definitions relation-aware while retaining
   the current inventory tools. The baseline recognises the logistics request
   as an answerable future capability and responds with:

   ~~~text
   outcome = unsupported
   limitation_kind = capability_gap
   capability_request.kind = shipment_customer_threshold
   ~~~

   It should make no logistics data read for this refusal.
6. Add tests for bundle immutability, content-hash tampering, relation
   isolation, cursor tampering, primary keys, foreign keys, timestamp
   validation, and the absence of the new aggregation tool from the baseline.

Likely files: config/analyst.yaml, src/self_heal/settings.py,
src/self_heal/table_store.py or a new logistics_store.py, the CLI/web layer,
harness/agent.py, harness/tools.py, harness/context.py, and focused tests.

### Phase 2 — protected logistics evaluation

1. Add a deterministic logistics generator and a protected logistics oracle;
   neither is editable by a candidate.
2. Extend scenario loading and evaluation dispatch from one flat inventory
   table to an input bundle plus task-family-specific answer validator.
3. Add a public incident fixture with a hand-checkable answer. For example,
   yesterday at warehouse 3 has customer C1 with 16 sent shipments, C2 with
   15, C3 with 17, and noise from other warehouses/days/statuses. The expected
   customer count is 2.
4. Freeze the structured task, reference instant, timezone, relation hashes,
   oracle version, expected-answer hash, and baseline expectation before
   candidate generation.
5. Add a capability-refusal evaluation expectation. The baseline must be
   explicitly unsupported for this answerable logistics case; a zero result or
   generic runtime error is not the intended failure.
6. Preserve every existing inventory scenario as a regression.

The logistics oracle independently filters sent shipments, resolves the fixed
day window, groups by sender_customer_id, and counts groups with a count
strictly greater than the threshold. It must not import harness code.

### Phase 3 — evidence, traceability, and history

1. Extend run, case, and evaluation contracts to record input kind, domain,
   bundle ID/hash, relation manifest (counts and hashes), task family, contract
   version, and capability request.
2. Preserve the factual task family and contract of the observed baseline run.
   An inventory harness that refuses a logistics question must not be rewritten
   as though it already supported logistics. Store the proposed logistics
   family, required relations, and required operation under a separate
   capability-gap diagnosis field; the later frozen logistics eval case carries
   logistics-shipment-threshold-v1.
3. Index the proposed capability kind/domain/family, bundle hash, and
   relevant candidate tool/capability identifiers. Continue to use runs as the
   source of capability gaps; do not use the empty capability_gaps collection.
4. Trace the refusal, domain/task metadata, registered tool names, and
   independently measured per-relation resource usage. Redact shipment rows,
   customer IDs when required, and protected answers from LangSmith.
5. Update history/UI summaries to show the capability request and compact
   bundle metadata, not raw logistics rows.
6. Add tests proving that an unsupported logistics request has a linked
   trace/history record with no data-tool spans and can be found by its
   capability kind.

### Phase 4 — create the eval and generate the capability

1. Teach the controller to classify the observed refusal as
   shipment_customer_threshold only when it maps to the approved
   logistics-shipment-threshold-v1 contract. Other logistics requests remain
   visible as awaiting_contract; the system must not invent a new data or
   database-access contract on its own.
2. Reproduce the original refusal on the exact public bundle and use the
   protected generator/oracle to materialize any derived development cases.
   Require a frozen case and independent expected answer before patch
   generation.
3. Give the proposer the redacted trace, original request, approved contract,
   allowed bridge API, disclosed reproduction, editable harness source, and
   relevant prior attempts. Do not give it credentials, private bundle IDs,
   oracle source, or expected answers.
4. Ask for one coherent hypothesis and one harness-only source change. The
   expected shape is a reusable shipment-cohort tool plus parser, tool
   registration, output validation, and context guidance—not a fixture-specific
   answer.
5. Screen the diff for hardcoded warehouse/date/customer/answer values,
   fixture IDs, changed limits, non-harness edits, imports that escape the
   sandbox, and attempts to use raw MongoDB.
6. Execute the candidate through the restricted Docker bridge and retain
   host-measured data-read, model, tool, token, and time evidence.

### Phase 5 — selection and promotion

1. Freeze an evaluation plan before either baseline or candidate runs. Pin the
   bundle manifests/hashes, data contract, oracle, bridge API, config, Docker
   image, model settings, and exact commits.
2. Require the baseline to reproduce the explicit unsupported outcome and the
   candidate to return the exact oracle answer for the original question.
3. Require inventory regressions to continue passing and require the
   candidate to retain honest refusals for revenue questions, arbitrary-query
   requests, and unapproved join requests.
4. Use private validation bundles with different customer and warehouse IDs,
   row order, page boundaries, dates, thresholds, cardinalities, and expected
   outputs. Include:

   - exactly 15 versus 16 shipments;
   - no qualifying customers;
   - one customer shipping from multiple warehouses;
   - matching and non-matching shipment statuses;
   - UTC/local-day and daylight-saving boundaries;
   - invalid duplicate shipment IDs, orphan foreign keys, and invalid
     timestamps that materialization must reject.

5. Reject a candidate that merely changes unsupported to answered, hardcodes
   the incident, raises a limit, returns an incomplete scan, accesses an
   unapproved relation, or exceeds unchanged resource limits.
6. Record capability/toolset identity on the candidate and promoted version.
   Promotion must compare-and-swap the exact parent commit and all frozen
   evaluation identities. A changed bridge, contract, manifest, config, or
   parent requires reevaluation.

## Evaluation matrix

| Case | Baseline expectation | Candidate expectation |
| --- | --- | --- |
| Original public warehouse-3/yesterday/15 question | Explicit unsupported | Exact customer count |
| Same logic, different warehouse/date/threshold | Not used to tune candidate | Exact customer count |
| Exactly 15 shipments | Not used to tune candidate | Customer excluded |
| No matching sent shipments | Not used to tune candidate | Zero |
| Other warehouse or day noise | Not used to tune candidate | Ignored |
| Invalid logistics bundle | Materialization rejected | Materialization rejected |
| Existing inventory small and edge cases | Pass | Pass |
| Existing inventory bulk baseline | Expected current limitation until separately evolved | Same declared outcome |
| Revenue, arbitrary MongoDB, or unapproved join question | Unsupported | Unsupported |

## Implementation order

1. Write and review the logistics data/task contract and exact temporal
   semantics.
2. Implement the additive logistics bundle store and its validation tests.
3. Implement the generator and independent oracle, then hand-check the public
   fixture.
4. Wire the baseline refusal, run history, and trace evidence.
5. Build the restricted candidate bridge and only then enable Phase 4
   evolution.
6. Add private validation bundles and Phase 5 gates before attempting
   promotion.

## Completion criteria

The expansion is complete only when an evaluator can inspect Atlas and
LangSmith evidence showing:

1. an original, explicit logistics capability-gap refusal;
2. a frozen immutable logistics bundle and independent expected result;
3. a screened, harness-only generated candidate;
4. a baseline-versus-candidate comparison under identical protected limits;
5. candidate success on the original, inventory regressions, and private
   logistics variations; and
6. an activated version whose capability manifest identifies the new tool and
   whose prior version remains rollbackable.
