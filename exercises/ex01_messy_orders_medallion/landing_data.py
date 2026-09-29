"""Deterministic 'messy customer data' for Exercise 01.

Every defect below is deliberate and mirrors something that shows up in real landing zones.
Each one is labelled so the tests (and you, in an interview) can point at it.

Day 1 file  (orders_2026-09-01.jsonl)
  ORD-1001  clean ISO record                                   -> valid
  ORD-1002  padded/lower-case id, "$" amount, naive timestamp  -> valid after standardising
  ORD-1003  EUR amount as a bare JSON number, US date format   -> valid, converted to USD
  ORD-1004  customer_id missing                                -> quarantine: customer_id_present
  ORD-1005  negative amount                                    -> quarantine: amount_positive
  ORD-1006  amount is JSON null                                -> quarantine: amount_positive (NULL-safe rule!)
  ORD-1007  unparseable order timestamp                        -> quarantine: order_ts_parsed
  ORD-1001  exact duplicate line (file re-delivered upstream)  -> removed by dedupe
  (broken)  malformed JSON line                                -> quarantine: not_corrupt
  ORD-1008  US spelling "canceled", late-evening UTC order     -> valid, status normalised to "cancelled"
  ORD-1009  amount "abc"                                       -> quarantine: amount_positive (parse -> NULL)

Day 2 file  (orders_2026-09-02.jsonl)
  ORD-1001  status update Shipped -> Delivered (newer updated_at)  -> latest state wins
  ORD-1002  OUT-OF-ORDER: "cancelled" with an OLDER updated_at     -> must NOT overwrite "shipped"
  ORD-1010  customer C006 not in the customer master (orphan key)  -> kept, region "Unknown"
  ORD-1011  order_ts delivered as epoch milliseconds               -> valid

customers.csv
  C002 appears twice (name/segment changed in June)   -> join fan-out trap: must dedupe the dimension
  C004 has an empty region                            -> "Unknown"
  C006 is missing entirely                            -> orphan handled with a LEFT join
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

EPOCH_MS_ORD_1011 = int(datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc).timestamp() * 1000)

DAY1 = [
    {"order_id": "ORD-1001", "customer_id": "C001", "status": "Shipped", "amount": "1,234.50",
     "currency": "usd", "order_ts": "2026-09-01T10:15:00Z", "updated_at": "2026-09-01T10:15:00Z"},
    {"order_id": " ord-1002 ", "customer_id": "C002", "status": " shipped ", "amount": "$99.99",
     "currency": "USD", "order_ts": "2026-09-01 11:00:00", "updated_at": "2026-09-01T11:00:00Z"},
    {"order_id": "ORD-1003", "customer_id": "C003", "status": "SHIPPED", "amount": 250,
     "currency": "EUR", "order_ts": "09/01/2026 12:30", "updated_at": "2026-09-01T12:30:00Z"},
    {"order_id": "ORD-1004", "customer_id": None, "status": "shipped", "amount": "40.00",
     "currency": "USD", "order_ts": "2026-09-01T13:00:00Z", "updated_at": "2026-09-01T13:00:00Z"},
    {"order_id": "ORD-1005", "customer_id": "C001", "status": "shipped", "amount": "-5.00",
     "currency": "USD", "order_ts": "2026-09-01T14:00:00Z", "updated_at": "2026-09-01T14:00:00Z"},
    {"order_id": "ORD-1006", "customer_id": "C002", "status": "shipped", "amount": None,
     "currency": "USD", "order_ts": "2026-09-01T15:00:00Z", "updated_at": "2026-09-01T15:00:00Z"},
    {"order_id": "ORD-1007", "customer_id": "C004", "status": "shipped", "amount": "75.25",
     "currency": "GBP", "order_ts": "not a date", "updated_at": "2026-09-01T16:00:00Z"},
    "DUPLICATE_OF_FIRST",
    "MALFORMED",
    {"order_id": "ORD-1008", "customer_id": "C005", "status": "canceled", "amount": "20.00",
     "currency": "USD", "order_ts": "2026-09-01T23:30:00Z", "updated_at": "2026-09-01T23:30:00Z"},
    {"order_id": "ORD-1009", "customer_id": "C003", "status": "shipped", "amount": "abc",
     "currency": "USD", "order_ts": "2026-09-01T17:00:00Z", "updated_at": "2026-09-01T17:00:00Z"},
]

DAY2 = [
    {"order_id": "ORD-1001", "customer_id": "C001", "status": "Delivered", "amount": "1,234.50",
     "currency": "usd", "order_ts": "2026-09-01T10:15:00Z", "updated_at": "2026-09-02T09:00:00Z"},
    {"order_id": "ORD-1002", "customer_id": "C002", "status": "cancelled", "amount": "$99.99",
     "currency": "USD", "order_ts": "2026-09-01 11:00:00", "updated_at": "2026-09-01T10:00:00Z"},
    {"order_id": "ORD-1010", "customer_id": "C006", "status": "shipped", "amount": "500.00",
     "currency": "EUR", "order_ts": "2026-09-02T01:30:00Z", "updated_at": "2026-09-02T01:30:00Z"},
    {"order_id": "ORD-1011", "customer_id": "C002", "status": "shipped", "amount": "60.00",
     "currency": "usd", "order_ts": str(EPOCH_MS_ORD_1011), "updated_at": "2026-09-02T02:00:00Z"},
]

CUSTOMERS_CSV = """customer_id,name,region,segment,updated_at
C001,Acme Corp,EMEA,Enterprise,2026-01-01
C002,Globex,AMER,SMB,2026-01-01
C003,Initech,APAC,SMB,2026-01-01
C004,Umbrella,,Enterprise,2026-01-01
C005,Hooli,AMER,Enterprise,2026-01-01
C002,Globex Inc,AMER,Mid-Market,2026-06-01
"""

# Static FX table for simplicity. Real life: rates are date-effective, so this becomes an
# as-of join on (currency, rate_date <= order_date) -- mention it when you present.
FX_RATES = [("USD", 1.00), ("EUR", 1.10), ("GBP", 1.25)]


def _lines(records: list) -> list[str]:
    out = []
    for rec in records:
        if rec == "DUPLICATE_OF_FIRST":
            out.append(json.dumps(records[0]))
        elif rec == "MALFORMED":
            out.append('{"order_id": "ORD-BROKEN", "customer_id": "C001", "amount": ')  # truncated write
        else:
            out.append(json.dumps(rec))
    return out


def write_landing_zone(base_dir: str | Path) -> dict[str, str]:
    """Write the landing files the way an upstream system would drop them in a Volume."""
    base = Path(base_dir)
    orders_dir = base / "landing" / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    (orders_dir / "orders_2026-09-01.jsonl").write_text("\n".join(_lines(DAY1)) + "\n")
    (orders_dir / "orders_2026-09-02.jsonl").write_text("\n".join(_lines(DAY2)) + "\n")
    customers = base / "landing" / "customers.csv"
    customers.write_text(CUSTOMERS_CSV)
    return {
        "day1": str(orders_dir / "orders_2026-09-01.jsonl"),
        "day2": str(orders_dir / "orders_2026-09-02.jsonl"),
        "customers": str(customers),
        "base": str(base),
    }
