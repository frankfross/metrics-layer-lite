"""Metrics Layer Lite: define business metrics once in YAML, compile to SQL.

A metric definition names a source table, a measure (count, sum, avg, ...),
optional dimensions to group by, and optional filters. The compiler turns it
into a single parameterized SELECT; the runner executes it against any
DB-API 2.0 connection (SQLite ships in the demo, but the emitted SQL is
plain ANSI-ish SQL that ports to any warehouse with minimal dialect tweaks).
"""

from .compiler import compile_metric, MetricError
from .loader import load_metrics
from .runner import run_metric, run_all_metrics

__all__ = ["compile_metric", "load_metrics", "run_metric", "run_all_metrics", "MetricError"]
