"""Inputs for the debug kata. Each row exists to expose one bug (tagged B1..B8)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal as D

T = datetime.fromisoformat
WEB_SCHEMA = ("order_id STRING, customer_id STRING, status STRING, amount DECIMAL(18,2), quantity INT, "
              "currency STRING, order_ts TIMESTAMP, updated_at TIMESTAMP, source STRING")
# The store extract has the SAME columns in a DIFFERENT order (quantity before amount).   [B1]
STORE_SCHEMA = ("order_id STRING, customer_id STRING, status STRING, quantity INT, amount DECIMAL(18,2), "
                "currency STRING, order_ts TIMESTAMP, updated_at TIMESTAMP, source STRING")
REGION_SCHEMA = "customer_id STRING, region STRING, valid_from DATE"

WEB = [
    ("W1", "C1", "shipped", D("100.00"), 1, "USD", T("2026-09-01 10:00"), T("2026-09-01 10:00"), "web"),
    ("W2", "C2", None, D("50.00"), 2, "EUR", T("2026-09-01 12:00"), T("2026-09-01 12:00"), "web"),        # B4
    ("W3", "C3", "shipped", D("80.00"), 1, "GBP", T("2026-09-01 16:00"), T("2026-09-01 16:00"), "web"),   # B3
    ("W4", "C1", "shipped", D("40.00"), 1, "USD", T("2026-09-02 02:00"), T("2026-09-02 02:00"), "web"),   # B6
    ("W5", None, "shipped", D("30.00"), 3, "USD", T("2026-09-01 15:00"), T("2026-09-01 15:00"), "web"),   # B7
    ("W6", "C1", "cancelled", D("999.00"), 1, "USD", T("2026-09-01 11:00"), T("2026-09-01 11:00"), "web"),
    ("W7", "C3", "shipped", D("10.00"), 1, "USD", T("2026-09-01 09:00"), T("2026-09-01 09:00"), "web"),   # B2 stale
]
STORE = [
    ("S1", "C3", "shipped", 2, D("20.00"), "USD", T("2026-09-01 14:00"), T("2026-09-01 14:00"), "store"),  # B1
    ("W7", "C3", "shipped", 1, D("12.00"), "USD", T("2026-09-01 09:00"), T("2026-09-01 11:00"), "store"),  # B2 latest
]
REGIONS = [
    ("C1", "EMEA", date(2026, 1, 1)), ("C2", "AMER", date(2026, 1, 1)), ("C3", "APAC", date(2026, 1, 1)),
    ("C2", "AMER", date(2026, 5, 1)),                                                                 # B5 dup key
]

# Correct end-to-end answer (UTC days, all currencies, NULL status counted, latest W7, no fan-out):
#   2026-09-01 EMEA   : W1 100.00                                    = 100.00 (1 order)
#   2026-09-01 AMER   : W2 50 EUR * 1.10                             =  55.00 (1)
#   2026-09-01 APAC   : W3 80 GBP * 1.25 + S1 20.00 + W7 12.00       = 132.00 (3)
#   2026-09-01 Unknown: W5 30.00 (no customer)                       =  30.00 (1)
#   2026-09-02 EMEA   : W4 40.00 (02:00 UTC)                         =  40.00 (1)
EXPECTED_TOTAL = D("357.00")
