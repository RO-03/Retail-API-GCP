"""Print DB limits and purchase consistency. Run: python -m scripts.db_report

Used as a Cloud Run Job to read Postgres max_connections (pool sizing) and to check,
after a load test, that orders written equals stock removed (no overselling, no lost writes).
"""
from sqlalchemy import text

from app.core.database import engine


def report():
    with engine.connect() as conn:
        print("server_version:", conn.execute(text("SHOW server_version")).scalar())
        print("max_connections:", conn.execute(text("SHOW max_connections")).scalar())
        print("superuser_reserved_connections:",
              conn.execute(text("SHOW superuser_reserved_connections")).scalar())
        print("current_connections:",
              conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")).scalar())

        rows = conn.execute(text(
            "SELECT i.id, i.name, i.stock, COUNT(o.id) AS orders "
            "FROM items i LEFT JOIN orders o ON o.item_id = i.id GROUP BY i.id ORDER BY i.id"
        )).fetchall()
        print("item_id | name | stock | orders")
        for r in rows:
            print(f"{r.id} | {r.name} | {r.stock} | {r.orders}")
        print("total_orders:", conn.execute(text("SELECT count(*) FROM orders")).scalar())


if __name__ == "__main__":
    report()
