# Metrics Layer Lite

Define business metrics once in YAML, compile them to SQL, run them against a
warehouse. No dashboard, no server — just a small, inspectable layer that
keeps "what does total revenue mean?" in one version-controlled file instead
of scattered across ad-hoc queries.

A metric is one source table, one measure, optional dimensions, optional
filters:

```yaml
metrics:
  - name: total_revenue
    description: Sum of amounts for completed orders.
    source: orders
    measure:
      type: sum
      column: amount
    filters:
      - column: status
        operator: "="
        value: completed
```

Supported measures: `count`, `count_distinct`, `sum`, `avg`, `min`, `max`.
Supported filter operators: `=`, `!=`, `<>`, `>`, `<`, `>=`, `<=`, `IN`,
`IS NULL`, `IS NOT NULL`.

## Quickstart

```bash
pip install -r requirements.txt
python examples/seed.py            # builds demo.db with 200 orders
python -m metrics.cli list --defs examples/metrics.yaml
python -m metrics.cli compile total_revenue --defs examples/metrics.yaml
python -m metrics.cli run orders_by_region --defs examples/metrics.yaml --db demo.db
python -m metrics.cli run-all --defs examples/metrics.yaml --db demo.db
```

Example output (`compile total_revenue`):

```
SELECT SUM(amount) AS value FROM orders WHERE status = ?
-- params: ['completed']
```

Example output (`run orders_by_region`):

```json
[
  { "region": "Central", "value": 34 },
  { "region": "East",    "value": 44 },
  { "region": "South",   "value": 39 },
  { "region": "West",    "value": 32 }
]
```

Example output (`run total_revenue`):

```json
[ { "value": 38737.68 } ]
```

## Design notes

- **One metric, one query.** The compiler emits a single parameterized
  `SELECT` per metric — no query builder chains, no hidden joins. What you
  see in `compile` is exactly what runs.
- **Parameters, never interpolation.** Filter values are bound as query
  parameters, so a value like `completed` can never break out of the SQL.
  Identifiers (table/column names) are validated against a strict pattern
  and rejected on anything unexpected — a typo fails loudly instead of
  producing a weird query.
- **Warehouse-agnostic by design.** The demo runs on SQLite, but the emitted
  SQL is plain `SELECT ... WHERE ... GROUP BY` that ports to any warehouse.
  A real deployment would swap the connection in `runner.py` (e.g. a
  Snowflake or Postgres DB-API connection) and add a small dialect shim for
  anything non-standard — the compiler itself stays the same.
- **Validation is part of the contract.** Duplicate metric names, unknown
  measure types, unsupported operators, empty `IN` lists, and a `count`
  with a column are all rejected at load/compile time, before anything
  touches the database. A metrics file that passes `compile` is safe to
  schedule.
- **Deliberately not included:** joins, time grains / date spines, metric
  dependencies (metrics defined in terms of other metrics), and caching.
  Each is a real feature of a production metrics layer, but each also
  doubles the surface area; this project is the honest core — definitions
  in, SQL out, results back.

## Layout

```
metrics/
  loader.py    # YAML loading + duplicate-name validation
  compiler.py  # metric definition -> (parameterized SQL, params)
  runner.py    # execute compiled metrics on a DB-API connection
  cli.py       # list / compile / run / run-all
examples/
  metrics.yaml # 5 demo metrics over an orders table
  seed.py      # builds a deterministic demo SQLite database
tests/
  test_metrics.py  # compiler, loader, runner, CLI end-to-end
```

## Tests

```bash
python -m pytest -q
# 14 passed
```
