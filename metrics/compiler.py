"""Compile a metric definition (dict, usually loaded from YAML) to SQL.

Schema of one metric definition::

    name: total_revenue
    description: Sum of completed order amounts
    source: orders
    measure:
      type: sum            # count | count_distinct | sum | avg | min | max
      column: amount       # omitted for count (counts rows)
    dimensions: [region]   # optional GROUP BY columns
    filters:               # optional, AND-ed together
      - column: status
        operator: "="
        value: completed

The compiler returns ``(sql, params)`` where ``sql`` uses ``?`` placeholders
and ``params`` holds the filter values in order, so values are never
interpolated into the SQL string. Identifiers (table/column names) are
validated against ``^[A-Za-z_][A-Za-z0-9_]*$`` and rejected otherwise —
metric definitions are trusted config, but a typo should fail loudly
instead of producing a weird query.
"""

import re

from .loader import MetricError

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MEASURE_SQL = {
    "count": lambda col: "COUNT(*)",
    "count_distinct": lambda col: f"COUNT(DISTINCT {col})",
    "sum": lambda col: f"SUM({col})",
    "avg": lambda col: f"AVG({col})",
    "min": lambda col: f"MIN({col})",
    "max": lambda col: f"MAX({col})",
}

# Operator -> (sql template with {col} and {ph}, params needed)
# "IN" takes a list of values; null checks take none.
FILTER_OPS = {"=", "!=", "<>", ">", "<", ">=", "<=", "IN", "IS NULL", "IS NOT NULL"}


def _ident(name, what):
    if not isinstance(name, str) or not IDENT.match(name):
        raise MetricError(f"Invalid {what} identifier: {name!r}")
    return name


def _measure_sql(measure, metric_name):
    if not isinstance(measure, dict):
        raise MetricError(f"Metric {metric_name!r}: 'measure' must be a mapping")
    mtype = measure.get("type")
    if mtype not in MEASURE_SQL:
        raise MetricError(
            f"Metric {metric_name!r}: unknown measure type {mtype!r}; "
            f"expected one of {sorted(MEASURE_SQL)}"
        )
    if mtype == "count":
        if measure.get("column") is not None:
            raise MetricError(
                f"Metric {metric_name!r}: 'count' takes no column; "
                "use 'count_distinct' to count distinct values"
            )
        return MEASURE_SQL[mtype](None)
    column = _ident(measure.get("column"), "measure column")
    return MEASURE_SQL[mtype](column)


def _filter_clause(filt, metric_name):
    if not isinstance(filt, dict):
        raise MetricError(f"Metric {metric_name!r}: each filter must be a mapping")
    column = _ident(filt.get("column"), "filter column")
    op = str(filt.get("operator", "=")).upper()
    if op not in FILTER_OPS:
        raise MetricError(
            f"Metric {metric_name!r}: unsupported filter operator {op!r}; "
            f"expected one of {sorted(FILTER_OPS)}"
        )
    if op in ("IS NULL", "IS NOT NULL"):
        return f"{column} {op}", []
    if op == "IN":
        values = filt.get("value")
        if not isinstance(values, list) or not values:
            raise MetricError(
                f"Metric {metric_name!r}: 'IN' filter on {column} needs a non-empty list"
            )
        placeholders = ", ".join("?" for _ in values)
        return f"{column} IN ({placeholders})", list(values)
    if "value" not in filt:
        raise MetricError(
            f"Metric {metric_name!r}: filter on {column} is missing 'value'"
        )
    return f"{column} {op} ?", [filt["value"]]


def compile_metric(metric):
    """Compile one metric definition dict -> (sql, params)."""
    if not isinstance(metric, dict):
        raise MetricError("Metric definition must be a mapping")
    name = metric.get("name")
    if not name or not isinstance(name, str):
        raise MetricError("Metric definition is missing a string 'name'")
    source = _ident(metric.get("source"), "source table")
    measure_sql = _measure_sql(metric.get("measure"), name)

    dimensions = metric.get("dimensions") or []
    if not isinstance(dimensions, list):
        raise MetricError(f"Metric {name!r}: 'dimensions' must be a list")
    dimensions = [_ident(d, "dimension") for d in dimensions]

    filters = metric.get("filters") or []
    if not isinstance(filters, list):
        raise MetricError(f"Metric {name!r}: 'filters' must be a list")
    clauses, params = [], []
    for filt in filters:
        clause, values = _filter_clause(filt, name)
        clauses.append(clause)
        params.extend(values)

    select_parts = list(dimensions) + [f"{measure_sql} AS value"]
    sql = f"SELECT {', '.join(select_parts)} FROM {source}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    if dimensions:
        sql += " GROUP BY " + ", ".join(dimensions)
        sql += " ORDER BY " + ", ".join(dimensions)
    return sql, params
