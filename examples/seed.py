"""Build the demo SQLite database (demo.db) with a small orders table.

Deterministic: same seed every run, so the README's example output is
reproducible. Run:  python examples/seed.py [--db demo.db]
"""

import argparse
import random
import sqlite3
from pathlib import Path

REGIONS = ["West", "East", "Central", "South"]
STATUSES = ["completed", "refunded", "pending"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    region TEXT NOT NULL,
    status TEXT NOT NULL,
    amount REAL NOT NULL,
    order_date TEXT NOT NULL
);
"""


def build(db_path, n_orders=200, seed=42):
    rng = random.Random(seed)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.executescript(SCHEMA)
        rows = []
        for i in range(1, n_orders + 1):
            rows.append(
                (
                    i,
                    rng.randint(1, 60),
                    rng.choice(REGIONS),
                    rng.choices(STATUSES, weights=[0.8, 0.1, 0.1])[0],
                    round(rng.uniform(10, 500), 2),
                    f"2026-10-{rng.randint(1, 16):02d}",
                )
            )
        conn.executemany(
            "INSERT INTO orders (order_id, customer_id, region, status, amount, order_date)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return n_orders


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(Path(__file__).with_name("..").resolve() / "demo.db"))
    parser.add_argument("--orders", type=int, default=200)
    args = parser.parse_args()
    n = build(args.db, n_orders=args.orders)
    print(f"Seeded {n} orders into {args.db}")
