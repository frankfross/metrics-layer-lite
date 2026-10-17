"""Execute compiled metrics against a DB-API 2.0 connection (SQLite demo)."""

from .compiler import compile_metric


def run_metric(conn, metric):
    """Run one metric definition; return a list of row dicts.

    Each row maps dimension names -> values plus ``"value"`` -> the measure.
    For a metric with no dimensions, exactly one row is returned.
    """
    sql, params = compile_metric(metric)
    cursor = conn.execute(sql, params)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def run_all_metrics(conn, metrics):
    """Run every metric; return ``{name: [rows]}`` in definition order."""
    return {m["name"]: run_metric(conn, m) for m in metrics}
