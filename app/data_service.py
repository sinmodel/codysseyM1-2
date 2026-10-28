from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "samsung_2years.csv"
)


def load_stock_data() -> list[dict]:
    """Load fixed historical Samsung Electronics data for local testing."""
    with DATA_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    result = []
    for row in rows:
        result.append({
            "date": row["date"],
            "symbol": row["symbol"],
            "close": float(row["close"]),
            "data_type": row.get("data_type", "UNKNOWN"),
        })

    return result


def summarize_stock_data(rows: list[dict]) -> dict:
    if not rows:
        return {
            "count": 0,
            "mean": None,
            "max": None,
            "min": None,
            "first_date": None,
            "last_date": None,
            "first_close": None,
            "last_close": None,
            "change_percent": None,
            "data_type": None,
        }

    rows = sorted(rows, key=lambda item: item["date"])
    prices = [float(row["close"]) for row in rows]
    first_price, last_price = prices[0], prices[-1]
    change_percent = (
        (last_price - first_price) / first_price * 100
        if first_price
        else None
    )

    return {
        "count": len(rows),
        "mean": round(mean(prices), 2),
        "max": round(max(prices), 2),
        "min": round(min(prices), 2),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "first_close": round(first_price, 2),
        "last_close": round(last_price, 2),
        "change_percent": (
            round(change_percent, 2)
            if change_percent is not None
            else None
        ),
        "data_type": rows[0].get("data_type", "UNKNOWN"),
    }
