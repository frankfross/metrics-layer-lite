"""Tests for Metrics Layer Lite: compiler, loader, runner, CLI."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from metrics.compiler import compile_metric
from metrics.loader import MetricError, load_metrics
from metrics.runner import run_all_metrics, run_metric

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def conn():
    """In-memory SQLite DB with a tiny orders table with known values."""
    c = sqlite3.connect(":memory:")
    c.execute(
        "CREATE TABLE orders (order_id INTEGER, customer_id INTEGER, region TEXT,"
        " status TEXT, amount REAL)"
    )
    c.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
        [
            (1, 10, "West", "completed", 100.0),
            (2, 11, "West", "completed", 200.0),
            (3, 10, "East", "refunded", 50.0),
            (4, 12, "East", "completed", 300.0),
            (5, 13, "West", "pending", 400.0),
        ],
    )
    yield c
    c.close()


# --- compiler ---

def test_compile_count_no_dimensions():
    sql, params = compile_metric(
        {"name": "n", "source": "orders", "measure": {"type": "count"}}
    )
    assert sql == "SELECT COUNT(*) AS value FROM orders"
    assert params == []


def test_compile_sum_with_filter_and_dimension():
    sql, params = compile_metric(
        {
            "name": "rev",
            "source": "orders",
            "measure": {"type": "sum", "column": "amount"},
            "dimensions": ["region"],
            "filters": [{"column": "status", "operator": "=", "value": "completed"}],
        }
    )
    assert sql == (
        "SELECT region, SUM(amount) AS value FROM orders"
        " WHERE status = ? GROUP BY region ORDER BY region"
    )
    assert params == ["completed"]


def test_compile_count_distinct_and_in_filter():
    sql, params = compile_metric(
        {
            "name": "c",
            "source": "orders",
            "measure": {"type": "count_distinct", "column": "customer_id"},
            "filters": [
                {"column": "region", "operator": "IN", "value": ["West", "East"]},
                {"column": "status", "operator": "IS NOT NULL"},
            ],
        }
    )
    assert sql == (
        "SELECT COUNT(DISTINCT customer_id) AS value FROM orders"
        " WHERE region IN (?, ?) AND status IS NOT NULL"
    )
    assert params == ["West", "East"]


def test_compile_rejects_unknown_measure():
    with pytest.raises(MetricError, match="unknown measure type"):
        compile_metric({"name": "x", "source": "orders", "measure": {"type": "median", "column": "amount"}})


def test_compile_rejects_bad_operator():
    with pytest.raises(MetricError, match="unsupported filter operator"):
        compile_metric(
            {"name": "x", "source": "orders", "measure": {"type": "count"},
             "filters": [{"column": "status", "operator": "LIKE", "value": "com%"}]}
        )


def test_compile_rejects_bad_identifier():
    with pytest.raises(MetricError, match="Invalid"):
        compile_metric({"name": "x", "source": "orders; DROP TABLE orders;--", "measure": {"type": "count"}})


def test_compile_count_with_column_rejected():
    with pytest.raises(MetricError, match="takes no column"):
        compile_metric({"name": "x", "source": "orders", "measure": {"type": "count", "column": "amount"}})


# --- loader ---

def test_load_example_defs():
    metrics = load_metrics(ROOT / "examples" / "metrics.yaml")
    assert [m["name"] for m in metrics] == [
        "total_revenue",
        "orders_by_region",
        "avg_order_value",
        "active_customers",
        "high_value_orders",
    ]


def test_load_rejects_duplicate_names(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(
        "metrics:\n"
        "  - {name: dup, source: t, measure: {type: count}}\n"
        "  - {name: dup, source: t, measure: {type: count}}\n"
    )
    with pytest.raises(MetricError, match="duplicate"):
        load_metrics(p)


# --- runner ---

def test_run_sum_with_filter(conn):
    rows = run_metric(
        conn,
        {"name": "rev", "source": "orders", "measure": {"type": "sum", "column": "amount"},
         "filters": [{"column": "status", "operator": "=", "value": "completed"}]},
    )
    assert rows == [{"value": 600.0}]  # 100 + 200 + 300


def test_run_grouped_count(conn):
    rows = run_metric(
        conn,
        {"name": "by_region", "source": "orders", "measure": {"type": "count"},
         "dimensions": ["region"],
         "filters": [{"column": "status", "operator": "=", "value": "completed"}]},
    )
    assert rows == [{"region": "East", "value": 1}, {"region": "West", "value": 2}]


def test_run_count_distinct(conn):
    rows = run_metric(
        conn,
        {"name": "cust", "source": "orders",
         "measure": {"type": "count_distinct", "column": "customer_id"},
         "filters": [{"column": "status", "operator": "=", "value": "completed"}]},
    )
    assert rows == [{"value": 3}]  # customers 10, 11, 12


def test_run_all_returns_every_metric(conn):
    results = run_all_metrics(conn, load_metrics(ROOT / "examples" / "metrics.yaml"))
    assert set(results) == {
        "total_revenue",
        "orders_by_region",
        "avg_order_value",
        "active_customers",
        "high_value_orders",
    }
    assert results["total_revenue"] == [{"value": 600.0}]
    assert results["active_customers"] == [{"value": 3}]


# --- CLI end-to-end ---

def test_cli_run_all_end_to_end(tmp_path):
    db = tmp_path / "demo.db"
    seed = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "seed.py"), "--db", str(db)],
        capture_output=True, text=True, check=True,
    )
    assert "Seeded 200 orders" in seed.stdout
    out = subprocess.run(
        [sys.executable, "-m", "metrics.cli", "run-all",
         "--defs", str(ROOT / "examples" / "metrics.yaml"), "--db", str(db)],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    results = json.loads(out.stdout)
    assert set(results) == {
        "total_revenue",
        "orders_by_region",
        "avg_order_value",
        "active_customers",
        "high_value_orders",
    }
    assert results["orders_by_region"]  # one row per region
    assert all(row["value"] > 0 for row in results["orders_by_region"])
