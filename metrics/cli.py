"""Command-line interface for Metrics Layer Lite.

Usage:
    python -m metrics.cli list --defs examples/metrics.yaml
    python -m metrics.cli compile total_revenue --defs examples/metrics.yaml
    python -m metrics.cli run total_revenue --defs examples/metrics.yaml --db demo.db
    python -m metrics.cli run-all --defs examples/metrics.yaml --db demo.db
"""

import argparse
import json
import sqlite3
import sys

from .loader import MetricError, get_metric, load_metrics
from .compiler import compile_metric
from .runner import run_all_metrics, run_metric


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Metrics Layer Lite: YAML metrics -> SQL -> results")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--defs", default="examples/metrics.yaml", help="Path to metrics YAML file")
        p.add_argument("--db", default="demo.db", help="SQLite database file (run / run-all only)")

    list_p = sub.add_parser("list", help="List metric names and descriptions")
    add_common(list_p)
    compile_p = sub.add_parser("compile", help="Print the SQL for one metric")
    compile_p.add_argument("name")
    add_common(compile_p)
    run_p = sub.add_parser("run", help="Run one metric and print JSON rows")
    run_p.add_argument("name")
    add_common(run_p)
    run_all_p = sub.add_parser("run-all", help="Run every metric and print JSON results")
    add_common(run_all_p)
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    try:
        metrics = load_metrics(args.defs)
    except (MetricError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "list":
        for metric in metrics:
            print(f"{metric['name']}\t{metric.get('description', '')}")
        return 0

    if args.command == "compile":
        try:
            sql, params = compile_metric(get_metric(metrics, args.name))
        except MetricError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(sql)
        print(f"-- params: {params}")
        return 0

    # run / run-all need the database
    try:
        conn = sqlite3.connect(args.db)
    except sqlite3.Error as exc:
        print(f"error: cannot open database {args.db}: {exc}", file=sys.stderr)
        return 1
    try:
        if args.command == "run":
            try:
                rows = run_metric(conn, get_metric(metrics, args.name))
            except MetricError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            print(json.dumps(rows, indent=2, default=str))
        else:
            print(json.dumps(run_all_metrics(conn, metrics), indent=2, default=str))
    except sqlite3.Error as exc:
        print(f"error: query failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
